import datetime
import os
import sched
import threading
import time

from flask import Flask, request, jsonify, make_response

import host_utils
from utils import log, getMsgByCode

app = Flask(__name__)

"""
自动运行脚本并提交到 github 的时候为凌晨 4 点
"""
autoRunScriptHour = 4


@app.after_request
def af_request(resp):
    """
    #请求钩子，在所有的请求发生后执行，加入headers。
    :param resp:
    :return:
    """
    resp = make_response(resp)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET,POST'
    resp.headers['Access-Control-Allow-Headers'] = 'x-requested-with,content-type'
    return resp


@app.route('/api/checkhostname', methods=['GET', 'POST'])
def check_host():
    """
    传入参数后检测 host 是否为国内网站
    检测方式：
        1.获取 host ip 地址
        2.判断ip地址是否为国内地址
    :return:
    """
    checkhost = request.args.get('checkhost', None)
    if checkhost is None or checkhost == "":
        checkhost = request.form.get('checkhost', None)
    if checkhost is None or checkhost == "":
        return jsonify({'status': 1101, "msg": getMsgByCode(1101)})

    status_code = host_utils.checkHost(checkhost)
    return jsonify({'status': status_code, "msg": getMsgByCode(status_code)})


def schedulerTaskRun():
    """
    使用定时任务，每日定时更新一次 txt 文本
    为了防止出现隐藏的错误，发生异常时将保存错误日志
    :return:
    """
    addFuncToScheduler()
    try:
        log('run china host list write job')
        host_utils.checkAllHostIp()
        host_utils.getHostnameToFile()
        log('success write china host list to file')
    except Exception as e:
        log('run scheduler job exception,please check:{}'.format(e),
                filename="china_host_list_server_error")
    runGitCommit()
    log('success commit to github')


def addFuncToScheduler():
    now = datetime.datetime.now()
    sched_time = now.replace(hour=autoRunScriptHour, minute=0)

    delay_time = 60 * 60 * 24 - (now.timestamp() - sched_time.timestamp())
    if now.timestamp() < sched_time.timestamp():
        delay_time = sched_time.timestamp() - now.timestamp()

    # 不使用下方定时的方式，而是使用延迟的方式
    # 使用定时方式需要注意设定日期，年份等，而延迟 则相对简单不易错
    # if sched_time.timestamp() <= now.timestamp():
    #     sched_time = sched_time.replace(day=sched_time.day + 1)
    # log('success add job to scheduler,month:{} ,day:{} ,hour:{} ,minute:{}'.format(
    #     sched_time.month, sched_time.day, sched_time.hour, sched_time.minute))
    # scheduler.enterabs(sched_time.timestamp(), 0, schedulerTaskRun)
    scheduler.enter(delay_time, 0, schedulerTaskRun)


def runScheduler():
    """
    定时任务，任务在子线程中运行
    需要调用 run 才会执行
    :return:
    """
    global scheduler
    scheduler = sched.scheduler(time.time, time.sleep)
    addFuncToScheduler()
    scheduler.run()


def runGitCommit():
    """
    自动执行 添加 及 push 操作，更新 github 中的列表文件
    :return:
    """
    os.system('git add .')
    os.system('git commit -m "script auto commit,day:{}"'.format(datetime.datetime.now().day))
    os.system('git push origin master')


if __name__ == '__main__':
    log('run china host list server')
    host_utils.initDb()
    scheduler_thread = threading.Thread(target=runScheduler, daemon=True)
    scheduler_thread.start()
    app.run(debug=True, host="0.0.0.0", port=8120)
