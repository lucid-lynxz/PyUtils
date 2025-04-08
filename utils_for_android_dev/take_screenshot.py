# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os
import platform
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from base.BaseConfig import BaseConfig
from util.AdbUtil import AdbUtil
from util.FileUtil import FileUtil
from util.TimeUtil import TimeUtil
from util.CommonUtil import CommonUtil

"""
通过adb对手机屏幕进行截图,兼容多台设备情况
需要指定配置文件 --config xxx  其中需包含 screenshot.save_dir 信息,用于记录文件保存位置 
"""


class TakeScreenShotUtil(BaseConfig):
    def onRun(self):
        section = 'screenshot'
        picFolder = self.configParser.get(section, 'save_dir')
        picFolder = FileUtil.recookPath('%s/' % picFolder)
        FileUtil.createFile(picFolder)

        if not FileUtil.isDirFile(picFolder):
            print('截图保存目录不存在, 请确保已创建成功 %s' % picFolder)
            return

        time_format = self.configParser.get(section, 'timeFormat')
        includeDeviceId = self.configParser.getboolean(section, 'includeDeviceId')
        prefix = self.configParser.get(section, 'prefix')
        subfix = self.configParser.get(section, 'subfix')

        adbUtil = AdbUtil()
        targetDeviceId = adbUtil.choosePhone()  # 选择待截图的手机信息
        prefix = "" if CommonUtil.isNoneOrBlank(prefix) else f"{prefix}_"
        subfix = "" if CommonUtil.isNoneOrBlank(subfix) else f"_{subfix}"
        deviceId = f"_{targetDeviceId}" if includeDeviceId else ""
        picName = f'{prefix}{TimeUtil.getTimeStr(time_format)}{deviceId}{subfix}.png'

        # 手机中执行adb截图命令, 保存到sdcard/下
        screenShotPathInPhone = FileUtil.recookPath('/sdcard/%s' % picName)
        adbUtil.exeShellCmds(['screencap -p %s' % screenShotPathInPhone], targetDeviceId)

        # 提取截图文件到本机中
        localShotPngPath = FileUtil.recookPath('%s/%s' % (picFolder, picName))
        adbUtil.pull(screenShotPathInPhone, localShotPngPath, targetDeviceId)
        exist = FileUtil.isFileExist(localShotPngPath)
        if exist:
            self.taskParam.files.append(localShotPngPath)
            print('截图提取完成,删除手机中的截图...')
            adbUtil.exeShellCmds(['rm -rf %s' % screenShotPathInPhone], targetDeviceId)
            # 打开目录
            system = platform.system()
            print('current system is: %s' % system)
            print('提取完成,马上打开截图目录:%s' % picFolder)
            FileUtil.openDir(picFolder)
        else:
            print('提取截图失败, 请手动提取...')


if __name__ == '__main__':
    # 根据配置文件, 提取截图文件要保存的本机路径
    curDir = FileUtil.getParentPath(os.path.abspath(__file__))
    configPath = FileUtil.recookPath('%s/config.ini' % curDir)
    TakeScreenShotUtil(configPath, optFirst=True).run()
