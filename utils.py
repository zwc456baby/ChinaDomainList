import os


def log(msg, filename='china_host_list_server'):
    """
    打印服务端日志
    注意：如果部署的服务器中没有 log 日志工具，注释此行
    目前只有将服务部署于 linux 中才会保存运行日志
    :param filename:
    :param msg:
    :return:
    """
    if os.name.lower() == "posix":
        os.system('log -f{} "{}"'.format(filename, msg))


def getMsgByCode(code):
    """
        1000: 添加到数据库成功
        1001: 已经存在此host
        1002: host 解析错误
        1003: host 解析ip不位于 china
        1004: 长度太长了
        1005: 从数据库中删除
        1101: 输入域名格式不正确
    :param code:
    :return:
    """
    response_msg = {
        1000: "添加域名成功,白名单列表将在第二天自动更新,感谢您的提交",
        1001: "添加失败,已存在此域名或父级规则",
        1002: "解析域名IP失败,请确认输入数据无误",
        1003: "域名对应IP不处于CN",
        1004: "输入域名长度超出",
        1005: "域名已从白名单删除",
        1101: "请输入正确的域名"
    }
    return response_msg.get(code, "未知错误")
