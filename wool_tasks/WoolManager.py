# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys
import time

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

import threading
import typing
from base.BaseConfig import BaseConfig
from wool_tasks.ksjsb.main import KsAir
from wool_tasks.dyjsb.main import DyAir
from wool_tasks.dragon_read.dragon_read import DragonRead
from wool_tasks.WoolProject import AbsWoolProject, WoolProjectImpl
from util.AdbUtil import AdbUtil
from util.CommonUtil import CommonUtil
from util.TimeUtil import TimeUtil
from util.NetUtil import NetUtil
from util.FileUtil import FileUtil
from util.log_handler import LogHandlerSetting


class WoolThread(threading.Thread):
    def __init__(self, woolProject: AbsWoolProject):
        threading.Thread.__init__(self, name=woolProject.appName)
        self.woolProject = woolProject

    def run(self) -> None:
        print('设备 %s 测试开始,当前线程:%s' % (self.woolProject.deviceId, self.name))
        self.woolProject.run()
        print('设备 %s 测试完成,退出当前线程:%s' % (self.woolProject.deviceId, self.name))


class WoolManager(BaseConfig):

    def _getDeviceList(self, deviceIds: str) -> list:
        """
        获取可用的设备列表
        """
        result = []
        adbUtil = AdbUtil()
        if CommonUtil.isNoneOrBlank(deviceIds):
            device_ids_list, _ = adbUtil.getAllDeviceId(onlineOnly=True)
            return device_ids_list
        arr = deviceIds.split(',')
        for item in arr:
            if adbUtil.isAvailable(item):
                adbUtil.screenOff(off=False, deviceId=item)
                result.append(item.strip())
        return result

    def onRun(self):
        settingDict = self.configParser.getSectionItems('setting')
        appInfoDict = self.configParser.getSectionItems('app_info')
        robotSection = self.configParser.getSectionItems('robot')

        # 获取设备亮度
        dim = int(settingDict.get('dim', '-1'))

        # 获取设备列表
        deviceIds = settingDict.get('deviceIds', '')
        deviceList = self._getDeviceList(deviceIds=deviceIds)
        if CommonUtil.isNoneOrBlank(deviceList):
            NetUtil.push_to_robot(f'可用设备列表为空,退出挂机,请检查 {self}', robotSection)
            return

        # 挂机完成后是否休眠本机电脑
        sleepPcAfterAll = settingDict.get('sleepPcAfterAll', 'False') == 'True'
        forceRestartApp = settingDict.get('forceRestartApp', 'False') == 'True'
        sleepSec = settingDict.get('sleepSec', 0)
        performEarnActionDuration = int(settingDict.get('performEarnActionDuration', 5 * 60))

        cacheDir = settingDict.get('cacheDir', '')  # 缓存目录路径
        clearCache = settingDict.get('clearCache', 'False') == 'True'
        FileUtil.createFile('%s/' % cacheDir, clearCache)  # 按需创建缓存目录

        pidInfoFile = f'{cacheDir}/processInfo.txt'
        FileUtil.createFile(pidInfoFile)  # 创建当前进程信息
        FileUtil.write2File(pidInfoFile, f'{os.getpid()}')

        LogHandlerSetting.save_log_dir_path = cacheDir

        start = time.time()
        threadList = []
        adbUtil = AdbUtil()
        for deviceId in deviceList:
            connected = adbUtil.isAvailable(deviceId)
            print('device:%s is connected=%s' % (deviceId, connected))
            if connected:
                # 格式: 包名={app名称},{刷信息流的最短时长,单位:s},{挂机最短总时长,单位:s},{首页路径,可放空}
                # 获取待挂机的app信息,并拼接最终task
                if forceRestartApp:
                    adbUtil.killApp(None, deviceId=deviceId)  # 关闭所有程序
                project: typing.Optional[AbsWoolProject] = None
                for pkgName, value in appInfoDict.items():
                    pkgName = pkgName.split('__more__')[0]
                    arr = [] if CommonUtil.isNoneOrBlank(value) else value.split(',')
                    size = len(arr)
                    appName = arr[0] if size >= 1 else ''  # app名称
                    minInfoStreamSec = int(arr[1]) if size >= 2 else 180  # 默认至少需要刷信息流3min
                    totalSec = int(arr[2]) if size >= 3 else 180  # 默认总挂机时长至少3min
                    homeActPath = arr[3] if size >= 4 else ''  # app首页路径
                    print(f'appName={appName}, minInfoStreamSec={minInfoStreamSec},totalSec={totalSec}')

                    if KsAir.PKG_NAME == pkgName:
                        ksjsb = KsAir(deviceId=deviceId,
                                      totalSec=totalSec,
                                      minInfoStreamSec=minInfoStreamSec,
                                      forceRestart=forceRestartApp)
                        project = ksjsb if project is None else project.setNext(ksjsb)
                    elif DyAir.PKG_NAME == pkgName:
                        dyjsb = DyAir(deviceId=deviceId, totalSec=totalSec,
                                      minInfoStreamSec=minInfoStreamSec,
                                      forceRestart=forceRestartApp)
                        project = dyjsb if project is None else project.setNext(dyjsb)
                    elif DragonRead.PKG_NAME == pkgName:
                        dragonRead = DragonRead(deviceId=deviceId, totalSec=totalSec, minInfoStreamSec=minInfoStreamSec,
                                                forceRestart=forceRestartApp)
                        project = dragonRead if project is None else project.setNext(dragonRead)
                    else:
                        simpleProject = WoolProjectImpl(deviceId=deviceId, pkgName=pkgName, homeActPath=homeActPath,
                                                        forceRestart=forceRestartApp, minInfoStreamSec=minInfoStreamSec,
                                                        appName=appName, totalSec=totalSec)
                        project = simpleProject if project is None else project.setNext(simpleProject)

                t = WoolThread(project.updateCacheDir(cacheDir)
                               .updateDim(dim)
                               .updateStateKV(AbsWoolProject.key_minStreamSecs, performEarnActionDuration)
                               .setNotificationRobotDict(robotSection)
                               .setDefaultIme(settingDict.get('ime', ''))
                               )
                t.start()
                threadList.append(t)

        # 发送开始挂机通知
        # 检查当前笔记本电量,依赖 psutil 库
        pc_info = 'unknown'
        try:
            import psutil
            battery = psutil.sensors_battery()
            pc_info = '电量%s%%,%s' % (battery.percent, '已接通电源' if battery.power_plugged else '未接通电源')
        except:
            print("can't import psutil, please run 'pip install psutil' to install")

        NetUtil.push_to_robot('开始挂机\n本机信息:%s\n设备列表:%s' % (
            pc_info, [adbUtil.getDeviceInfo(x).get('model', x) for x in deviceList]), robotSection)

        # 等待所有子线程执行完毕
        for t in threadList:
            t.join()

        duration = time.time() - start
        secs_duration = TimeUtil.convertSecsDuration(duration)
        print('测试完成, 耗时: %s ,duration=%s' % (secs_duration, duration))

        # 电脑是否需要休眠
        willSleepPcAfter = CommonUtil.isWindows() and sleepPcAfterAll

        # 发送通知到钉钉/飞书
        sleepTip = '\n若想取消休眠,请在5min内终止程序' if willSleepPcAfter else ''
        NetUtil.push_to_robot(
            '完成挂机\n耗时:%s\n总秒数:%s\n电脑休眠:%s%s' % (secs_duration, int(duration), willSleepPcAfter, sleepTip),
            robotSection)

        deviceList = self._getDeviceList(deviceIds=deviceIds)
        if not CommonUtil.isNoneOrBlank(deviceList):
            for deviceId in deviceList:
                adbUtil.killApp(None, deviceId=deviceId, printCmdInfo=True)  # 关闭所有三方app
                adbUtil.screenOff(deviceId=deviceId)  # 关闭手机屏幕

        # 电脑进行休眠省电
        if willSleepPcAfter:
            print('5分钟后电脑即将休眠,若不想休眠请及时终止程序')
            TimeUtil.sleep(5 * 60)
            CommonUtil.exeCmd('rundll32.exe powrprof.dll,SetSuspendState Sleep')


if __name__ == '__main__':
    # 默认使用当前目录下的 config.ini 文件路径
    curDirPath = os.path.abspath(os.path.dirname(__file__))
    configPath = '%s/config.ini' % curDirPath

    # 触发更新
    WoolManager(configPath, optFirst=True).run()
