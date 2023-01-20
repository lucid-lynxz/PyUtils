# -*- coding:utf-8 -*-
import os
import sys
import urllib.error
import urllib.request as urllib2

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from util.CommonUtil import CommonUtil
from base.BaseConfig import BaseConfig
from util.FileUtil import FileUtil
from util.NetUtil import NetUtil
from custom_work_scripts.monitor_pc_status.MonitorUtil import MonitorUtil

"""
client端, 用于发起一次请求给server端
对于未收到响应或者响应中的手机设备序列号为空的情形,发起钉钉通知
"""


class ClientMonitorImpl(BaseConfig):

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

    def check(self, server_address: str, server_port: str, log_path: str, startup_check: bool = False):
        """
        发起请求, 获取当前可用的手机列表信息, 并与本地日志比较
        :param server_address: 服务器地址
        :param server_port:服务端端口
        :param log_path: 日志文件路径
        :param startup_check:当前是否是第一次自检, 若是,则即使设备列表未变化也会发出一次钉钉通知
        """
        headers = {"Content-type": "application/json"}
        url = '%s:%s/adb_devices_online' % (server_address, server_port)
        request = urllib2.Request(url=url, headers=headers, method="GET")
        failMsg = ''
        responseStr = ''
        try:
            response = urllib2.urlopen(request)
            responseStr = response.read().decode('utf-8').strip()
            print(responseStr)
            print('adb_devices_online response=%s' % responseStr)
            failMsg = MonitorUtil.checkPhoneList(responseStr, log_path)
            FileUtil.write2File(log_path, responseStr, autoAppendLineBreak=False, enableEmptyMsg=True)
        except urllib.error.URLError as e:
            FileUtil.write2File(log_path, '', autoAppendLineBreak=False, enableEmptyMsg=True)
            if isinstance(e.reason, ConnectionRefusedError):
                failMsg = '请求失败: ConnectionRefusedError\n请检查目标主机是否离线'
            else:
                failMsg = '请求失败: %s' % e.reason
        except Exception as e:
            FileUtil.write2File(log_path, '', autoAppendLineBreak=False, enableEmptyMsg=True)
            failMsg = '请求失败: %s' % e
        finally:
            if not CommonUtil.isNoneOrBlank(failMsg):
                self.notifyDingding('client端%s\n%s' % (failMsg, url))
            elif startup_check:
                self.notifyDingding('client端:启动成功\n设备列表未变化,当前为:\n%s\n%s' % (responseStr, url))
            else:
                print('server和adb devices列表正常, 与上一次无差别')

    def onRun(self):
        clientKvDict = self.configParser.getSectionItems('client')
        server_port = self.configParser.get('server', 'port')
        server_address = clientKvDict.get('server_address', '127.0.0.1')
        if CommonUtil.isNoneOrBlank(server_address):
            self.notifyDingding('monitor client端执行失败: server_address为空, 请检查config配置西西里')
            return

        log_dir_path = clientKvDict.get('log_dir_path', '')
        if CommonUtil.isNoneOrBlank(log_dir_path):
            log_dir_path = '%s/log' % os.path.dirname(__file__)
        log_dir_path = FileUtil.recookPath(log_dir_path)

        # 上一次请求成功获取到的设备列表信息,格式: 序列号1, 序列号2
        # 多个设备序列号间使用逗号分隔,可能还有空格, 具体依据server端的格式进行解析
        logPath = '%s/last_devices_client.txt' % log_dir_path

        # 查看定期轮询时间间隔,单位:min,若小于等于0,则不作轮询, 仅启动一次
        check_duration = clientKvDict.get('check_duration', '0')
        duration = int(check_duration)
        # 首次启动自检,即使设备无变更也发送一次钉钉通知
        startup_check = True
        if duration > 0:
            duration_secs = duration * 60
            startup_check: bool = True
            while True:
                self.check(server_address, server_port, logPath, startup_check)
                startup_check = False
                time.sleep(duration_secs)
        else:
            self.check(server_address, server_port, logPath, startup_check)


if __name__ == '__main__':
    # 根据配置文件, 提取指定位置的文件
    curDir = FileUtil.getParentPath(os.path.abspath(__file__))
    configPath = FileUtil.recookPath('%s/config.ini' % curDir)
    ClientMonitorImpl(configPath, optFirst=True).run()
