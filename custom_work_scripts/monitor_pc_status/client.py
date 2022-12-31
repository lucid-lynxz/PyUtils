# -*- coding:utf-8 -*-
import os
import sys
import urllib.error
import urllib.request as urllib2

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util.CommonUtil import CommonUtil
from base.BaseConfig import BaseConfig
from util.FileUtil import FileUtil
from util.NetUtil import NetUtil

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

    def parseDevicesInfo(self, strList: list, splitFlag: str = ',') -> set:
        """
        解析日志信息列表, 每行字符串使用 splitFlag 进行拆分, 去除空格后得到序列号
        """
        result: set = set()
        for line in strList:
            if CommonUtil.isNoneOrBlank(line):
                continue
            for seri in line.split(splitFlag):
                if CommonUtil.isNoneOrBlank(seri):
                    continue
                result.add(seri.strip())
        return result

    def onRun(self):
        server_port = self.configParser.get('server', 'port')

        clientKvDict = self.configParser.getSectionItems('client')
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
        logPath = '%s/last_devices.txt' % log_dir_path
        lastDeviceSet: set = self.parseDevicesInfo(FileUtil.readFile(logPath))  # 上一次请求得到的设备信息

        headers = {"Content-type": "application/json"}
        url = '%s:%s/adb_devices_online' % (server_address, server_port)
        request = urllib2.Request(url=url, headers=headers, method="GET")
        failMsg = ''
        try:
            response = urllib2.urlopen(request)
            responseStr = response.read().decode('utf-8').strip()
            print(responseStr)
            print('adb_devices_online response=%s' % responseStr)
            FileUtil.write2File(logPath, responseStr, autoAppendLineBreak=False, enableEmptyMsg=True)
            if CommonUtil.isNoneOrBlank(responseStr):
                failMsg = 'adb devices设备列表为空,请及时检查'
            else:

                # 与上一次设备列表(通过日志提取)进行对比,若有增减,也发出通知
                curDevicesSet: set = self.parseDevicesInfo([responseStr])
                offlineDeviceSet = lastDeviceSet - curDevicesSet
                newOnlineDeviceSet = curDevicesSet - lastDeviceSet

                if len(offlineDeviceSet) > 0:
                    failMsg = '与上次相比:\n被移除的手机: ' + ', '.join(offlineDeviceSet)
                if len(newOnlineDeviceSet) > 0:
                    if not CommonUtil.isNoneOrBlank(failMsg):
                        failMsg += '\n'
                    failMsg += '发现新手机: ' + ', '.join(newOnlineDeviceSet)
        except urllib.error.URLError as e:
            FileUtil.write2File(logPath, '', autoAppendLineBreak=False, enableEmptyMsg=True)
            if isinstance(e.reason, ConnectionRefusedError):
                failMsg = '请求失败: ConnectionRefusedError\n请检查目标主机是否离线'
            else:
                failMsg = '请求失败: %s' % e.reason
        except Exception as e:
            FileUtil.write2File(logPath, '', autoAppendLineBreak=False, enableEmptyMsg=True)
            failMsg = '请求失败: %s' % e
        finally:
            if not CommonUtil.isNoneOrBlank(failMsg):
                self.notifyDingding('%s\n%s' % (failMsg, url))
            else:
                print('server和adb devices列表正常, 与上一次无差别')


if __name__ == '__main__':
    # 根据配置文件, 提取指定位置的文件
    curDir = FileUtil.getParentPath(os.path.abspath(__file__))
    configPath = FileUtil.recookPath('%s/config.ini' % curDir)
    ClientMonitorImpl(configPath, optFirst=True).run()
