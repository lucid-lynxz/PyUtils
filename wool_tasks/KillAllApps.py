# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from util.AdbUtil import AdbUtil

from airtest.aircv import *
from base.BaseConfig import BaseConfig
from util.NetUtil import NetUtil
from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil


class KillApp(BaseConfig):
    """
    主要用于jenkins脚本,在流程终止后,停止运行的app,关闭屏幕, 以便使设备冷却降温省电减少寿命损耗
    """

    def onRun(self):
        # 结束上一次wool进程
        processInfoPath = self.configParser.get('setting', 'processInfoPath')
        pids = FileUtil.readFile(processInfoPath)
        for pid in pids:
            CommonUtil.killPid(pid)

        # 结束手机中的app
        appInfoList = self.configParser.getSectionKeyList('app_info')
        adbUtil: AdbUtil = AdbUtil()
        devIds = adbUtil.getAllDeviceId(onlineOnly=True)[0]
        for devId in devIds:
            print(f'killAllApps for devId={devId},pending kill appInfoList={appInfoList}')
            if CommonUtil.isNoneOrBlank(appInfoList):  # 关闭所有进程
                adbUtil.killApp(appPkgName=None, deviceId=devId)
            else:
                for appInfo in appInfoList:  # 只关闭指定进程
                    adbUtil.killApp(appPkgName=appInfo, deviceId=devId)
            adbUtil.screenOff(deviceId=devId)  # 关闭屏幕

        # 发送钉钉通知
        robotSection = self.configParser.getSectionItems('robot')
        content = f"{robotSection['keyWord']}\n{robotSection['extraInfo']}\nkillApp finished:{devIds}"
        content = content.strip()
        print(f'killApp finish content={content}')
        print(NetUtil.push_to_robot(content, robotSection))


if __name__ == "__main__":
    # 默认使用当前目录下的 config.ini 文件路径
    # 通过 --config xxx.ini 传入配置文件路径
    curDirPath = os.path.abspath(os.path.dirname(__file__))
    configPath = '%s/config_kill_all_apps.ini' % curDirPath

    KillApp(configPath, optFirst=True).run()
