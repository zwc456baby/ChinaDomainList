import json
import os
import shutil
import socket
import time
from urllib.parse import urlparse

import redis
import requests

from ip2region_lib.ip2Region import Ip2Region
from utils import log

_pool = redis.ConnectionPool(host='127.0.0.1', port=8888, decode_responses=True)
redis_db = redis.Redis(connection_pool=_pool)

max_ip_length = 4
white_host_hashname = 'gfw_white_hostname_hash'
white_host_del_tmp_format = 'gfw_white_domain_del_tmp_{}'
white_ip_hashname_format = 'gfw_white_ip_hash_{}'
redis_hash_key_max_length = 128
whitelist_filename = 'whitelist.txt'

"""
如果处于测试状态，将不从数据库读取及写入，用来测试代码正确性
某些地方仅用来读取数据
"""
is_test = False


def getip(hostname):
    """
    从域名获取 ip 地址
    :param hostname: 输入的域名名称
    :return: ip
    """
    try:
        domain = hostname
        if hostname.startswith("*."):
            domain = hostname.lstrip("*.")
        return socket.gethostbyname(domain)
    except Exception:
        return ""


def ischina(ip):
    """
    判断该ip是否为国内地址
    :param ip: 输入的 ip 地址
    :return: True or False
    """
    if is_test:
        return True
    if searcher.isip(ip):
        data = searcher.btreeSearch(ip)
        ip_info = data["region"].decode('utf-8').split('|')
        return ip_info[0] == "中国"
    else:
        return False


def checkHost(_hostname):
    """
    判断域名是否为国内 ip 地址，如果是，添加到数据库中
        1000: 添加到数据库成功
        1001: 已经存在此host
        1002: host 解析错误
        1003: host 解析ip不位于 china
        1004: 长度太长了
        1005: 从数据库中删除
    :param _hostname:
    :return:
    """
    hostname = _hostname.strip('\n')
    parse_domain = urlparse(hostname)
    hostname = parse_domain.netloc
    if hostname is None or hostname == "":
        hostname = parse_domain.path
    if len(hostname) > redis_hash_key_max_length:
        return 1004
    host_ip = getip(hostname)
    print('input host:{} ,scheme:{} ,ip:{}'.format(hostname, parse_domain.scheme, host_ip))
    if host_ip is None or host_ip == "":
        return 1002
    if ischina(host_ip):
        is_exists, updata_db, domain_key = _checkOrSetDomain(hostname, host_ip, parse_domain.scheme)
        if is_exists and not updata_db:
            print('exists domain:{}'.format(domain_key))
            return 1001
        if is_test:
            print("add hostname:{} ,ip:{} to hash".format(hostname, host_ip))
        else:
            log('success add host:{} ,scheme:{} ,ip:{} to redis db'.format(hostname, parse_domain.scheme, host_ip))
        return 1000
    else:
        db_host_ip = "" if is_test else redis_db.hget(white_host_hashname, hostname)
        if db_host_ip is not None and str(db_host_ip) != "":
            _tryDeleteDomain(hostname)
        return 1003


def checkAllHostIp():
    """
    每隔一段时间，再次检测该域名解析的 ip 地址是否位于国内
    :return:
    """
    # 首先更新 ip 数据
    _updateAllIpList()
    if is_test:
        return
    for k in redis_db.hkeys(white_host_hashname):
        hostname = k
        host_ip = getip(hostname)
        if host_ip is None or host_ip == "":
            # 解析不到 ip 地址
            # 说明这个 域名已经无法正常解析
            # 此时需要移除
            _tryDeleteDomain(hostname)
            continue
        if not ischina(host_ip):
            # 之前解析的ip位于国内
            # 而目前最新的解析显示ip位于国外，则移除这个域名
            _tryDeleteDomain(hostname)
        else:
            _checkOrSetDomain(hostname, host_ip)
            # redis_db.hset(white_host_hashname, hostname, host_ip)


