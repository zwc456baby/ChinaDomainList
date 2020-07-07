
# CN 域名白名单列表

目前github上已有许多同类仓库，例如 gfw whiteList,
但是很多库长久不更新，或者更新不及时，要么作者已经放弃了
此库最大的不同在于

**白名单列表可由所有人进行维护**

## 说明

本程序会将提交的域名暂存到数据库中
每日凌晨4点自动将数据库中的域名列表输出到文件
并提交到 github 上

域名提交例子： `example.com` , `*.example.com`

目前仅支持通配符提交


## 使用方式

- 安装 `SwitchyOmega`
- 新建情景模式，自动切换模式
- 添加规则列表：`https://github.com/zwc456baby/ChinaDomainList/raw/master/whitelist.txt`
- 默认情景模式选代理，规则列表选择直连

## 如何提交域名

[点击直达提交网页](https://whitedomain.zwc365.com)

在网页输入框中输入域名后，回车提交即可

## 程序如何判定域名的?

程序是如何判定域名是否位于CN呢？通过以下步骤：

1. 抓取公共的IP归属列表
2. 对提交的域名解析其IP地址
3. 判定IP地址是否位于CN，如果是，则添加到白名单中


## 初始列表来源

使用其中的域名对数据库进行初始化
[blackwhite](https://github.com/txthinking/blackwhite)

使用了其中的正则规则
[gfw_whitelist](https://github.com/neko-dev/gfw_whitelist)

IP归属地抓取链接：
`http://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest`


