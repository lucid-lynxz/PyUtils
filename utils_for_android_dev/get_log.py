# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

import re
from base.BaseConfig import BaseConfig
from base.TaskManager import TaskParam, TaskLifeCycle
from util.AdbUtil import AdbUtil
from util.CommonUtil import CommonUtil
from util.CompressUtil import CompressUtil
from util.FileUtil import FileUtil
from util.TimeUtil import TimeUtil


class GetLogImpl(BaseConfig):

    def onRun(self):
        sectionName = 'get_log'
        keySaveDir = 'save_dir'  # 日志保存在本机的路径key
        keyParentLogDirInPhone = 'parent_log_dir_in_phone'  # 手机中的日志父目录路径key
        keyExcludeRemoveFile = 'remove_file'  # 提取日志后, 需要删除的无用日志信息,可多条,逗号分隔
        keyCompressFile = 'compress_file'  # 待压缩的本机文件路径key
        keySevenZipPath = 'seven_zip_path'  # 压缩工具路径
        keyExcludeCompressFile = 'exclude_compress_file'  # 压缩工具路径
        keyExcludeDecrypt = 'auto_decrypt_log'  # 是否解密日志
        keyExcludeCompressFileLimitSize = 'compress_file_limit'  # 压缩包大小限制
        keyPrintLog = 'print_log'  # 是否打印日志

        # 非待提取的日志路径参数
        notLogPathKeyList = list()
        notLogPathKeyList.append(keySaveDir)
        notLogPathKeyList.append(keyParentLogDirInPhone)
        notLogPathKeyList.append(keyExcludeRemoveFile)
        notLogPathKeyList.append(keyCompressFile)
        notLogPathKeyList.append(keySevenZipPath)
        notLogPathKeyList.append(keyExcludeCompressFile)
        notLogPathKeyList.append(keyExcludeCompressFileLimitSize)
        notLogPathKeyList.append(keyExcludeDecrypt)
        notLogPathKeyList.append(keyPrintLog)
        print_log = 'True' == self.configParser.get(sectionName, keyPrintLog)

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
        pendingPullLogList = list()  # 普通路径信息
        pendingPullLogRegexList = list()  # 正则路径信息
        regexPrefix = '(regex)'  # 正则路径信息的前缀标志符号
        regexIndex = len(regexPrefix)
        for key in pullLogDict:
            if key in notLogPathKeyList:
                continue

            oriKey = key
            targetList = pendingPullLogList
            if key.startswith(regexPrefix):
                targetList = pendingPullLogRegexList
                key = key[regexIndex:]
            else:
                key = FileUtil.recookPath(key)

            value = pullLogDict.get(oriKey, None)
            if not key.startswith('/') and not CommonUtil.isNoneOrBlank(parent_log_dir_in_phone):
                key = FileUtil.recookPath('%s/%s' % (parent_log_dir_in_phone, key))
            targetList.append((key, value))

        # 对正则路径进行识别, 转化为待提取的绝对路径信息并追加到 pendingPullLogList 中
        adbUtil = AdbUtil()
        targetDeviceId = adbUtil.choosePhone()  # 选择目标手机
        if len(pendingPullLogRegexList) > 0:
            for itemTuple in pendingPullLogRegexList:
                logPath, localLogPath = itemTuple
                arr = logPath.split('/')
                regexName = arr[-1]
                parentDirPath = '/'.join(arr[:-1])
                fileList = adbUtil.getFileList(parentDirPath, regexFileName=regexName, deviceId=targetDeviceId)
                for item in fileList:
                    pendingPullLogList.append((item, localLogPath))

        if len(pendingPullLogList) == 0:
            print('待提取的日志路径列表为空, 请检查后再试')
            return

        # 创建本机中日志保存子目录
        # 要提取保存在本机中的路径
        timeInfo = TimeUtil.getTimeStr('%Y%m%d_%H%M%S')
        saveDirPath = FileUtil.recookPath('%s/%s_log/' % (save_parent_dir, timeInfo))
        FileUtil.makeDir(saveDirPath)
        print('提取的日志会保存到:%s' % saveDirPath)

        # 将结果目录保存到参数中
        self.taskParam.files.append(saveDirPath)
        self.taskParam.configParser.updateSectonItem(TaskParam.runtimeParamSectionName, "saveDirPath", saveDirPath)

        # 依次提取日志
        for itemTuple in pendingPullLogList:
            logPath, localLogPath = itemTuple
            if CommonUtil.isNoneOrBlank(localLogPath):
                localLogPath = saveDirPath
            else:
                localLogPath = FileUtil.recookPath('%s/%s' % (saveDirPath, localLogPath))

            if FileUtil.isDirPath(localLogPath):
                FileUtil.makeDir(localLogPath)

            print('正在提取日志:%s' % logPath)
            adbUtil.pull(logPath, localLogPath, targetDeviceId, printCmdInfo=print_log)

        print('提取anr日志')
        adbUtil.pullANRFile(saveDirPath, targetDeviceId, printCmdInfo=print_log)

        print('提取tombstone日志')
        adbUtil.pullTombstoneFile(saveDirPath, targetDeviceId, printCmdInfo=print_log)

        print('提取logcat信息')
        adbUtil.getLogcatInfo(saveDirPath, level='V', logcatFileName='logcatV.txt',
                              deviceId=targetDeviceId,
                              printCmdInfo=print_log)
        # adbUtil.getLogcatInfo(saveDirPath, level='E', logcatFileName='logcatE.txt', deviceId=targetDeviceId)

        print('尝试删除一级空白子目录')
        allSubFiles = FileUtil.listAllFilePath(saveDirPath)
        for subFilePath in allSubFiles:
            if FileUtil.isDirFile(subFilePath) and len(FileUtil.listAllFilePath(subFilePath)) == 0:
                print('  删除 %s' % subFilePath)
                FileUtil.deleteFile(subFilePath)

        # 删除 config.ini 中指定的无用日志信息
        removeFiles = self.configParser.get(sectionName, keyExcludeRemoveFile)
        self._removeFiles(saveDirPath, removeFiles)

        # 压缩子目录
        if not CommonUtil.isNoneOrBlank(compressFile) and not CommonUtil.isNoneOrBlank(sevenZipPath):
            print('提取完成，尝试压缩文件')
            excludeCompressFile = self.configParser.get(sectionName, keyExcludeCompressFile)
            excludeCompressFileLimitSize = self.configParser.get(sectionName, keyExcludeCompressFileLimitSize)
            compressFile = FileUtil.recookPath('%s/%s' % (saveDirPath, compressFile))
            dst = CompressUtil(sevenZipPath).compress(compressFile, excludeDirName=excludeCompressFile,
                                                      sizeLimit=excludeCompressFileLimitSize)
            # 压缩成功后,若只有一个压缩包,则重命名 'xx.zip.001' 为 'xx.zip'
            if not CommonUtil.isNoneOrBlank(excludeCompressFileLimitSize) \
                    and not CommonUtil.isNoneOrBlank(dst) \
                    and not FileUtil.isFileExist('%s.002' % dst):
                FileUtil.moveFile('%s.001' % dst, dst)

        if not self.isTaskExist(taskLifeCycle=TaskLifeCycle.afterRun):
            print('完成所有提取日志操作, 打开目录: %s' % saveDirPath)
            FileUtil.openDir(saveDirPath)

    def _removeFiles(self, rootDir: str, removeFiles: str):
        """
        删除指定目录下的文件
        :param rootDir: 父目录,非空
        :param removeFiles: 待删除的文件信息,支持多条,逗号分隔,每条最后一级文件名支持正则表达式
        """
        if CommonUtil.isNoneOrBlank(removeFiles):
            return

        for removeFile in removeFiles.split(','):
            tRemoveFile = FileUtil.recookPath('%s/%s' % (rootDir, removeFile))
            fullName, _, _ = FileUtil.getFileName(tRemoveFile)
            fullName = fullName.replace('(', '\\(').replace(')', '\\)')
            parentDirPath = FileUtil.getParentPath(tRemoveFile)

            allFiles = FileUtil.listAllFilePath(parentDirPath)
            for name in allFiles:
                if re.search(r'%s' % fullName, name) is not None:
                    path = FileUtil.recookPath('%s/%s' % (parentDirPath, name))
                    FileUtil.deleteFile(path)


if __name__ == '__main__':
    # 根据配置文件, 提取指定位置的文件
    curDir = FileUtil.getParentPath(os.path.abspath(__file__))
    configPath = FileUtil.recookPath('%s/config.ini' % curDir)
    GetLogImpl(configPath, optFirst=True).run()
