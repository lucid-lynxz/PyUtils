# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import re
import subprocess

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil


class AdbUtil(object):
    def __init__(self, adbPath: str = 'adb', defaultDeviceId: str = None):
        """
        :param defaultDeviceId:默认的设备号，用于各方法未指定deviceId时，默认使用的值
        :param adbPath: adb应用程序的路径,若为空,则：
        1. 查看本工程是否已內置adb工具
        2. 若未內置，则使用环境变量中的adb(请自行确保系统已支持adb命令)
        """
        hit = False
        if not CommonUtil.isNoneOrBlank(adbPath):
            result = CommonUtil.exeCmd('%s version' % adbPath)
            if 'version' in result:
                hit = True
        self.adbPath = 'third_tools/android_platform_tools/*/adb.exe' if not hit else adbPath
        self.adbPath = CommonUtil.checkThirdToolPath(self.adbPath, 'adb')
        self.defaultDeviceId = defaultDeviceId

    def getAllDeviceId(self, onlineOnly: bool = False) -> tuple:
        """
        通过adb devices -l 命令获取所有设备id(未判断offline等特殊情况)
        :param onlineOnly: 是否只显示在线的设备(不包含 offline 和 unauthorized 的设备)
        :return: tuple(设备序列号列表,设备model名称列表)
        """
        device_ids_list = []
        device_names_list = []
        out = CommonUtil.exeCmd("%s devices -l" % self.adbPath, printCmdInfo=False)
        devices_info_list = "" if out is None else out.splitlines()
        for line in devices_info_list:
            if 'List of devices attached' in line:
                continue
            if 'device:' in line:
                if onlineOnly and ('offline' in line or 'unauthorized' in line):
                    continue
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
        :param deviceId:  设备号,若为空，则使用 adbUtil对象默认的 defaultDeviceId
        """
        deviceId = self.defaultDeviceId if CommonUtil.isNoneOrBlank(deviceId) else deviceId
        return '' if CommonUtil.isNoneOrBlank(deviceId) else '-s %s' % deviceId

    def exeShellCmds(self, cmdArr: list, deviceId: str = None, printCmdInfo: bool = False) -> tuple:
        """
        在 adb shell 中执行cmd列表命令
        :param cmdArr: 命令列表,如 ["su","ls","exit"], 会自动拼接成 adb -s deviceId shell ***
        :param deviceId: 若同时连接多台设备,则需要给出设备id
        :param printCmdInfo:执行命令时是否打印命令内容
        :return: tuple(stdout,stderr)
        """
        cmd_adb_shell = '%s %s shell' % (self.adbPath, self._getDeviceIdOpt(deviceId))
        ori_cmd = '%s %s' % (cmd_adb_shell, ' '.join(cmdArr))
        cmdArr.append('exit')
        pipe = subprocess.Popen(cmd_adb_shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        cmds_str = '\n'.join(cmdArr)
        cmds_str = '%s\n' % cmds_str
        if printCmdInfo:
            print('exeAdbCmd: %s' % ori_cmd)
        stdout, stderr = pipe.communicate(cmds_str.encode())
        stdout = None if stdout is None else stdout.decode().strip()
        stderr = None if stderr is None else stderr.decode().strip()
        result: str = stderr if CommonUtil.isNoneOrBlank(stdout) else stdout
        if printCmdInfo and not CommonUtil.isNoneOrBlank(result):
            print(result)
        return stdout, stderr

    def pull(self, src: str, dst: str = ".", deviceId: str = None, printCmdInfo: bool = True):
        """
        通过adb从手机中pull出特定文件到指定位置
        :param deviceId: 设备id,多台设备共存时需要指定
        :param src: 手机中源文件路径
        :param dst: 存储到本机的目录路径,若路径以 "/" 结尾,则提取源文件到该目录下,保持同名,请自行确保本机目录存在
        :param printCmdInfo:执行命令时是否打印命令内容
        :return: 本机存储文件路径,若pull失败,则返回 ""
        """
        path, src_file_name = os.path.split(src)

        if CommonUtil.isNoneOrBlank(dst):
            dst = "./"

        cmd = "%s %s pull %s %s" % (self.adbPath, self._getDeviceIdOpt(deviceId), src, dst)
        result = CommonUtil.exeCmd(cmd, printCmdInfo)
        if result is not None and "adb: error: " in result:
            return ""
        if dst.endswith("/"):
            dst = "%s/%s" % (dst, src_file_name)  # 本机文件路径
        return dst

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
                      deviceId: str = None,
                      printCmdInfo: bool = True):
        """
        抓取指定级别的日志,并存入 save_folder 中, 若有 tombstone 文件, 则尝试 pull
        :param saveDirPath: 日志文件保存目录
        :param level 日志级别,如 V,D,I,W,E
        :param logcatFileName: 日志文件名
        :param printCmdInfo:执行命令时是否打印命令内容
        """
        log_file = FileUtil.recookPath('%s/%s' % (saveDirPath, logcatFileName))
        # cmd = "adb logcat *:E -d | find \"%s\" > %s" % (app_pkg_name, log_file) # 会漏掉很多信息
        cmd = "%s %s logcat *:%s -d  > %s" % (self.adbPath, self._getDeviceIdOpt(deviceId), level.upper(), log_file)
        CommonUtil.exeCmd(cmd, printCmdInfo=printCmdInfo)
        # # 提取tombstone信息
        # try:
        #     with open(log_file, 'r', encoding='UTF8') as f:
        #         while True:
        #             log = f.readline()
        #             if not log:
        #                 break
        #             if log.__contains__("Tombstone written to:"):
        #                 tmb = log.split(":")
        #                 # tombstone_file = tmb[len(tmb) - 1].replace("\n", "").replace(" ", "")
        #                 self.pullTombstoneFile(saveDirPath, deviceId)
        # except Exception as e:
        #     print('getLogcatInfo try get tombstone info fail: %s' % e)
        return self

    def isFileExist(self, pathInPhone: str, deviceId: str = None) -> bool:
        """
        判断手机中的文件是否存在
        """
        if CommonUtil.isNoneOrBlank(pathInPhone):
            return False
        # '2>&1' 表示把标准错误 stderr 重定向到标准输出 stdout
        cmd = "%s %s shell ls %s 2>&1" % (self.adbPath, self._getDeviceIdOpt(deviceId), pathInPhone)
        result = CommonUtil.exeCmd(cmd, printCmdInfo=False)
        # print('isFileExist %s' % result)
        return not CommonUtil.isNoneOrBlank(result) and 'No such file or directory' not in result

    def getFileList(self, parentPathInPhone: str, regexFileName: str = None, deviceId: str = None) -> list:
        """
        获取满足条件的文件路径列表
        :param parentPathInPhone 目录绝对路径
        :param regexFileName: 正则表达式文件名, 若为空,则不作过滤,仅获取指定目录下的文件列表信息
        :param deviceId: 手机设备序列号
        """
        result = list()
        if not self.isFileExist(parentPathInPhone):
            return result

        cmd = "%s %s shell ls %s 2>&1" % (self.adbPath, self._getDeviceIdOpt(deviceId), parentPathInPhone)
        cmdResult = CommonUtil.exeCmd(cmd, printCmdInfo=False)

        if 'no devices/emulators found' in cmdResult:
            return result

        lines = cmdResult.splitlines()
        for line in lines:
            absPath = line
            if not line.startswith('/'):
                absPath = FileUtil.recookPath('%s/%s' % (parentPathInPhone, line))

            # if not self.isFileExist(absPath):
            #     continue

            fullName, _, _ = FileUtil.getFileName(absPath)
            if not CommonUtil.isNoneOrBlank(regexFileName):
                if re.search(r'%s' % regexFileName, fullName) is not None:
                    result.append(absPath)
            else:
                result.append(absPath)
        return result

    def pullANRFile(self, saveDirPath: str, deviceId: str = None, printCmdInfo: bool = True) -> bool:
        """
        提取anr日志,由于位于 /data/anr/ ,无法直接pull,因此中转到 /sdcard/anr/ 下再 pull
        :param saveDirPath:  要提取到本机位置,如 d:/log/, 提取后实际目录为 d:/log/anr/
        :param deviceId:设备序列号(通过 adb devices -l 获取)
        :param printCmdInfo:执行命令时是否打印命令内容
        :return: true-成功 false-失败
        """
        # print('pull_anr_files save_folder=%s' % saveDirPath)
        FileUtil.makeDir(saveDirPath)

        src_anr_folder = '/data/anr/'
        sdcard_path = '/sdcard/'
        move_to_file = '/sdcard/anr/'

        cmd_copy = ["su", "cp -r %s %s" % (src_anr_folder, sdcard_path)]
        cmd_delete = ["su", "rm -r %s*" % src_anr_folder, "rm -r %s" % move_to_file]

        self.exeShellCmds(cmd_copy, deviceId, printCmdInfo=printCmdInfo)
        self.pull(move_to_file, saveDirPath, deviceId, printCmdInfo=printCmdInfo)
        self.exeShellCmds(cmd_delete, deviceId, printCmdInfo=printCmdInfo)

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

    def pullTombstoneFile(self, saveDirPath: str, deviceId: str = None, printCmdInfo: bool = True):
        """
        提取tombstone文件 srcPath 到本机目录save_folder中
        由于 adb pull 无法直接提取 /data/tombstone/*** 文件,因此采用如下操作:
        1. 复制 /data/tombstones/ 目录到 /sdcard/ 下
        2. pull 到本机 save_folder 目录下
        3. 删除 /sdcard/ 下的临时中转文件
        :param saveDirPath: 要保存在本机的目录路径, 如 D:/log/
        :param printCmdInfo:执行命令时是否打印命令内容
        :return:
        """
        FileUtil.makeDir(saveDirPath)
        move_to_file = "/sdcard/tombstones"

        cmd_copy = ["su", "cp -r /data/tombstones /sdcard/"]
        cmd_delete = ["rm -rf %s" % move_to_file]

        self.exeShellCmds(cmd_copy, deviceId, printCmdInfo=printCmdInfo)
        self.pull(move_to_file, saveDirPath, deviceId, printCmdInfo=printCmdInfo)
        self.exeShellCmds(cmd_delete, deviceId, printCmdInfo=printCmdInfo)
        return self

    def deleteFromPhone(self, absPath: str, deviceId: str = None) -> str:
        """
        删除手机指定的文件/目录
        :param absPath: 待删除的文件路径(可以是目录)
        :param deviceId: 设备id,当前有多台设备连接时需要指定
        :return:
        """
        if self.isFileExist(absPath, deviceId):
            cmd = "%s %s shell rm -r %s" % (self.adbPath, self._getDeviceIdOpt(deviceId), absPath)
            return CommonUtil.exeCmd(cmd, printCmdInfo=False)
        else:
            return '文件不存在 %s' % absPath

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

    def getImeiInfo(self, targetDeviceId: str = None) -> list:
        """
        获取本机连接的手机设备imei列表,要求手机已root,需要执行 su 命令
        :param targetDeviceId: 要获取imei的手机序列号, 若为空,则获取所有手机的序列号
        :return: list 元素类型是str
        """
        if CommonUtil.isNoneOrBlank(targetDeviceId):
            deviceIdList, _ = self.getAllDeviceId()
        else:
            deviceIdList = [targetDeviceId]

        resultList = list()
        for did in deviceIdList:
            cmd = ["su", "service call iphonesubinfo 1"]
            out, err = self.exeShellCmds(cmd, did)
            lines = out.splitlines()
            device_imei_list = []
            for line in lines:
                if isinstance(line, bytes):
                    line = bytes.decode(line)
                if "Result: Parcel" in line:
                    continue
                if "'" in line:
                    splits = line.split("'")
                    device_imei_list.append(splits[-2])
            if len(device_imei_list) > 0:
                imei = "".join(device_imei_list).replace(".", "")
                resultList.append(imei.strip())
        return resultList

    def getMacAddress(self, targetDeviceId: str = None) -> list:
        """
        获取设备的网卡地址,要求手机已root,需要执行 su 命令
        :param targetDeviceId: 要获取imei的手机序列号, 若为空,则获取所有手机的序列号
        :return: list 元素类型是str
        """
        if CommonUtil.isNoneOrBlank(targetDeviceId):
            deviceIdList, _ = self.getAllDeviceId()
        else:
            deviceIdList = [targetDeviceId]

        resultList = list()
        for did in deviceIdList:
            cmd = ["su", "cat /sys/class/net/wlan0/address"]
            out, err = self.exeShellCmds(cmd, did)
            if isinstance(out, bytes):
                out = bytes.decode(out)
            resultList.append(out.strip())
        return resultList

    def getCurrentActivity(self, deviceId: str = None) -> str:
        """
        获取当前activity信息, 命令：adb shell dumpsys window | grep mCurrentFocus
        得到结果如：mCurrentFocus=Window{bcb5ed0 u0 org.lynxz.demo/org.lynxz.demo.activity.HomeActivity}
        :return: activity路径信息，如：org.lynxz.demo.activity.HomeActivity
        """
        out, err = self.exeShellCmds(['dumpsys window | grep mCurrentFocus'], deviceId)
        if CommonUtil.isNoneOrBlank(out):
            return ''
        tArr = out.split('{')
        if tArr is not None and len(tArr) >= 2:
            arr = tArr[1].replace('}', '').split(' ')
            pkgName, actPath = arr[len(arr) - 1].split('/')
            if actPath.startswith('.'):
                actPath = '%s.%s' % (pkgName, actPath)
            return actPath.strip()
        return ''

    def startApp(self, appPkgName: str, activityPath: str, deviceId: str = None):
        """
        启动app指定activity
        可通过 adb shell dumpsys window | grep mCurrentFocus 查看到当前activity信息
        :param appPkgName:包名，如： org.lynxz.demo
        :param activityPath: 主activity完整路径，如： org.lynxz.demo.activity.mainActivity
        """
        self.exeShellCmds(['am start %s/%s' % (appPkgName, activityPath)], deviceId)
        return self

    def killApp(self, appPkgName, deviceId: str = None):
        """
        kill掉指定的app进程
        """
        if CommonUtil.isNoneOrBlank(appPkgName):
            return self
        self.exeShellCmds(['am force-stop %s' % appPkgName], deviceId)
        return self

    def isAppRunning(self, appPkgName: str, deviceId: str = None) -> bool:
        """
        判断手机中指定app进程是否存在
        :param appPkgName: 包名
        :param deviceId: 设备号
        :return: bool
        """
        # 命令中不能使用windows cmd不支持的命令, 如: grep
        # 运行结果格式示例:
        # u0_a457      25439   736 4002152 118904 0                   0 S org.lynxz.test
        try:
            cmd = ['ps | grep %s' % appPkgName]
            msg, stderr = self.exeShellCmds(cmd, deviceId)
            if CommonUtil.isNoneOrBlank(msg):
                return False
            for line in msg.splitlines():
                if appPkgName == line.split()[-1]:
                    return True
            return False
        except Exception as e:
            print('checkAppRunning exception: %s' % e)
            return False

    def getAllPkgs(self, opt: str = None, deviceId: str = None, printCmdInfo: bool = False) -> list:
        """
        获取手机上的所有app包名列表
        使用的命令: adb shell pm list packages [-3/-s]
        :param opt: 参数,默认为None表示获取所有包
                    3: 表示金获取三方包
                    s: 表示仅获取系统包
        """
        extOpt = '' if CommonUtil.isNoneOrBlank(opt) else '-%s' % opt
        out, _ = self.exeShellCmds(['pm list packages %s' % extOpt], deviceId, printCmdInfo)
        result = list()
        if CommonUtil.isNoneOrBlank(out):
            return result

        for line in out.splitlines():
            l: str = line.strip()
            if ':' in l:
                arr = l.split(':')
                size = len(arr)
                if size >= 2:
                    result.append(arr[1])
        return result

    def isPkgExist(self, pkgName: str, deviceId: str = None, printCmdInfo: bool = False) -> bool:
        """
        手机上是有安装有指定的包
        :param pkgName: 目标app包名
        """
        if CommonUtil.isNoneOrBlank(pkgName):
            return False
        return pkgName in self.getAllPkgs(deviceId=deviceId, printCmdInfo=printCmdInfo)

    def tapByTuple(self, posTuple: tuple, deviceId: str = None):
        self.tap(posTuple[0], posTuple[1], deviceId)
        return self

    def tap(self, x: int, y: int, deviceId: str = None, printCmdInfo: bool = False):
        """
        点击设备的指定位置
        :param x: 点击坐标x，屏幕左上角为0
        :param y: 点击坐标y，屏幕左上角为0
        """
        self.exeShellCmds(['input tap %s %s' % (x, y)], deviceId, printCmdInfo)
        return self

    def swipe(self, from_x: int, from_y: int, to_x: int, to_y: int,
              durationMs: int = 500, deviceId: str = None,
              printCmdInfo: bool = False):
        """
        在手机屏幕上滑动
        :param from_x: 起始点击坐标x，屏幕左上角为0
        :param from_y: 起始点击坐标y，屏幕左上角为0
        :param durationMs: 滑动时长, 单位:ms
        """
        self.exeShellCmds(['input swipe %s %s %s %s %s' % (from_x, from_y, to_x, to_y, durationMs)], deviceId,
                          printCmdInfo)
        return self

    def back(self, times: int = 1):
        """
        按下返回键
        :param times: 返回次数，默认是一次
        """
        for index in range(1, 1 + times):
            self.exeShellCmds(['input keyevent BACK'])
        return self

    def power(self, deviceId: str = None):
        # 按下power键
        self.exeShellCmds(['input keyevent 26'], deviceId)
        return self

    def updateVolume(self, up: bool = True, mute: bool = False, deviceId: str = None):
        """
        音量调节
        这个是系统根据当前应用判断调节的是哪个音量，比如媒体、通话等
        :param up: 是否调大音量
        :param mute: 是否静音
        """
        event = 164 if mute else 24 if up else 25
        self.exeShellCmds(['input keyevent %s' % event], deviceId)
        return self

    def updateDeviceSzie(self, width: int, height: int, deviceId: str = None, printCmdInfo: bool = False):
        """
        修改设备分辨率
        ：param width: 宽度
        ：param height: 高度
        """
        self.exeShellCmds(['wm size %sx%s' % (width, height)], deviceId, printCmdInfo)
        return self

    def getDeviceInfo(self, deviceId: str = None) -> dict:
        """
        获取设备的其他信息,当前支持的key如下：
        imei:设备imei,高版本可能无法获取到
        mac:设备mac地址
        android_id: androidId字符串，重置手机后会变
        model:机型，如：pixel 5
        android_version:系统版本， 如: 12， 表示 android 12
        api_version:系统api版本， 如: 32
        size: 设备的原始物理尺寸像素，如：1080x2340
        width: 设备宽度像素， 如： 1080
        height： 设备长度像素，如： 2340
        override_size: 设备通过adb修改后的像素，如：1080x1920,若未修改过，则等同于上方的size
        ov_width: 设备当前宽度像素， 如： 1080， 若未修改过，则等同于上方的 width
        ov_height： 设备当前长度像素，如： 1920，若未修改过，则等同于上方的 height
        """
        result = dict()
        result['imei'] = self.getImeiInfo(deviceId)
        result['mac'] = self.getMacAddress(deviceId)
        result['android_id'], _ = self.exeShellCmds(['settings get secure android_id'], deviceId)
        result['model'], _ = self.exeShellCmds(['getprop ro.product.model'], deviceId)
        result['android_version'], _ = self.exeShellCmds(['getprop ro.build.version.release'], deviceId)
        result['api_version'], _ = self.exeShellCmds(['getprop ro.build.version.sdk'], deviceId)

        # 获取屏幕物理尺寸，结果示例:
        # Physical size: 1080x2340
        # Override size: 1080x1920
        out, err = self.exeShellCmds(['wm size'], deviceId)
        if ':' in out:
            for line in out.splitlines():
                if 'Physical size:' in line:
                    size = line.split(':')[1]
                    result['size'] = size  # 如： 1080x2340
                    result['width'], result['height'] = size.split('x')

                    result['override_size'] = size  # 如： 1080x2340
                    result['ov_width'], result['ov_height'] = result['width'], result['height']
                elif 'Override size:' in line:
                    size = line.split(':')[1]
                    result['override_size'] = size  # 如： 1080x2340
                    result['ov_width'], result['ov_height'] = size.split('x')
        return result


if __name__ == '__main__':
    adbUtil = AdbUtil()
    # print(adbUtil.getImeiInfo())
    # print(adbUtil.getMacAddress())

    # import pprint
    #
    # pprint.PrettyPrinter(indent=2)
    # pprint.pprint(adbUtil.getDeviceInfo())
    adbUtil.back()
