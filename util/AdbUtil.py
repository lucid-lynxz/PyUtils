# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import subprocess

from util import FileUtil
from util.CommonUtil import CommonUtil


class AdbUtil(object):
    def __init__(self, adbPath: str = ''):
        """
        :param adbPath: adb应用程序的路径,若为空,则请确保已添加到环境变量中
        """
        self.adbPath = 'adb' if CommonUtil.isNoneOrBlank(adbPath) else adbPath

    def getAllDeviceId(self) -> tuple:
        """
        通过adb devices -l 命令获取所有设备id(未判断offline等特殊情况)
        :return: tuple(设备序列号列表,设备model名称列表)
        """
        device_ids_list = []
        device_names_list = []
        out = CommonUtil.exeCmd("%s devices -l" % self.adbPath)
        devices_info_list = "" if out is None else out.splitlines()
        for line in devices_info_list:
            if 'List of devices attached' in line:
                continue
            if 'device:' in line:
                split = line.split()  # 多空格切分
                device_ids_list.append(split[0])
                device_name = ""
                for info in split:
                    if 'model:' in info:
                        device_name = info.split(":")[1]
                        break
                device_names_list.append(device_name)
        return device_ids_list, device_names_list

    def isAvailable(self, deviceId: str) -> bool:
        """
        判断指定 deviceId 对应的设备是否连接在当前电脑上
        :param deviceId: 待确定的设备id
        :return:true-该设备连接在当前电脑上
        """
        deviceId = "" if deviceId is None else deviceId.rstrip()
        if len(deviceId) == 0:
            return False
        availableDeviceIds, _ = self.getAllDeviceId()
        return deviceId in availableDeviceIds

    def choosePhone(self) -> str:
        """
        自动检测当前连接的设备数,若有多台,则提示用户选择一台,并返回其设备id
        :return: str 被选中的设备的序列号
        """
        ids, names = self.getAllDeviceId()
        target_device_id = ids[0]  # 用户最终选定的设备,默认为第一台
        length = len(ids)
        if length > 1:
            print('检测到有多台设备: ')
            for i in range(length):
                print('%s %s\t%s' % (i, names[i], ids[i]))

            index_input = input('\n请选择要操作的设备序号(默认0):\n')
            index_choose = 0
            if index_input is not None and len(index_input.strip()) > 0:
                index_choose = int(index_input)

            target_device_id = ids[index_choose]
            print('您选定的设备为:%s %s\n' % (target_device_id, names[index_choose]))
        return target_device_id

    def _getDeviceIdOpt(self, deviceId: str = None) -> str:
        """
        按需生成adb命令设备号参数信息  -s {deviceId}
        :param deviceId:  设备号
        :return:
        """
        if deviceId is None or len(deviceId) == 0:
            device_opt = ''
        else:
            device_opt = '-s %s' % deviceId
        return device_opt

    def exeShellCmds(self, cmdArr: list, deviceId: str = None) -> tuple:
        """
        在 adb shell 中执行cmd列表命令
        :param cmdArr: 命令列表,如 ["su","ls","exit"], 会自动拼接成 adb -s deviceId shell ***
        :param deviceId: 若同时连接多台设备,则需要给出设备id
        :return: tuple(stdout,stderr)
        """
        cmd_adb_shell = '%s %s shell' % (self.adbPath, self._getDeviceIdOpt(deviceId))
        cmdArr.append('exit')
        pipe = subprocess.Popen(cmd_adb_shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        cmds_str = '\n'.join(cmdArr)
        cmds_str = '%s\n' % cmds_str
        stdout, stderr = pipe.communicate(cmds_str.encode())
        print("%s shell\n%sstdout=%s,stderr=%s" % (self.adbPath, cmds_str, stdout, stderr))
        return stdout, stderr

    def pull(self, src: str, dest: str = ".", deviceId: str = None):
        """
        通过adb从手机中pull出特定文件到指定位置
        :param deviceId: 设备id,多台设备共存时需要指定
        :param src: 手机中源文件路径
        :param dest: 存储到本机的目录路径,若路径以 "/" 结尾,则提取源文件到该目录下,保持同名,请自行确保本机目录存在
        :return: 本机存储文件路径,若pull失败,则返回 ""
        """
        path, src_file_name = os.path.split(src)

        if CommonUtil.isNoneOrBlank(dest):
            dest = "./"

        cmd = "%s %s pull %s %s" % (self.adbPath, self._getDeviceIdOpt(deviceId), src, dest)
        result = CommonUtil.exeCmd(cmd)
        if result is not None and "adb: error: " in result:
            return ""
        if dest.endswith("/"):
            dest = "%s/%s" % (dest, src_file_name)  # 本机文件路径
        return dest

    def push(self, src: str,
             dest: str,
             deviceId: str = None,
             pushLocalFileSelf: bool = True) -> bool:
        """
        推送本机指定资源文件到手机指定位置
        :param src: 本机中的资源文件路径,可以是文件或者目录路径
        :param dest: 手机端的目标路径, 要求目录已存在
        :param deviceId: 手机设备id
        :param pushLocalFileSelf: 是否是push本地文件本身,若为false,则表示 push 本地目录下的子文件 (localResPath表示目录时有效)
        :return: True/False 是否push成功
        """
        if not FileUtil.isFileExist(src):
            print("push localResPath 不存在,无需push: %s" % src)
            return True

        # 若 localResPath 表示目录,且需要push资源根目录下的子文件,则遍历得到子文件路径,添加到待push列表
        pendingPushFiles = list()
        if not pushLocalFileSelf:
            subFileList = os.listdir(src)  # 返回的是子文件的相对路径
            subFileSize = 0 if subFileList is None else len(subFileList)
            if subFileSize > 0:
                for subFileName in subFileList:
                    pendingPushFiles.append("%s/%s" % (src, subFileName))
            else:
                pendingPushFiles.append(src)
        else:
            pendingPushFiles.append(src)

        # subFileList = FileUtil.listAllFilePath(localResPath)
        # subFileSize = 0 if subFileList is None else len(subFileList)
        # subFileSize = 0
        # if subFileSize > 0 and not pushLocalFileSelf:
        #     for subFile in subFileList:
        #         pendingPushFiles.append(subFile)
        # else:
        #     pendingPushFiles.append(localResPath)

        print("start pushLocalFileSelf=%s,localResPath=%s deviceId=%s,remoteDirPath=%s" % (
            pushLocalFileSelf, src, deviceId, dest))

        success = True  # 有一个推送失败就表示失败
        for tFile in pendingPushFiles:
            # adb命令,明确拼接目标位置文件名称, 以便兼容中文文件名
            fName = FileUtil.getFileName(tFile)[0]
            # runCmd = 'adb %s push %s %s/%s' % (AdbUtil.get_device_id_opt(deviceId).rstrip(), tFile, remoteDirPath, fName)
            runCmd = '%s %s push %s %s' % (self.adbPath, self._getDeviceIdOpt(deviceId), tFile, dest)
            result = CommonUtil.exeCmd(runCmd)
            if result is not None and "adb: error:" not in result and " pushed" in result:
                # success = True
                pass
            else:
                success = False
            print("push %s 结果success=%s,result=%s" % (runCmd, success, result))
        return success

    def setLogcatBufferSize(self, size: str = '16M', deviceId: str = None) -> str:
        """
        设置logcat的缓冲区大小
        :param size: 缓冲区大小,默认设置为最大16M, 可填入其他数值, 以K, M 结尾, 具体可参考手机设置 开发者选项 - 日志缓冲区大小
        :param deviceId: 设备id
        :return:
        """
        cmd = "%s %s logcat -G %s" % (self.adbPath, self._getDeviceIdOpt(deviceId), size)
        return CommonUtil.exeCmd(cmd)

    def getLogcatInfo(self, saveDirPath: str,
                      level: str = "E",
                      logcatFileName: str = "logcat.txt",
                      deviceId: str = None):
        """
        抓取指定级别的日志,并存入 save_folder 中, 若有 tombstone 文件, 则尝试 pull
        :param saveDirPath: 日志文件保存目录
        :param level 日志级别,如 V,D,I,W,E
        :param logcatFileName: 日志文件名
        """
        log_file = "%s/%s" % (saveDirPath, logcatFileName)
        # cmd = "adb logcat *:E -d | find \"%s\" > %s" % (app_pkg_name, log_file) # 会漏掉很多信息
        cmd = "%s %s logcat *:%s -d  > %s" % (self.adbPath, self._getDeviceIdOpt(deviceId), level.upper(), log_file)
        CommonUtil.exeCmd(cmd)
        # 提取tombstone信息
        with open(log_file, 'r') as f:
            while True:
                log = f.readline()
                if not log:
                    break
                if log.__contains__("Tombstone written to:"):
                    tmb = log.split(":")
                    tombstone_file = tmb[len(tmb) - 1].replace("\n", "").replace(" ", "")
                    self.pullTombstoneFile(tombstone_file, saveDirPath, deviceId)

    def pullANRFile(self, saveDirPath: str, deviceId: str = None) -> bool:
        """
        提取anr日志,由于位于 /data/anr/ ,无法直接pull,因此中转到 /sdcard/anr/ 下再 pull
        :param saveDirPath:  要提取到本机位置,如 d:/log/, 提取后实际目录为 d:/log/anr/
        :param deviceId:
        :return: true-成功 false-失败
        """
        print('pull_anr_files save_folder=%s' % saveDirPath)
        FileUtil.makeDir(saveDirPath)

        src_anr_folder = '/data/anr/'
        sdcard_path = '/sdcard/'
        move_to_file = '/sdcard/anr/'

        cmd_copy = ["su", "cp -r %s %s" % (src_anr_folder, sdcard_path)]
        cmd_delete = ["su", "rm -r %s/*" % src_anr_folder, "rm -r %s" % move_to_file]

        self.exeShellCmds(cmd_copy, deviceId)
        self.pull(move_to_file, saveDirPath, deviceId)
        self.exeShellCmds(cmd_delete, deviceId)

        # 检测本机是否存在anr目录,若存在表示提取成功
        local_anr_log_folder_path = FileUtil.recookPath('%s/anr/' % saveDirPath)
        if not os.path.exists(local_anr_log_folder_path):
            FileUtil.makeDir(local_anr_log_folder_path)
            print('pull_anr_files fail as dir not exit: %s' % local_anr_log_folder_path)
            return False
        anr_files = os.listdir(local_anr_log_folder_path)
        for name in anr_files:  # 添加后缀txt,方便查看
            if name.startswith('anr_') and not name.endswith(".txt"):
                log_file = '%s/%s' % (local_anr_log_folder_path, name)
                os.rename(log_file, '%s.txt' % log_file)
        # todo bugReport
        return True

    def pullTombstoneFile(self, saveDirPath: str, deviceId: str = None):
        """
        提取tombstone文件 srcPath 到本机目录save_folder中
        由于 adb pull 无法直接提取 /data/tombstone/*** 文件,因此采用如下操作:
        1. 复制 /data/tombstones/ 目录到 /sdcard/ 下
        2. pull 到本机 save_folder 目录下
        3. 删除 /sdcard/ 下的临时中转文件
        :param saveDirPath: 要保存在本机的目录路径, 如 D:/log/
        :return:
        """
        FileUtil.makeDir(saveDirPath)
        move_to_file = "/sdcard/tombstones"

        cmd_copy = ["su", "cp -r /data/tombstones /sdcard/"]
        cmd_delete = ["rm -rf %s" % move_to_file]

        self.exeShellCmds(cmd_copy, deviceId)
        self.pull(move_to_file, saveDirPath, deviceId)
        self.exeShellCmds(cmd_delete, deviceId)

    def deleteFromPhone(self, absPath: str, deviceId: str = None) -> str:
        """
        删除手机指定的文件/目录
        :param absPath: 待删除的文件路径(可以是目录)
        :param deviceId: 设备id,当前有多台设备连接时需要指定
        :return:
        """
        cmd = "%s %s shell rm -r %s" % (self.adbPath, self._getDeviceIdOpt(deviceId), absPath)
        return CommonUtil.exeCmd(cmd)

    def installApk(self, apkPath: str, deviceId: str = None, onlyForTest: bool = False) -> bool:
        """
        安装apk
        :param apkPath: apk文件路径, 若不存在,则返回False
        :param deviceId: 要安装的设备id
        :param onlyForTest: 是否需要加 -t 参数
        """
        if not FileUtil.isFileExist(apkPath):
            print('installApk apkPath 不存在,无需安装: %s' % apkPath)
            return False

        onlyForTestPara = "-t" if onlyForTest else ""
        print('start installApk...apkOnlyForTest=%s deviceId=%s,apkPath=%s' % (onlyForTest, deviceId, apkPath))
        runCmd = '%s %s install -r %s %s' % (self.adbPath, self._getDeviceIdOpt(deviceId), onlyForTestPara, apkPath)
        result = CommonUtil.exeCmd(runCmd)
        success = False
        if result is not None and 'Success' in result:
            success = True
        print('installApk %s 结果success=%s,result=%s' % (runCmd, success, result))
        return success
