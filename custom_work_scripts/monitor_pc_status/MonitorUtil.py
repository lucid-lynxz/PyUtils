# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil


class MonitorUtil(object):
    @staticmethod
    def checkPhoneList(curPhoneListStr: str, logPath: str) -> str:
        """
        检查手机列表的变化情况
        :param curPhoneListStr: 当前通过adb获取的手机列表, 格式为: 序列号1,序列号2,序列号3,...
        :return str: 错误信息, 若为空,表示与上次相比没有变化, 无需发出通知
        """
        failMsg = ''
        if CommonUtil.isNoneOrBlank(curPhoneListStr):
            failMsg = '获取到的设备列表为空,请及时检查'
        else:
            # 上一次请求成功获取到的设备列表信息,格式: 序列号1,序列号2
            # 多个设备序列号间使用逗号分隔,可能还有空格, 具体依据server端的格式进行解析
            lastDeviceSet: set = MonitorUtil.parseDevicesInfo(FileUtil.readFile(logPath))

            # 与上一次设备列表(通过日志提取)进行对比,若有增减,也发出通知
            curDevicesSet: set = MonitorUtil.parseDevicesInfo([curPhoneListStr])
            offlineDeviceSet = lastDeviceSet - curDevicesSet
            newOnlineDeviceSet = curDevicesSet - lastDeviceSet

            if len(offlineDeviceSet) > 0:
                failMsg = '与上次相比:\n被移除的手机: ' + ', '.join(offlineDeviceSet)
            if len(newOnlineDeviceSet) > 0:
                if not CommonUtil.isNoneOrBlank(failMsg):
                    failMsg += '\n'
                failMsg += '发现新手机: ' + ', '.join(newOnlineDeviceSet)
        return failMsg

    @staticmethod
    def parseDevicesInfo(strList: list, splitFlag: str = ',') -> set:
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
