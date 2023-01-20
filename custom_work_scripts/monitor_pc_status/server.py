# -*- coding:utf-8 -*-
import http.server
import os
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import threading
import time
from util.CommonUtil import CommonUtil
from util.AdbUtil import AdbUtil
from util.NetUtil import NetUtil
from custom_work_scripts.monitor_pc_status.MonitorUtil import MonitorUtil

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
            resp = PcServerImpl.getAllDeviceIdInfo()

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

    @staticmethod
    def getAllDeviceIdInfo() -> str:
        """
        获取本机连接的可用手机列表信息,使用逗号连接, 格式: 序列号1,序列号2,....
        """
        names = AdbUtil().getAllDeviceId(onlineOnly=True)[0]
        return ', '.join(names)

    def check(self, duration_sec: int, log_path: str):
        """
        进行一次自检, 检查当前连接的手机信息, 与本地缓存的上一次信息之间的变化
        :param duration_sec: 间隔指定时长后,再次自检,单位:s
        :param log_path:本地日志路径
        :return str:手机列表变化结果,若为空,则表示无变化,不需要发送钉钉通知
        """
        # 首次启动自检,即使设备无变更也发送一次钉钉通知
        startup_check = True
        while True:
            deviceIdInfo = PcServerImpl.getAllDeviceIdInfo()
            failMsg = MonitorUtil.checkPhoneList(deviceIdInfo, log_path)
            FileUtil.write2File(log_path, deviceIdInfo, autoAppendLineBreak=False, enableEmptyMsg=True)

            if not CommonUtil.isNoneOrBlank(failMsg):
                self.notifyDingding('server端自检结果:\n%s' % failMsg)
            elif startup_check:
                self.notifyDingding('server端首次自检正常,当前连接的设备为:\n%s' % deviceIdInfo)
            else:
                print('server和adb devices列表正常, 与上一次无差别')
            startup_check = False
            if duration_sec <= 0:
                break
            else:
                time.sleep(duration_sec)

    def scheduleCheck(self, duration_sec: int, logPath: str):
        """
        定期发起自检, 检测本机连接的手机列表信息
        """
        if duration_sec <= 0:
            self.check(duration_sec, logPath)
            return
        thread = threading.Thread(target=self.check, args=[duration_sec, logPath])
        thread.start()

    def onRun(self):
        ip = NetUtil.getIp()
        port = -1
        try:
            port = int(self.configParser.get('server', 'port'))
            self.notifyDingding('正在启动Server...\n本机ip: %s\n端口: %s' % (ip, port))

            # 查看定期轮询时间间隔,单位:min,若小于等于0,则不作轮询, 仅启动一次
            check_duration = int(self.configParser.get('server', 'check_duration'))
            log_dir_path = self.configParser.get('server', 'log_dir_path')
            if CommonUtil.isNoneOrBlank(log_dir_path):
                log_dir_path = '%s/log' % os.path.dirname(__file__)
            log_dir_path = FileUtil.recookPath(log_dir_path)
            logPath = '%s/last_devices_server.txt' % log_dir_path
            self.scheduleCheck(check_duration * 60, logPath)

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
