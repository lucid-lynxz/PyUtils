# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base.BaseConfig import BaseConfig
from util.AdbUtil import AdbUtil
from util.CommonUtil import CommonUtil
from util.CompressUtil import CompressUtil
from util.FileUtil import FileUtil
from util.TimeUtil import TimeUtil


class GetLogImpl(BaseConfig):
    def run(self):
        sectionName = 'get_log'
        keySaveDir = 'save_dir'  # 日志保存在本机的路径key
        keyParentLogDirInPhone = 'parent_log_dir_in_phone'  # 手机中的日志父目录路径key
        keyCompressFile = 'compress_file'  # 待压缩的本机文件路径key
        keySevenZipPath = 'seven_zip_path'  # 压缩工具路径
        keyExcludeCompressFile = 'exclude_compress_file'  # 压缩工具路径

        # 非待提取的日志路径参数
        notLogPathKeyList = list()
        notLogPathKeyList.append(keySaveDir)
        notLogPathKeyList.append(keyParentLogDirInPhone)
        notLogPathKeyList.append(keyCompressFile)
        notLogPathKeyList.append(keySevenZipPath)
        notLogPathKeyList.append(keyExcludeCompressFile)

        save_parent_dir = self.configParser.get(sectionName, keySaveDir)
        if CommonUtil.isNoneOrBlank(save_parent_dir):
            print('save_dir参数为空, 请检查后重试')
            return
        save_parent_dir = FileUtil.recookPath('%s/' % save_parent_dir)
        FileUtil.makeDir(save_parent_dir)

        sevenZipPath = self.configParser.get(sectionName, keySevenZipPath)
        compressFile = self.configParser.get(sectionName, keyCompressFile)
        parent_log_dir_in_phone = self.configParser.get(sectionName, keyParentLogDirInPhone)
        pullLogDict = self.configParser.getSectionItems(sectionName)

        # 待提取的日志路径, 元素是 tuple(源日志路径, 提取后的存储路径)
        pendingPullLogList = list()
        for key in pullLogDict:
            if key in notLogPathKeyList:
                continue

            key = FileUtil.recookPath(key)
            value = pullLogDict.get(key, None)
            if not key.startswith('/') and not CommonUtil.isNoneOrBlank(parent_log_dir_in_phone):
                key = FileUtil.recookPath('%s/%s' % (parent_log_dir_in_phone, key))
            pendingPullLogList.append((key, value))

        if len(pendingPullLogList) == 0:
            print('待提取的日志路径列表为空, 请检查后再试')
            return

        # 创建本机中日志保存子目录
        # 要提取保存在本机中的路径
        timeInfo = TimeUtil.getTimeStr('%Y%m%d_%H%M%S')
        saveDirPath = FileUtil.recookPath('%s/%s_log/' % (save_parent_dir, timeInfo))
        FileUtil.makeDir(saveDirPath)

        # 依次提取日志
        adbUtil = AdbUtil()
        targetDeviceId = adbUtil.choosePhone()  # 选择待截图的手机信息
        for itemTuple in pendingPullLogList:
            logPath, localLogPath = itemTuple
            if CommonUtil.isNoneOrBlank(localLogPath):
                localLogPath = saveDirPath
            else:
                localLogPath = FileUtil.recookPath('%s/%s' % (saveDirPath, localLogPath))

            if FileUtil.isDirPath(localLogPath):
                FileUtil.makeDir(localLogPath)

            print('正在提取日志:%s' % logPath)
            adbUtil.pull(logPath, localLogPath, targetDeviceId)

        print('提取anr日志')
        adbUtil.pullANRFile(saveDirPath, targetDeviceId)

        print('提取logcat信息')
        adbUtil.getLogcatInfo(saveDirPath, level='V', logcatFileName='logcatV.txt', deviceId=targetDeviceId)
        adbUtil.getLogcatInfo(saveDirPath, level='E', logcatFileName='logcatE.txt', deviceId=targetDeviceId)

        print('尝试删除一级空白子目录')
        allSubFiles = FileUtil.listAllFilePath(saveDirPath)
        for subFilePath in allSubFiles:
            if FileUtil.isDirFile(subFilePath) and len(FileUtil.listAllFilePath(subFilePath)) == 0:
                print('删除空目录 %s' % subFilePath)
                FileUtil.deleteFile(subFilePath)

        # 压缩子目录
        if not CommonUtil.isNoneOrBlank(compressFile) and not CommonUtil.isNoneOrBlank(sevenZipPath):
            excludeCompressFile = self.configParser.get(sectionName, keyExcludeCompressFile)
            compressFile = FileUtil.recookPath('%s/%s' % (saveDirPath, compressFile))
            CompressUtil(sevenZipPath).compress(compressFile, excludeDirName=excludeCompressFile)

        print('提取完成, 打开目录: %s' % saveDirPath)
        FileUtil.openDir(saveDirPath)


if __name__ == '__main__':
    # 根据配置文件, 提取指定位置的文件
    curDir = FileUtil.getParentPath(os.path.abspath(__file__))
    configPath = FileUtil.recookPath('%s/config.ini' % curDir)
    GetLogImpl(configPath, optFirst=True).run()
