# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os

from base.BaseConfig import BaseConfig
from util.AdbUtil import AdbUtil
from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

"""
清除日志, 要求config.ini中包含 clear_logs.parent_log_dir_in_phone 属性
"""


class GetLogImpl(BaseConfig):

    def run(self):
        sectionName = 'clear_logs'
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
        for logPath in pendingPullLogList:
            print('正在删除日志:%s' % logPath)
            adbUtil.exeShellCmds(['su', 'rm -r %s' % logPath], targetDeviceId)

        print('清除logcat日志')
        CommonUtil.exeCmd('adb -s %s logcat -c' % targetDeviceId)


if __name__ == '__main__':
    # 根据配置文件, 清理日志
    curDir = FileUtil.getParentPath(os.path.abspath(__file__))
    configPath = FileUtil.recookPath('%s/config.ini' % curDir)
    GetLogImpl(configPath, optFirst=True).run()
