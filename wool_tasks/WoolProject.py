# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from abc import ABC, abstractmethod, ABCMeta
import random
import time
import logging
import traceback
from base.Interfaces import Runnable
from util.AdbUtil import AdbUtil
from util.TimeUtil import TimeUtil
from util.CommonUtil import CommonUtil
from util.NetUtil import NetUtil

logger = logging.getLogger("airtest")
logger.setLevel(logging.WARN)


class AbsWoolProject(ABC, Runnable):
    __metaclass__ = ABCMeta

    """
    封装了基类实用方法:
    1. updateDeviceId(str) 更新实用的设备号
    2. startApp(bool) 启动/重启指定的app
    3. back2HomePage() 返回首页
    4. setNext(AbsWoolProject) 设置下一个wool工程,当前工程执行完成后自动在本机执行下一个工程
    5. sleep(int) 等待指定时长,单位:s
    6. swipeNext() 滑动到下一屏
    7. forLoop(fun,int,float) 执行指定操作N次,每次间隔x秒 
    8. informationStreamPageAction() 
    各方法若无明确指定返回值类型,则表示返回的是self, 可以继续链式调用
    """

    def __init__(self, pkgName: str = '',
                 homeActPath: str = '',
                 deviceId: str = '',
                 forceRestart: bool = False,
                 appName: str = '',
                 totalSec: int = 180):
        """
        :param pkgName: app包名
        :param homeActPath: app入口页面完整路径
        :param deviceId: 要运行的设备序列号,目前支持android
        :param forceRestart: 是否要强制重启app
        :param appName: app可读名称
        :param totalSec: 挂机时长, 单位: s, 默认180s
        """
        self.pkgName: str = pkgName  # app包名
        self.homeActPath: str = homeActPath  # app入口activity完整路径
        self.deviceId: str = deviceId  # Android设备序列号
        self.forceRestart: bool = forceRestart  # 执行时是否要强制重启app
        self.appName: str = appName
        self.adbUtil: AdbUtil = AdbUtil(defaultDeviceId=deviceId)  # adb工具类
        self.notificationRobotDict: dict = None  # 钉钉/飞书等推送信息配置
        self.dim: int = -1  # 挂机时的屏幕亮度值, 非正数时表示不做调整
        self.dimOri: int = -1  # 设备初始的亮度
        self.next: AbsWoolProject = None  # 下一个需要执行的项目
        self.totalSec: int = totalSec

    def setNext(self, woolProject):
        """设置下一个task,会自动使用当前设备id"""
        if isinstance(woolProject, AbsWoolProject) and CommonUtil.isNoneOrBlank(woolProject.deviceId):
            woolProject.updateDeviceId(deviceId=self.deviceId)
        self.next = woolProject
        return self

    def setnotificationRobotDict(self, robotSettings: dict):
        """
        设置消息推送配置信息
        """
        self.notificationRobotDict = robotSettings
        return self

    def startApp(self, forceRestart: bool = False):
        """
        启动app
        :param forceRestart:是否强制重启，若True，则会kill掉现有进程后再启动
        """
        if CommonUtil.isNoneOrBlank(self.pkgName):
            return self
        if forceRestart:
            self.adbUtil.killApp(self.pkgName)
        self.adbUtil.startApp(self.pkgName, self.homeActPath)
        return self

    def back2HomePage(self):
        """
        返回到首页
        :return: 返回自己 self
        """
        if CommonUtil.isNoneOrBlank(self.homeActPath):
            return self
        for index in range(1, 20):
            curAct = self.adbUtil.getCurrentActivity()
            if CommonUtil.isNoneOrBlank(curAct):
                print('貌似退出app了, 重新进行启动 %s %s' % (self.deviceId, self.appName))
                self.startApp()
                curAct = self.adbUtil.getCurrentActivity()

            if self.homeActPath == curAct:
                break
            self.adbUtil.back()
            self.sleep(1)
        return self

    def sleep(self, sec: float = -1, minSec: float = 1, maxSec: float = 8) -> float:
        """
        等待sec秒, 若sec小于等于0, 则在[minSec,maxSec)中随机挑一个数等待
        """
        return TimeUtil.sleep(sec, minSec, maxSec)

    def swipeNext(self, minX: int = 100, maxX: int = 700, minDeltaY: int = 500):
        # 上滑切换到下一个页面
        dx = maxX - minX
        x1 = round(random.random() * dx + minX)
        y1 = round(random.random() * 100 + 1000)

        x2 = round(random.random() * dx + minX)
        y2 = max(round(random.random() * 300 - 210), 10)

        if abs(y2 - y1) < minDeltaY:
            y2 = y1 - minDeltaY

        self.adbUtil.swipe(x1, y1, x2, y2, printCmdInfo=True)
        return self

    def swipeLeft(self, minX: int = 600, maxX: int = 800, minDeltaY: int = 100):
        dx = maxX - minX
        x1 = round(random.random() * dx + minX)
        y1 = round(random.random() * 100 + 900)

        x2 = max(round(random.random() * 300 - 200), 10)
        y2 = round(random.random() * dx + minX)

        if abs(y2 - y1) < minDeltaY:
            y2 = y1 - minDeltaY
        self.adbUtil.swipe(x1, y1, x2, y2, printCmdInfo=True)
        return self

    def swipeRight(self, minX: int = 50, maxX: int = 200, minDeltaY: int = 100):
        dx = maxX - minX
        x1 = round(random.random() * dx + minX)
        y1 = round(random.random() * 100 + 900)

        x2 = max(round(random.random() * 300 + 600), 10)
        y2 = round(random.random() * dx + minX)

        if abs(y2 - y1) < minDeltaY:
            y2 = y1 - minDeltaY
        self.adbUtil.swipe(x1, y1, x2, y2, printCmdInfo=True)
        return self

    # 多次尝试执行指定操作, func() 返回True时退出循环
    def forLoop(self, func, times: int = 3, sec: float = 3, **kwargs) -> bool:
        for index in range(1, times + 1):
            if func(**kwargs):
                return True
            self.sleep(sec)
        return False

    def updateDeviceId(self, deviceId: str):
        """更新设备id,返回self,可以继续链式调用"""
        self.deviceId = deviceId
        self.adbUtil = AdbUtil(defaultDeviceId=deviceId)
        return self

    def informationStreamPageAction(self, totalSec: float = -1, minSec: float = 3, maxSec: float = 6,
                                    maxRatio: float = 1.1, func=None):
        """
        信息流页面操作，比如视频流页面的不断刷视频，直到达到指定时长
        :param totalSec: 预期刷视频的总时长,单位: s, 若为非正数,则使用 self.totalSec 替代
        :param minSec: 每个视频停留观看的最短时长，单位：s
        :param maxSec: 每个视频停留观看的最长时长，单位：s
        :param maxRatio: 若始终无法跑够 totalSec 时长, 最多跑 totalSec * maxRatio 后必须退出
        :param func: 用于计算当前信息流页面是否需要挂机
        """
        totalSec = self.totalSec if totalSec <= 0 else totalSec
        print(
            'informationStreamPageAction totalSec=%s,deviceId=%s,appName=%s' % (totalSec, self.deviceId, self.appName))

        valid_duration = 0  # 有效的信息流耗时
        ts_start = time.time()
        max_total_sec = totalSec * maxRatio  # 最多运行1.5倍时长,超时后退出
        while True:
            if func is None or func():  # 当前视频页面有效(有奖励),可以进行挂机
                sec = self.sleep(minSec=minSec, maxSec=maxSec)  # 等待，模拟正在观看视频
                valid_duration = valid_duration + sec  # 挂机的有效总耗时

            # 计算总耗时，若超过max_total_sec，则强制退出
            total_duration = time.time() - ts_start  # 总耗时

            if valid_duration >= totalSec or total_duration >= max_total_sec:
                break

            # 视频观看结束后，上滑切换到下一个视频
            self.swipeNext()

    def updateDim(self, dim: float, dimOri: float = -1):
        """
        更新挂机的屏幕亮度,正数有效
        :param dim: 挂机时要设置的屏幕亮度, 正数有效
        :param dimOri: 设备原始屏幕亮度,用于会在结束挂机时恢复,正数有效(其他值时会尝试获取当前设备值)
        """
        if dim > 0:
            self.dim = int(round(dim))

        if dimOri > 0:
            self.dimOri = int(round(dimOri))
        elif not CommonUtil.isNoneOrBlank(self.deviceId):  # 获取当前屏幕亮度
            out, _ = self.adbUtil.exeShellCmds(['settings get system screen_brightness'], deviceId=self.deviceId)
            self.dimOri = -1 if CommonUtil.isNoneOrBlank(out) else int(out)
        return self

    def run(self, **kwargs):
        try:
            running = True
            if not CommonUtil.isNoneOrBlank(self.pkgName):
                if not self.adbUtil.isPkgExist(pkgName=self.pkgName, deviceId=self.deviceId):
                    raise Exception('未找到包名是 %s 的app,请确认是否已安装到设备:%s' % (self.pkgName, self.deviceId))

                random.seed()
                self.adbUtil.updateVolume(mute=True)  # 开启静音
                # self.adbUtil.updateDeviceSzie(1080, 1920)
                if self.dim > 0:
                    self.adbUtil.exeShellCmds(['settings put system screen_brightness_mode 0'])  # 关闭自动亮度
                    self.adbUtil.exeShellCmds(['settings put system screen_brightness %s' % self.dim])  # 降低屏幕亮度，减少耗电

                self.startApp(forceRestart=self.forceRestart)  # 启动app
                self.sleep(3)  # 等待启动完成
                running: bool = self.adbUtil.isAppRunning(appPkgName=self.pkgName)
                print('wool %s(%s) is running=%s,deviceId=%s' % (self.appName, self.pkgName, running, self.deviceId))
                if self.forceRestart:
                    # 每天首次启动可能会弹出青少年模式等弹框, 通过返回键进行取消
                    self.adbUtil.back()
                    self.sleep(3)
                    self.adbUtil.back()
            if running:
                self.onRun(**kwargs)
        except Exception as e:
            traceback.print_exc()
            print('run task exception: %s(%s) %s' % (self.appName, self.pkgName, e))
            model = self.adbUtil.getDeviceInfo(self.deviceId).get('model', self.deviceId)
            NetUtil.push_to_robot('%s设备异常,退出%s挂机\nerrorDetail:%s' % (model, self.appName, e),
                                  self.notificationRobotDict)

        # 测试完成后, kill调进程,并开始下一个task的执行
        self.adbUtil.killApp(appPkgName=self.pkgName, deviceId=self.deviceId)
        print('self.next=%s' % self.next)
        if isinstance(self.next, AbsWoolProject):
            self.next.updateDeviceId(self.deviceId).updateDim(self.dim, self.dimOri).setnotificationRobotDict(
                self.notificationRobotDict).run()
        else:
            if self.dimOri > 0:
                self.adbUtil.exeShellCmds(['settings put system screen_brightness_mode 1'])  # 开启自动亮度
                self.adbUtil.exeShellCmds(['settings put system screen_brightness %s' % self.dimOri])  # 恢复原屏幕亮度
            self.adbUtil.power(deviceId=self.deviceId)  # 关闭手机屏幕

    def convert2RelPos(self, x: int, y: int, digits: int = 3) -> tuple:
        """
        将本机绝对坐标转为相对坐标
        如本机宽高为:1080*1920
        则将(x,y)=(300,500)转为相对坐标得到: (300/1080,500/1920)=(0.27,0.26)
        :param x:x轴绝对坐标
        :param y:y轴绝对坐标
        :param digits:保留的小数位数
        """
        infoDict = self.adbUtil.getDeviceInfo(self.deviceId)
        width = infoDict['ov_width']
        height = infoDict['ov_height']
        return round(x / width, digits), round(y / height, digits)

    def convert2AbsPos(self, x: float, y: float) -> tuple:
        """
        将本机相对坐标转为绝对坐标
        如本机宽高为:1080*1920
        则将(x,y)=(0.27,0.26)转为相对坐标得到: (0.27*1080,0.26*1920)=(291,499)
        :param x:x轴相对坐标 [0,1]
        :param y:y轴相对坐标 [0,1]
        :return (int,int)
        """
        infoDict = self.adbUtil.getDeviceInfo(self.deviceId)
        width = infoDict['ov_width']
        height = infoDict['ov_height']
        return round(x / width), round(y / height)

    @abstractmethod
    def onRun(self, **kwargs):
        """子类实现具体的逻辑,默认可直接调用 informationStreamPageAction() """
        pass


class WoolProjectImpl(AbsWoolProject):
    """AbsWoolProject的默认实现类, 不做扩展"""

    def onRun(self, **kwargs):
        self.informationStreamPageAction()
