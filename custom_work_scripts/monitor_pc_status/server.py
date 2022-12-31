# -*- coding:utf-8 -*-
import http.server
import os
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util.CommonUtil import CommonUtil
from util.AdbUtil import AdbUtil
from util.NetUtil import NetUtil

"""
运行于待被监控的pc端,可以通过get请求查看本机连接的手机设备信息
请求: {本机ip地址}:8989/adb_devices_online
返回http code 200, 并且有返回非空的手机序列号说明电脑正常

本地浏览器访问:      http://localhost:8989
curl命令 GET 访问:  curl http://localhost:8989/adb_devices_online
curl命令 POST 访问: curl http://localhost:8989/adb_devices_online -d "name=tom&age=25"

端口可通过 config.ini 修改
"""

from base.BaseConfig import BaseConfig
from util.FileUtil import FileUtil


class RequestHandlerImpl(http.server.BaseHTTPRequestHandler):
    """
    自定义一个 HTTP 请求处理器
    """

    def do_GET(self):
        """
        处理 GET 请求, 处理其他请求需实现对应的 do_XXX() 方法
        """
        # print(self.server)                # HTTPServer 实例
        # print(self.client_address)        # 客户端地址和端口: (host, port)
        # print(self.requestline)           # 请求行, 例如: "GET / HTTP/1.1"
        # print(self.command)               # 请求方法, "GET"/"POST"等
        # print(self.path)                  # 请求路径, Host 后面部分
        # print(self.headers)               # 请求头, 通过 headers["header_name"] 获取值
        # self.rfile                        # 请求输入流
        # self.wfile                        # 响应输出流

        resp = 'hello %s' % self.path
        if "/adb_devices_online" == self.path:
            # resp = CommonUtil.exeCmd('adb devices -l')
            names = AdbUtil().getAllDeviceId(onlineOnly=True)[0]
            resp = ', '.join(names)

        # 1. 发送响应code
        self.send_response(200)

        # 2. 发送响应头
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        # 3. 发送响应内容（此处流不需要关闭）
        self.wfile.write(('%s\n' % resp).encode("utf-8"))

    def do_POST(self):
        """
        处理 POST 请求
        """
        # 0. 获取请求Body中的内容（需要指定读取长度, 不指定会阻塞）
        req_body = self.rfile.read(int(self.headers["Content-Length"])).decode()
        print("req_body: " + req_body)

        # 1. 发送响应code
        self.send_response(200)

        # 2. 发送响应头
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        # 3. 发送响应内容（此处流不需要关闭）
        self.wfile.write(("Hello World: " + req_body + "\n").encode("utf-8"))


class PcServerImpl(BaseConfig):
    def notifyDingding(self, msg: str):
        if CommonUtil.isNoneOrBlank(msg):
            return

        robotSection = self.configParser.getSectionItems('robot')
        token = robotSection['accessToken']
        content = "%s\n%s" % (robotSection['keyWord'], robotSection['extraInfo'])
        content = content.strip()
        content += '\n%s' % msg
        print(content)
        if CommonUtil.isNoneOrBlank(token):
            print('accessToken为空, 无需发送通知')
        else:
            atPhoneList = robotSection['atPhone'].split(',')
            print(NetUtil.push_ding_talk_robot(content, token, False, atPhoneList))

    def onRun(self):
        ip = NetUtil.getIp()
        port = -1
        try:
            port = int(self.configParser.get('server', 'port'))
            self.notifyDingding('正在启动Server...\n本机ip: %s\n端口: %s' % (ip, port))

            # 服务器绑定的地址和端口
            server_address = ("", port)
            # 创建一个 HTTP 服务器（Web服务器）, 指定绑定的地址/端口 和 请求处理器
            httpd = http.server.HTTPServer(server_address, RequestHandlerImpl)
            # 循环等待客户端请求
            httpd.serve_forever()
        except Exception as e:
            self.notifyDingding('启动Server失败\n本机ip:%s\n端口: %s\n错误信息:\n%s' % (ip, port, e))


if __name__ == '__main__':
    # 根据配置文件, 提取指定位置的文件
    curDir = FileUtil.getParentPath(os.path.abspath(__file__))
    configPath = FileUtil.recookPath('%s/config.ini' % curDir)
    PcServerImpl(configPath, optFirst=True).run()
