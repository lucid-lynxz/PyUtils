# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

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
from util.FileUtil import FileUtil


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
                 splashActPath: str = '',
                 homeActPath: str = '',
                 deviceId: str = '',
                 forceRestart: bool = False,
                 appName: str = '',
                 totalSec: int = 180,
                 sleepSecBetweenProjects: int = 0,
                 cacheDir: str = ''):
        """
        :param pkgName: app包名
        :param splashActPath: app启动页面完整路径, 主要用于启动app
        :param homeActPath: app首页页面完整路径, 若splashActPath为空,则惠使用 homeActPath 替代
        :param deviceId: 要运行的设备序列号,目前支持android,若为空,则只有一台可用设备时可自动识别,若有多台,则adbUtil等工具类不会初始化
        :param forceRestart: 是否要强制重启app
        :param appName: app可读名称
        :param totalSec: 挂机时长, 单位: s, 默认180s
        :param sleepSecBetweenProjects: 执行下一个project前需要等待的时长, 单位: s
        :param cacheDir: 缓存目录路径,主要用于存储ocr截图和日志等
        """
        self.pkgName: str = pkgName  # app包名
        self.homeActPath: str = homeActPath
        self.splashActPath: str = homeActPath if CommonUtil.isNoneOrBlank(splashActPath) else splashActPath
        self.appName: str = appName
        self.forceRestart: bool = forceRestart  # 执行时是否要强制重启app

        self.cacheDir: str = cacheDir
        self.logName: str = ''
        self.updateCacheDir(cacheDir)

        # 自定义日志,参考: https://zhuanlan.zhihu.com/p/445411809
        self.logger = logging.getLogger("wool")
        self.logger.handlers = []  # 将当前文件的handlers 清空后再添加,否则可能会多次打印日志
        self.logger.setLevel(logging.INFO)
        # formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        # handler = logging.StreamHandler()
        # handler.setFormatter(formatter)
        # handler.setLevel(logging.INFO)
        # self.logger.addHandler(handler)
        self.fileLoggerHandler: logging.FileHandler = None

        # 设备相关配置
        self.deviceId: str = deviceId  # Android设备序列号
        self.adbUtil: AdbUtil = None  # AdbUtil(defaultDeviceId=deviceId)  # adb工具类
        self.model: str = None  # self.adbUtil.getDeviceInfo(self.deviceId).get('model', self.deviceId)  # 设备型号, 如: 小米6
        self.updateDeviceId(deviceId=deviceId)
        self.dim: int = -1  # 挂机时的屏幕亮度值, 非正数时表示不做调整
        self.dimOri: int = -1  # 设备初始的亮度

        self.next: AbsWoolProject = None  # 下一个需要执行的项目
        self.totalSec: int = totalSec
        self.sleepSecBetweenProjects: int = sleepSecBetweenProjects
        self.notificationRobotDict: dict = None  # 钉钉/飞书等推送信息配置

    def logInfo(self, msg, printCmdInfo: bool = True):
        if not printCmdInfo:
            return self
        try:
            self.logger.info('%s %s:%s,deviceId=%s' % (self.model, self.appName, msg, self.deviceId))
        except Exception as e:
            traceback.print_exc()
        finally:
            return self

    def logWarn(self, msg, printCmdInfo: bool = True):
        if not printCmdInfo:
            return self
        try:
            self.logger.warning('%s %s:%s,deviceId=%s' % (self.model, self.appName, msg, self.deviceId))
        except Exception as e:
            traceback.print_exc()
        finally:
            return self

    def logError(self, msg, printCmdInfo: bool = True):
        if not printCmdInfo:
            return self
        try:
            self.logger.error('%s %s:%s,deviceId=%s' % (self.model, self.appName, msg, self.deviceId))
        except Exception as e:
            traceback.print_exc()
        finally:
            return self

    def runAction(self, target_func, **kwargs):
        """
        执行某个操作, 忽略各种异常
        """
        try:
            target_func(**kwargs)
        except Exception as e:
            traceback.print_exc()
            model = self.adbUtil.getDeviceInfo(self.deviceId).get('model', self.deviceId)
            isAvailable = self.adbUtil.isAvailable(self.deviceId)
            msg = '%s %s %s isAvailable=%s 执行方法 %s 失败 %s' % (
                model, self.appName, self.deviceId, isAvailable, target_func.__name__, e)
            NetUtil.push_to_robot(msg, self.notificationRobotDict)
            self.logError(msg)
        finally:
            return self

    def updateCacheDir(self, cache: str):
        self.cacheDir = FileUtil.recookPath(cache)
        FileUtil.createFile('%s/' % cache)
        return self

    def setDefaultIme(self, ime: str):
        """切换当前使用的输入法"""
        if not CommonUtil.isNoneOrBlank(ime):
            self.adbUtil.exeShellCmds(['ime set %s' % ime], self.deviceId)
        return self

    def updateLogPath(self, logPath: str = None, logName: str = None):
        """
        更新日志文件存储信息
        :param logPath: 日志绝对路径,优先使用
        :param logName: 日志文件名, 会自动拼接得到: {self.cacheDir}/{logName}
        """
        if CommonUtil.isNoneOrBlank(logPath):
            if CommonUtil.isNoneOrBlank(logName) or CommonUtil.isNoneOrBlank(self.cacheDir):
                return self
            else:
                logPath = FileUtil.recookPath('%s/%s' % (self.cacheDir, logName))
        self.logName, _, _ = FileUtil.getFileName(logPath)
        if self.fileLoggerHandler is not None:
            self.logger.removeHandler(self.fileLoggerHandler)

        self.fileLoggerHandler = logging.FileHandler(filename=logPath, encoding='utf-8')
        formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        self.fileLoggerHandler.setFormatter(formatter)
        self.fileLoggerHandler.setLevel(logging.WARN)
        self.logger.addHandler(self.fileLoggerHandler)
        self.logError('updateLogPath....%s' % logPath)
        return self

    def setNext(self, woolProject):
        """设置下一个task,会自动使用当前设备id"""
        if isinstance(woolProject, AbsWoolProject) and CommonUtil.isNoneOrBlank(woolProject.deviceId):
            woolProject.updateDeviceId(deviceId=self.deviceId)
        self.next = woolProject
        return self

    def setNotificationRobotDict(self, robotSettings: dict):
        """
        设置消息推送配置信息
        """
        self.notificationRobotDict = robotSettings
        return self

    def startApp(self, homeActPath: str = None,
                 forceRestart: bool = False, msg: str = None):
        """
        启动app
        :param homeActPath:启动页名称,若为空,则会使用 self.splashActPath
        :param forceRestart:是否强制重启，若True，则会kill掉现有进程后再启动
        :param msg:描述为何进行强制重新启动
        """
        if CommonUtil.isNoneOrBlank(self.pkgName):
            return self

        if CommonUtil.isNoneOrBlank(homeActPath):
            homeActPath = self.splashActPath

        if forceRestart:
            self.logWarn(f'startApp by kill first {msg}')
            self.killApp()
        self.adbUtil.startApp(self.pkgName, homeActPath)
        return self

    def killApp(self):
        if not CommonUtil.isNoneOrBlank(self.pkgName):
            self.adbUtil.killApp(self.pkgName)
        return self

    def back2HomePage(self, funcDoAfterPressBack=None):
        """
        返回到首页
        :return: 返回自己 self
        """
        self.logWarn(f'back2HomePage start {self.homeActPath}')
        if CommonUtil.isNoneOrBlank(self.homeActPath):
            return self

        curAct: str = ''
        lastIndex: int = 0
        for index in range(10):
            lastIndex = index
            curAct = self.adbUtil.getCurrentActivity(self.deviceId)
            if CommonUtil.isNoneOrBlank(curAct):
                if index <= 5:
                    self.logWarn(f'貌似已退出app了, 尝试延迟等待后重试 index={index}')
                    self.sleep(1)
                    continue
                if index >= 8:
                    self.startApp(forceRestart=True, msg=f'貌似已退出app了, 尝试重新进行启动 index={index}')
                    self.sleep(5)
                curAct = self.adbUtil.getCurrentActivity(self.deviceId)
            if self.homeActPath == curAct:
                break
            self.adbUtil.back()
            self.sleep(1)
            if funcDoAfterPressBack is not None:
                funcDoAfterPressBack()
        self.logWarn(f'back2HomePage end index={lastIndex},curAct:{curAct}')
        return self

    def sleep(self, sec: float = -1, minSec: float = 1, maxSec: float = 8) -> float:
        """
        等待sec秒, 若sec小于0, 则在[minSec,maxSec)中随机挑一个数等待
        """
        return TimeUtil.sleep(sec, minSec, maxSec)

    def swipeDown(self, minX: int = 300, maxX: int = 500,
                  minY: int = 300, maxY: int = 1600,
                  minDeltaY: int = 0, maxDeltaY=0,
                  durationMs: int = 500,
                  keepVerticalSwipe: bool = False,
                  printCmdInfo: bool = False):
        self._swipeVertical(minX=minX, maxX=maxX, minY=minY, maxY=maxY, minDeltaY=minDeltaY, maxDeltaY=maxDeltaY,
                            durationMs=durationMs, keepVerticalSwipe=keepVerticalSwipe, reverse=True,
                            printCmdInfo=printCmdInfo)

    def swipeUp(self, minX: int = 300, maxX: int = 500,
                minY: int = 300, maxY: int = 1600,
                minDeltaY: int = 0, maxDeltaY=0,
                durationMs: int = 500,
                keepVerticalSwipe: bool = False,
                printCmdInfo: bool = False):
        self._swipeVertical(minX=minX, maxX=maxX, minY=minY, maxY=maxY, minDeltaY=minDeltaY, maxDeltaY=maxDeltaY,
                            durationMs=durationMs, keepVerticalSwipe=keepVerticalSwipe, reverse=False,
                            printCmdInfo=printCmdInfo)

    def _swipeVertical(self, minX: int = 300, maxX: int = 500,
                       minY: int = 300, maxY: int = 1600,
                       minDeltaY: int = 0, maxDeltaY=0,
                       durationMs: int = 500,
                       keepVerticalSwipe: bool = False,
                       reverse: bool = False,
                       printCmdInfo: bool = False):
        """
        上滑屏幕
        :param minX: 手指上滑起终点的x坐标范围
        :param maxX: 手指上滑起终点的x坐标范围
        :param minY: 手指上滑起终点的Y坐标范围
        :param maxY: 手指上滑起终点的Y坐标范围
        :param minDeltaY: Y方向至少需要滑动的距离最小距离,若<=0,则为屏幕高度的0.5
        :param maxDeltaY: Y方向可滑动的距离最大距离,若<=0,则为屏幕高度的0.8(不能太大,避免全面屏触发home操作)
        :param durationMs: 滑动耗时,单位:ms,默认500毫秒,可滚动页面会有惯性滑动效果, 若不想惯性滑动(如ocr截图场景),请设置大点
        :param keepVerticalSwipe: 竖直滑动, 即 toX == fromX
        :param reverse: 是否反方向滑动, True-向下滑 False-向上滑
        :param printCmdInfo: 是否打印执行的adb命令
        """
        infoDict = self.adbUtil.getDeviceInfo(self.deviceId)
        height = CommonUtil.convertStr2Float(infoDict['ov_height'], 1920)

        if minDeltaY <= 0:
            minDeltaY = int(height * 0.5)
        if maxDeltaY <= 0:
            maxDeltaY = int(height * 0.8)

        # 上滑切换到下一个页面
        dx = maxX - minX
        dy = maxY - minY
        x1 = round(random.random() * dx + minX)
        y1 = round(random.random() * dy + minY)

        x2 = round(random.random() * dx + minX)
        y2 = round(random.random() * dy + minY)

        curDeltaY = abs(y2 - y1)
        if curDeltaY < minDeltaY:
            y2 = y1 - minDeltaY
        elif curDeltaY > maxDeltaY:
            y2 = y1 - maxDeltaY

        if y2 < minY:
            delta = abs(y2 - y1)
            y2 = minY
            y1 = y2 + delta

        if y1 >= maxY:
            y1 = maxY

        if keepVerticalSwipe:
            x2 = x1

        if reverse:
            self.adbUtil.swipe(x2, y2, x1, y1, durationMs=durationMs, printCmdInfo=printCmdInfo)
        else:
            self.adbUtil.swipe(x1, y1, x2, y2, durationMs=durationMs, printCmdInfo=printCmdInfo)
        return self

    def swipeLeft(self, minX: int = 600, maxX: int = 800,
                  minY: int = 200, maxY: int = 600,
                  minDeltaX: int = 500,
                  minDeltaY: int = 100,
                  durationMs: int = 300,
                  printCmdInfo: bool = False):
        dx = maxX - minX
        dy = maxY - minY
        x1 = round(random.random() * dx + minX)
        y1 = round(random.random() * dy + minY)

        x2 = max(round(random.random() * 300 - 200), 10)
        y2 = round(random.random() * dx + minX)

        if abs(y2 - y1) < minDeltaY:
            y2 = y1 - minDeltaY

        if abs(x1 - x2) < minDeltaX:
            x2 = x1 - minDeltaX

        self.adbUtil.swipe(x1, y1, x2, y2, durationMs=durationMs, printCmdInfo=printCmdInfo)
        return self

    def swipeRight(self, minX: int = 50, maxX: int = 200,
                   minDeltaX: int = 500,
                   minDeltaY: int = 100,
                   durationMs: int = 300,
                   printCmdInfo: bool = False):
        dx = maxX - minX
        x1 = round(random.random() * dx + minX)
        y1 = round(random.random() * 100 + 900)

        x2 = max(round(random.random() * 300 + 600), 10)
        y2 = round(random.random() * dx + minX)

        if abs(y2 - y1) < minDeltaY:
            y2 = y1 - minDeltaY

        if abs(x1 - x2) < minDeltaX:
            x2 = x1 + minDeltaX
        self.adbUtil.swipe(x1, y1, x2, y2, durationMs=durationMs, printCmdInfo=printCmdInfo)
        return self

    # 多次尝试执行指定操作, func() 返回True时退出循环
    def forLoop(self, func, times: int = 3, sec: float = 3, **kwargs) -> bool:
        for index in range(times):
            if func(**kwargs):
                return True
            self.sleep(sec)
        return False

    def updateDeviceId(self, deviceId: str):
        """更新设备id,返回self,可以继续链式调用"""
        tAdbUtil: AdbUtil = AdbUtil(defaultDeviceId=deviceId)
        if CommonUtil.isNoneOrBlank(deviceId):
            deviceIds = tAdbUtil.getAllDeviceId(True)[0]
            if len(deviceIds) == 1:
                deviceId = deviceIds[0]
            else:
                self.logWarn('updateDeviceId fail as deviceId is empty but more than one devices available')
                return self

        self.deviceId = deviceId
        self.adbUtil = AdbUtil(defaultDeviceId=deviceId)
        self.model = self.adbUtil.getDeviceInfo(self.deviceId).get('model', self.deviceId)
        self.adbUtil.pointerLocation(1)  # 打开指针位置,方便调试
        self.adbUtil.exeShellCmds(['settings put system show_touches 1'], deviceId=deviceId)  # 显示点按位置
        return self

    def informationStreamPageAction(self, totalSec: float = -1, minSec: float = 4, maxSec: float = 10,
                                    maxRatio: float = 1.1, func=None):
        """
        信息流页面操作，比如视频流页面的不断刷视频，直到达到指定时长
        :param totalSec: 预期刷视频的总时长,单位: s, 若为非正数,则使用 self.totalSec 替代
        :param minSec: 每个视频停留观看的最短时长，单位：s
        :param maxSec: 每个视频停留观看的最长时长，单位：s
        :param maxRatio: 若始终无法跑够 totalSec 时长, 最多跑 totalSec * maxRatio 后必须退出
        :param func: 用于计算当前信息流页面是否需要挂机, func()的执行可能比较耗时,有可能会有页面跳转,因此minSec/maxSec可适当小点
        """
        totalSec = self.totalSec if totalSec <= 0 else totalSec
        self.logWarn(
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
            self.swipeUp()

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

    def get_earn_monkey_tab_name(self) -> tuple:
        """
        获取 去赚钱 页面的跳转按钮名称和目标页面的关键字(用于确认有跳转成功)
        """
        return '来赚钱', '(任务中心|抵用金|现金收益|开宝箱得金币|金币收益|赚钱任务|交友广场)'

    def get_home_tab_name(self) -> tuple:
        """
        获取 首页 信息流页面的跳转按钮名称和目标页面的关键字(用于确认有跳转成功)
        """
        return '首页', r'(^放映厅$|^同城$|^热榜TOP|^搜索：|^热搜：|^直播卖货|^抢首评|^社会榜TOP.*|作品原声|来一发弹幕)'

    # 跳转子tab页面,默认是 '去赚钱' 页面
    def goto_home_sub_tab(self, name: str = None, prefixText: str = None, targetPageKeyword: str = None,
                          sleepSecsInPage: int = 0, enableByRestartApp: bool = True) -> bool:
        """
        :param name:通过点击指定的文本按钮跳转,若为空,则默认点击 get_earn_monkey_tab_name() 按钮
        :param prefixText: name的前置文本
        :param targetPageKeyword: 跳转后的页面关键字检测,若不符合,则返回False
        :param sleepSecsInPage: 跳转后, 先等待指定时长再继续执行后续操作
        :param enableByRestartApp: 是否允许重启app后再做点击
        :return bool: 是否跳转成功
        """
        return False

    def run(self, **kwargs):
        try:
            running = True
            if not CommonUtil.isNoneOrBlank(self.pkgName):
                if not self.adbUtil.isPkgExist(pkgName=self.pkgName, deviceId=self.deviceId):
                    raise Exception(
                        f'{self.model} 未找到包名是 {self.pkgName} 的app,请确认是否已安装到设备: {self.deviceId}')

                random.seed()
                self.adbUtil.updateVolume(mute=True)  # 开启静音
                # self.adbUtil.updateDeviceSzie(1080, 1920)
                if self.dim > 0:
                    self.adbUtil.exeShellCmds(['settings put system screen_brightness_mode 0'])  # 关闭自动亮度
                    self.adbUtil.exeShellCmds(['settings put system screen_brightness %s' % self.dim])  # 降低屏幕亮度，减少耗电

                # 多次重复启动,用于去掉类似升级提示/签到提醒等弹框,通常都是一天弹出一次
                for index in range(3):
                    self.startApp(forceRestart=self.forceRestart, msg=f'开始挂机时,第{index}次强制重启')  # 启动app
                    self.sleep(minSec=6, maxSec=10)  # 等待启动完成
                    if self.forceRestart and index <= 1:
                        self.goto_home_sub_tab(sleepSecsInPage=10)

                    if not self.forceRestart:
                        break

                running: bool = self.adbUtil.isAppRunning(appPkgName=self.pkgName)
                self.logWarn(
                    'wool %s(%s) is running=%s,deviceId=%s' % (self.appName, self.pkgName, running, self.deviceId))
                if self.forceRestart:
                    # 每天首次启动可能会弹出青少年模式等弹框, 通过返回键进行取消
                    self.adbUtil.back()
                    self.sleep(minSec=5, maxSec=8)
                    self.adbUtil.back()
            if running:
                self.onRun(**kwargs)
        except Exception as e:
            traceback.print_exc()
            model = self.adbUtil.getDeviceInfo(self.deviceId).get('model', self.deviceId)
            NetUtil.push_to_robot('%s设备异常,退出%s挂机\nerrorDetail:%s' % (model, self.appName, e),
                                  self.notificationRobotDict)
            self.logError('run task exception: %s(%s) %s' % (self.appName, self.pkgName, e))

        self.onFinish()  # 执行完成

        # 测试完成后, kill调进程,并开始下一个task的执行
        self.killApp()
        self.logWarn('self.next=%s' % self.next)
        if isinstance(self.next, AbsWoolProject):
            self.sleep(self.sleepSecBetweenProjects)
            self.next.updateCacheDir(self.cacheDir).updateLogPath(logName=self.logName).updateDeviceId(
                self.deviceId).updateDim(self.dim, self.dimOri).setNotificationRobotDict(
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

    def onFinish(self, **kwargs):
        """ onRun 执行结束后触发"""
        self.adbUtil.exeShellCmds(['ime reset'], self.deviceId)
        pass


class WoolProjectImpl(AbsWoolProject):
    """AbsWoolProject的默认实现类, 不做扩展"""

    def onRun(self, **kwargs):
        self.informationStreamPageAction()