def _tryDeleteDomain(domain):
    """
    尝试从 白名单列表移除一个域名
    注意：
        域名只有失效 一天才会被移除
        这是为了网站可能因为某些原因暂时无法解析到正确IP
    :param domain:
    :return:
    """
    delete_tmp_time = redis_db.get(white_host_del_tmp_format.format(domain))
    if delete_tmp_time is None or delete_tmp_time == "":
        redis_db.setex(white_host_del_tmp_format.format(domain), 60 * 60 * 72,
                       int(time.time()))
    else:
        try:
            db_time = int(delete_tmp_time)
            if db_time < (int(time.time()) - 60 * 60 * 24):
                redis_db.hdel(white_host_hashname, domain)
        except ValueError:
            redis_db.hdel(white_host_hashname, domain)


def getHostnameToFile():
    """
    写入 redis 中的 hostname 到txt 文本中
    如果需要手动添加一个 host 到文件，则写入 extwhitelist.txt 即可
    程序运行时，会将 extwhitelist.txt 文件的内容附加到 whitelist.txt
    建议每日定时执行
    :return:
    """
    filename = whitelist_filename
    ext_filename = 'extwhitelist.txt'
    if os.path.exists(filename):
        os.remove(filename)
    if os.path.exists(ext_filename):
        shutil.copyfile(ext_filename, filename)
    with open(filename, mode='a+', encoding="UTF-8") as file:
        for k in redis_db.hkeys(white_host_hashname):
            file.write(_getDomainLineByKey(k))
        file.flush()


def _getDomainLineByKey(domain_key):
    """
    通过 key ，获取保存的信息，并构建一行规则
    :param domain_key:
    :return:
    """
    result_str = ""
    domain_info_str = "" if is_test else redis_db.hget(white_host_hashname, domain_key)
    try:
        domain_info = json.loads(domain_info_str, encoding='utf-8')
        if domain_info['ishttps']:
            result_str = '|https://{}\n'.format(domain_key)
        if domain_info['ishttp']:
            result_str = '{}||{}\n'.format(result_str,
                                           domain_key.lstrip("*.") if domain_key.startswith("*.") else domain_key)
    except Exception:
        pass
    if result_str is None or result_str == "":
        result_str = '{}\n'.format(domain_key if domain_key.startswith("*.") else domain_key)
    return result_str


def _updateAllIpList():
    """
    从 ip 管理局更新 国内 ip 列表
    :return:
    """
    iplist_response = requests.get("http://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest")
    print(iplist_response.status_code)
    if iplist_response.status_code != 200:
        print('get all iplist faild:{}'.format(iplist_response.status_code))
        return
    print("成功获取ip数据,正在将数据保存到本地数据库中,请稍后...")
    clearCityList = {}
    for ipline in iplist_response.text.splitlines():
        if ipline.startswith("#") or ipline.startswith(";"):
            continue
        ipinfo = ipline.split('|')
        if ipinfo[2].upper() == "IPV4" or ipinfo[2].upper() == "IPV6":
            # 测试方式下，只检测 cn ip
            if is_test and ipinfo[1].upper() != "CN":
                continue
            if clearCityList.get(ipinfo[1].upper(), 0) == 0:
                clearCityList[ipinfo[1].upper()] = 1
                hash_name_key = white_ip_hashname_format.format(ipinfo[1].upper())
                _deleteAllHash(hash_name_key)
            if is_test:
                return
    print("刷新本地数据库成功")


def _deleteAllHash(hashname):
    """
    删除数据库中 hash 存在的所有数据
    用来重新从网络获取 ip 数据
    redis 有直接删除的方式
    但是我使用的是兼容库 ssdb
    这个库对于 hash 中的数据只能遍历删除
    如果部署为 redis ，可以修改此方法
    :param hashname:
    :return:
    """
    if is_test:
        return
    for k in redis_db.hkeys(hashname):
        redis_db.hdel(hashname, k)
    redis_db.delete(hashname)


