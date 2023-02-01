# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os
import platform
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base.BaseConfig import BaseConfig
from util.AdbUtil import AdbUtil
from util.FileUtil import FileUtil
from util.TimeUtil import TimeUtil

"""
通过adb对手机屏幕进行截图,兼容多台设备情况
需要指定配置文件 --config xxx  其中需包含 screenshot.save_dir 信息,用于记录文件保存位置 
"""


class TakeScreenShotUtil(BaseConfig):
    def onRun(self):
        picFolder = self.configParser.get('screenshot', 'save_dir')
        picFolder = FileUtil.recookPath('%s/' % picFolder)
        FileUtil.createFile(picFolder)

        if not FileUtil.isDirFile(picFolder):
            print('截图保存目录不存在, 请确保已创建成功 %s' % picFolder)
            return

        adbUtil = AdbUtil()
        targetDeviceId = adbUtil.choosePhone()  # 选择待截图的手机信息
        # 手机中执行adb截图命令, 保存到sdcard/下
        picName = 'screenshot_%s_%s.png' % (TimeUtil.getTimeStr('%Y%m%d%H%M%S'), targetDeviceId)
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
