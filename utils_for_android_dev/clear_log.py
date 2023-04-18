# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os
import re
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from base.BaseConfig import BaseConfig
from util.AdbUtil import AdbUtil
from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

"""
清除日志, 要求config.ini中包含 clear_logs.parent_log_dir_in_phone 属性
"""


class ClearLogImpl(BaseConfig):

    def onRun(self):
        sectionName = 'clear_log'
        keyParentLogDirInPhone = 'parent_log_dir_in_phone'  # 手机中的日志父目录路径key

        parent_log_dir_in_phone = self.configParser.get(sectionName, keyParentLogDirInPhone)
        pullLogDict = self.configParser.getSectionItems(sectionName)

        # 待清除的日志路径
        pendingPullLogList = list()
        for key in pullLogDict:
            if key in [keyParentLogDirInPhone]:
                continue

            key = FileUtil.recookPath(key)
            if key.startswith('/'):
                pendingPullLogList.append(key)
            elif not CommonUtil.isNoneOrBlank(parent_log_dir_in_phone):
                pendingPullLogList.append(FileUtil.recookPath('%s/%s' % (parent_log_dir_in_phone, key)))

        if len(pendingPullLogList) == 0:
            print('待清除的日志路径列表为空, 请检查后再试')
            return

        # 依次删除日志
        adbUtil = AdbUtil()
        targetDeviceId = adbUtil.choosePhone()  # 选择待截图的手机信息
        regularPathList = list()  # 正则表达式路径
        for logPath in pendingPullLogList:
            if '*' in logPath:
                rPath = FileUtil.recookPath(logPath).strip()
                if not rPath.startswith('/'):
                    rPath = FileUtil.recookPath('%s/%s' % (parent_log_dir_in_phone, rPath))
                regularPathList.append(rPath)
                continue
            print('正在删除日志:%s' % logPath)
            if adbUtil.isFileExist(logPath):
                adbUtil.exeShellCmds(['su', 'rm -r %s' % logPath], targetDeviceId, printCmdInfo=False)

        # 根据正则路径,删除相关日志
        subRegularFileList = list()
        for regularPath in regularPathList:
            fullName, _, _ = FileUtil.getFileName(regularPath)
            parentDirPath = FileUtil.getParentPath(regularPath)

            # 获取所有子文件名, 并进行正则匹配
            stdout, stderr = adbUtil.exeShellCmds(['ls %s' % parentDirPath],
                                                  deviceId=targetDeviceId,
                                                  printCmdInfo=False)
            if stderr is not None:
                print('获取子文件名列表失败 stderr=%s' % stderr)
                break

            for name in stdout.split():
                name = CommonUtil.convert2str(name)
                if re.search(r'%s' % fullName, name) is not None:
                    path = FileUtil.recookPath('%s/%s' % (parentDirPath, name))
                    subRegularFileList.append(path)

        for path in subRegularFileList:
            print('正在删除正则路径日志 %s' % path)
            adbUtil.deleteFromPhone(path, targetDeviceId)

        print('清除logcat日志')
        CommonUtil.exeCmd('adb -s %s logcat -c' % targetDeviceId, printCmdInfo=False)


if __name__ == '__main__':
    # 根据配置文件, 清理日志
    curDir = FileUtil.getParentPath(os.path.abspath(__file__))
    configPath = FileUtil.recookPath('%s/config.ini' % curDir)
    ClearLogImpl(configPath, optFirst=True).run()