def _checkOrSetDomain(domain, hostip, scheme=''):
    """
    检测 域名是否已经存在数据库中，包括使用 *. 进行的匹配域名
    实际上这里应该扩展为正则匹配，但是目前只能使用 一个通配符
    :param domain:
    :return:
    """
    domain_exists = False
    domain_key = ""
    def_domain_info = {
        'hostip': hostip,
        'ishttp': False,
        'ishttps': False
    }
    domain_key_tmp, max_length = _fromDomainGetKey(domain, child=-1)
    domain_exists, domain_info_str = _checkDomainExistsByKey(domain_key_tmp)

    if (not domain_exists) and max_length > 2:
        for index in range(2, max_length):
            domain_key_tmp, max_length = _fromDomainGetKey(domain, child=index)
            domain_exists, domain_info_str = _checkDomainExistsByKey(domain_key_tmp, regex=True)
            if domain_exists:
                break
    if domain_exists:
        domain_key = domain_key_tmp
        try:
            domain_info = json.loads(domain_info_str, encoding='utf-8')
        except Exception:
            domain_info = def_domain_info
    else:
        domain_info = def_domain_info
    need_set_db = not domain_exists
    if scheme == 'http' and not domain_info['ishttp']:
        domain_info['ishttp'] = True
        need_set_db = True
    elif scheme == 'https' and not domain_info['ishttps']:
        domain_info['ishttps'] = True
        need_set_db = True
    if hostip != domain_info['hostip']:
        domain_info['hostip'] = hostip
        need_set_db = True
    if need_set_db:
        redis_db.hset(white_host_hashname, domain, json.dumps(domain_info, ensure_ascii=False))

    return domain_exists, need_set_db, domain_key


def _checkDomainExistsByKey(domain_key, regex=False):
    if regex:
        split_start = domain_key.find(".")
        if split_start != -1:
            new_key = "*.{}".format(domain_key[split_start + 1:len(domain_key)])
        else:
            new_key = "*.{}".format(domain_key)
        db_host_info = "" if is_test else redis_db.hget(white_host_hashname, new_key)
        if db_host_info is not None and str(db_host_info) != "":
            return True, db_host_info
        if domain_key.startswith("*."):
            return False, ''
    elif domain_key is not None and domain_key != "":
        db_host_info = "" if is_test else redis_db.hget(white_host_hashname, domain_key)
        if db_host_info is not None and str(db_host_info) != "":
            return True, db_host_info
    return False, ""


def _fromDomainGetKey(domain, child=-1):
    result_str = ""
    split_size = -1
    if domain is None or domain == "":
        return result_str, split_size
    if domain.find('.') != -1:
        domain_split_l = domain.split('.')
        split_size = len(domain_split_l)
        if split_size < 2:
            return result_str, split_size
    else:
        return result_str, split_size

    if child > len(domain_split_l):
        return result_str, split_size

    for_end_index = 0 if child == -1 else len(domain_split_l) - child
    for index in range(len(domain_split_l) - 1, -1, -1):
        if index < for_end_index:
            break
        if result_str == "":
            result_str = domain_split_l[index]
        else:
            result_str = "{}.{}".format(domain_split_l[index], result_str)
    return result_str, split_size


def initDb():
    """
    从文件中读取初始的域名
    避免项目刚部署时没有任何数据
    init 后可以从接口单个获取数据
    :return:
    """
    log('start init db data')
    filename = 'inithost.txt'
    init_lock_file = 'initsuccess'
    if not os.path.exists(filename):
        if is_test:
            log('can not found inithost.txt')
        return
    # 使用一个文件占位，如果已经初始化了，则不再初始化
    if os.path.exists(init_lock_file):
        log('initsuccess file exists')
        return
    with open(filename, mode='r', encoding="UTF-8") as file:
        while True:
            line = file.readline()
            if line is None or line == "":
                break
            if line.startswith('#'):
                continue
            if line.startswith(';'):
                continue
            if line.startswith('!'):
                continue
            if line.startswith('|'):
                continue
            if line.startswith('||'):
                line = line.lstrip('||')
            status_code = checkHost(line)
            print('add host:{} to db status:{}'.format(line, status_code))
    getHostnameToFile()
    with open(init_lock_file, mode='w+') as f:
        pass
    log('init db data and get hostname to file success')


if is_test:
    # updateAllIpList()
    checkHost('*.www.baidu.com')
    # result = _fromDomainGetKey('www.baidu.com', 2)
    # print(result)
    # _checkDbExistsDomain('*.www.baidu.com')

searcher = Ip2Region('./ip2region_lib/ip2region.db')

if __name__ == '__main__':
    initDb()
    if not os.path.exists(whitelist_filename):
        getHostnameToFile()
