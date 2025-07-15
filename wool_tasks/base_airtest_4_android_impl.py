# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys

from util.NetUtil import NetUtil

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from abc import ABCMeta
import re

__author__ = "Lynxz"

from typing import Union
from airtest.core.api import *
from base.TaskManager import TaskManager, TaskLifeCycle
from util.CommonUtil import CommonUtil
from WoolProject import AbsAndroidWoolProject
from util.decorator import log_wrap
from base_airtest import BaseAir

"""
android子类按需重写 check_info_stream_valid(self) 方法  
"""
auto_setup(__file__)


class AbsBaseAir4Android(BaseAir, AbsAndroidWoolProject):
    __metaclass__ = ABCMeta

    def __init__(self, deviceId: str, pkgName: str = '',
                 splashActPath: str = '',
                 homeActPath: str = '',
                 appName: str = '',
                 totalSec: int = 180,
                 minInfoStreamSec: int = 180,
                 forceRestart: bool = False,
                 cacheDir: str = None):

        BaseAir.__init__(self, 'android', deviceId, cacheDir=cacheDir)
        AbsAndroidWoolProject.__init__(self, pkgName=pkgName,
                                       splashActPath=splashActPath,
                                       homeActPath=homeActPath,
                                       appName=appName,
                                       deviceId=deviceId,
                                       totalSec=totalSec,
                                       minInfoStreamSec=minInfoStreamSec,
                                       forceRestart=forceRestart, cacheDir=cacheDir)

    def kan_zhibo_in_page(self, count: int = 1,  # 总共需要看几次直播
                          max_sec: int = 60,  # 每个直播最多需要观看的时长
                          zhiboHomePageTitle: str = r'^看直播领金.',  # 直播列表首页的标题名,用于判断是否跳转到直播详情成功
                          autoBack2Home: bool = True):
        pass

    @log_wrap(print_out_obj=False, print_caller=True)
    def continue_watch_ad_videos(self, max_secs: int = 90,  # 最多要观看的时长, 之后会通过检测 '已领取' / '已成功领取奖励' 来决定是否继续观看
                                 min_secs: int = 10,
                                 maxVideos: int = 5,
                                 breakIfHitText: str = None):
        """
        当前已在广告视频页面, 会最多观看 secs 秒后, 按下返回键
        若弹出继续浏览的弹框, 则继续浏览,最终回到前一页
        :param max_secs: 每个广告视频观看的最大时长,单位:s, 会自动比 min_secs 多20s
        :param min_secs: 每个广告视频观看的最小时长,单位:s
        :param maxVideos: 最多观看多少个广告视频, >=1, 其他值会统一替代为20, 一般也只会让你连续看3个广告视频左右
        :param breakIfHitText: 若看完一个视频进行back操作后, 识别到存在指定的文本,则退出后续的视频观看,表明已不在视频页面了
        """
        pass

    # 可能会弹出获得金币弹框, 点击关闭按钮, 耗时比较久, 建议是想检测特定文本后按需触发
    @log_wrap(print_caller=True)
    def closeDialog(self, extraImg: str = None, autoClick: bool = True,
                    minX: int = 200, minY: int = 200, maxX: int = 0, maxY: int = 0) -> tuple:
        """
        搜索并点击关闭弹框
        :param extraImg: 其他自定义的关闭按钮图片相对路径,会优先匹配该图片
        :param autoClick: 匹配到关闭按钮后是否直接点击
        :param minX:匹配到的按钮必须满足的指定的区间才认为合法
        :param maxX:匹配到的按钮必须满足的指定的区间才认为合法
        :param minY:匹配到的按钮必须满足的指定的区间才认为合法
        :param maxY:匹配到的按钮必须满足的指定的区间才认为合法
        :return tuple:(float,float) 表示匹配到的按钮坐标值, 若为空,则表示未匹配到
        """
        pass

    @log_wrap(exclude_arg={'self', 'cnocr_result'})
    def get_rest_chance_count(self, title: str,
                              subTitle: str,
                              cnocr_result: list = None,
                              appendStrFlag: str = '') -> tuple:
        """
        要求当前已在赚钱任务页面
        比如搜索/看直播等活动,每天有限额,通过本方法根据 subTitle 信息获取剩余可用次数
        1. 优先进行ocr单行匹配
        2. 对完整的ocr结果进行匹配

        :param title: 标题行
        :param subTitle: 正则表达式要求至少包含一个 '(\\d+/\\d+)' 表示已完成次数和总次数
        :param cnocr_result: 若已有ocr识别结果,则直接服用,否则重新ocr
        :param appendStrFlag: 根据ocr结果列表拼接生成完整字符串时,连续两个文本之间的连接符号,默认为一个空格
        :return tuple: (int,int)  completeCount, totalCount 依次表示已使用的次数, 总次数
        """
        completeCount: int = 0
        totalCount: int = 0
        if cnocr_result is None:
            pos, ocrStr, ocrResultList = self.findTextByOCR(subTitle, prefixText=title,
                                                            swipeOverlayHeight=300,
                                                            height=1400, appendStrFlag=appendStrFlag)
        else:
            pos, ocrStr, ocrResultDict = self.findTextByCnOCRResult(cnocr_result, targetText=subTitle,
                                                                    prefixText=title, appendStrFlag=appendStrFlag)
            if not CommonUtil.isNoneOrBlank(ocrResultDict):
                subTitleText = ocrResultDict.get('text', '')
                ocrStr = ocrStr if CommonUtil.isNoneOrBlank(subTitleText) else subTitleText

        if CommonUtil.isNoneOrBlank(ocrStr):
            return completeCount, totalCount

        pattern = re.compile(subTitle)  # 如果已搜索过,还有剩余搜索机会的话,此时可能没有 '去搜索' 按钮, 而是倒计时按钮
        resultList = pattern.findall(ocrStr)
        if CommonUtil.isNoneOrBlank(resultList):
            return completeCount, totalCount
        else:
            chancesInfo = resultList[0]
            if '/' in chancesInfo:
                arr = chancesInfo.split('/')
                if len(arr) >= 2:
                    completeCount = CommonUtil.convertStr2Int(arr[0], 0)
                    totalCount = CommonUtil.convertStr2Int(arr[1], 0)
        self.logWarn(f'已完成:{chancesInfo},complete={completeCount},total={totalCount},ocrStr={ocrStr}')
        return completeCount, totalCount

    def search_by_input(self, keyword: str, hintListKeyword: str = r'搜索有奖',
                        viewSec: int = 20, ignoreCase: bool = True) -> bool:
        """
        要求当前已在搜索页面,且光标已定位到搜索输入框
        则会自动输入部分keyword,并尝试匹配:
         1. '搜索有奖'
         2. 入参的 'keyword' 完整内容
         3. 比输入的部分keyword更长的提示项
         返回是否输入搜索成功
         :param keyword: 完整的搜索关键字
         :param hintListKeyword: 输入keyword后可能会弹出提示列表,点选带有 hintListKeyword 的item
         :param viewSec: 若搜索成功,则浏览搜索结果的时长,单位:s, 大于0有效,浏览完成后仍在当前页面
         :param ignoreCase: 是否忽略大小写
         :return bool:是否搜索成功
        """
        # 由于使用 yosemite 等输入直接键入文本时,获得金币约等于无,此处尝试只输入一半内容,然后通过下拉提示列表进行点击触发关键字输入
        length = len(keyword)
        inputKWIndex: int = length if length <= 8 else int(length / 2)
        inputKW: str = keyword[0:inputKWIndex]  # 实际输入的关键字内容
        self.logWarn(f'尝试输入搜索关键字: {inputKW}  完整的关键字为:{keyword}')
        self.text(inputKW, search=False)  # 输入关键字,进行搜索
        self.sleep(2)

        pos, ocrStr, ocrResList = self.findTextByOCR(targetText=inputKW, subfixText=r'搜索',
                                                     height=800, maxSwipeRetryCount=1)
        if CommonUtil.isNoneOrBlank(pos):
            img_path = self.saveScreenShot(f'search_by_input_fail_input_fail')
            self.logWarn(f'search_by_input fail 未输入成功,kw={inputKW},img_path={img_path}')
            return False

        # 检测下拉提示列表
        success: bool = False
        for checkIndex in range(3):
            pos, ocrStr, ocrResList = self.findTextByOCR(hintListKeyword, prefixText=inputKW,
                                                         height=800, maxSwipeRetryCount=1)
            success = self.tapByTuple(self.calcCenterPos(pos))
            self.logWarn(f'search_by_input 尝试匹配搜索有奖提示语 success={success},ocrStr={ocrStr}')
            if not success:  # 未找到 '搜索有奖' 时,表明对关键字无要求,直接点击比输入值更长的文本即可
                pos, ocrStr, _ = self.findTextByCnOCRResult(ocrResList, keyword, prefixText='搜索')
                success = self.tapByTuple(self.calcCenterPos(pos))
                if not success:
                    pos, ocrStr, _ = self.findTextByCnOCRResult(ocrResList, r'%s.+' % inputKW, prefixText=inputKW)
                    pos = self.calcCenterPos(pos)
                    self.logWarn(f'search_by_input 查找比输入更长的提示语 pos={pos}')
                    success = self.tapByTuple(pos)
                    if not success:
                        pos, ocrStr, _ = self.findTextByCnOCRResult(ocrResList, r'搜索')
                        pos = self.calcCenterPos(pos)
                        self.logWarn(f'search_by_input fail 直接点击 "搜索" 按钮: pos={pos}')
                        success = self.tapByTuple(pos)

                if self.findTextByCnOCRResult(cnocr_result=ocrResList, targetText=r'浏览\d+秒可得搜索金币'):
                    success = True

            if not success:
                self.logWarn(f'search input kw fail wait 3s:{inputKW}')
                self.sleep(3)
            else:
                self.logWarn(f'search input kw success:{inputKW}, ocrStr={ocrStr}')
                break

        # 浏览指定的时长
        if success and viewSec > 0:
            totalSec: float = 0
            while True:
                self.sleep(4)
                self.swipeUp(durationMs=1000)
                totalSec = totalSec + 5
                if totalSec > viewSec:
                    break
        return success

    @log_wrap(print_out_obj=False, print_caller=True)
    def updateDeviceId(self, deviceId: str):
        if self.adbUtil is None:
            AbsAndroidWoolProject.updateDeviceId(self, deviceId)

        if not CommonUtil.isNoneOrBlank(
                self.deviceId) and self.deviceId == deviceId and self.airtest_device is not None:
            return self

        AbsAndroidWoolProject.updateDeviceId(self, deviceId)
        # super().updateDeviceId(deviceId)
        connect_device("Android:///%s?cap_method=javacap&touch_method=adb" % self.deviceId)
        wake()  # 唤醒设备
        set_current(self.deviceId)
        self.airtest_device = G.DEVICE
        # for dev in G.DEVICE_LIST:
        #     if self.deviceId == dev.serialno:
        #         self.airtest_device = dev
        #         break
        self.init_poco()
        return self

    def getWH(self) -> tuple:
        """
        获取当前设备的宽高
        """
        # 经测试, pixel2xl 耗时1.6s左右,因此做下缓存, 一般挂机时不做横竖屏切换
        height = self.getStateValue('height', 0)
        width = self.getStateValue('width', 0)
        if height > 0 and width > 0:
            return width, height

        if self.airtest_device.display_info['orientation'] in [1, 3]:  # 横屏
            height = self.airtest_device.display_info['width']
            width = self.airtest_device.display_info['height']
        else:
            height = self.airtest_device.display_info['height']
            width = self.airtest_device.display_info['width']
        self.updateStateKV('height', height)
        self.updateStateKV('width', width)
        return width, height

    @log_wrap(print_caller=True, exclude_arg=['self', 'ocrResList'])
    def check_if_in_page(self, targetText: str, prefixText: str = None, ocrResList=None, height: int = 0,
                         maxRetryCount: int = 1, autoCheckDialog: bool = True, minOcrLen: int = 20) -> bool:
        """
        检测当前是否在指定的页面
        :param targetText:页面上必须存在的信息,正则表达式,若为空,则直接返回True
        :param prefixText: 特定信息前面必须存在的字符串,支持正则
        :param ocrResList: cnocr识别结果,若为空,则会进行一次ocr识别
        :param height: 若需要进行截图ocr,则ocr的高度是多少
        :param maxRetryCount: 识别重试次数, 若当前识别失败,则下一轮必然重新ocr
        :param autoCheckDialog: 是否自动检测弹框,默认True
        :param minOcrLen: 要求ocr得到的文本总长度不能小于该值,否则认为识别失败
        :return bool: 是否在目标页面
        """
        if CommonUtil.isNoneOrBlank(targetText):
            return True
        for index in range(maxRetryCount):
            if ocrResList is None:  # 重新ocr
                pos, ocrResStr, ocrResList = self.findTextByOCR(targetText, height=height, prefixText=prefixText,
                                                                maxSwipeRetryCount=1)
            else:  # 复用原先的ocr结果
                pos, ocrResStr, _ = self.findTextByCnOCRResult(ocrResList, targetText=targetText, prefixText=prefixText)

            if not CommonUtil.isNoneOrBlank(pos):  # 找到目标文本
                return True

            if maxRetryCount <= 1:  # 只允许匹配一次,则直接返回
                return False

            # 检测文本长度
            if CommonUtil.isNoneOrBlank(ocrResStr) or len(ocrResStr) <= minOcrLen:
                self.logWarn(f'check_if_in_page fail ocrResStr is too short,wait:ocrResStr={ocrResStr}')
                ocrResList = None
                self.sleep(2)
                continue

            img_path = self.saveScreenShot(f'未找到_{targetText}_{prefixText}_{index}')
            self.logWarn(
                f'check_if_in_page 未找到:{targetText}, index={index},prefixText={prefixText},'
                f'img_path={img_path}\nocrResStr={ocrResStr}')
            if autoCheckDialog:
                ocrResList = self.check_dialog(breakIfHitText=targetText)  # 可能是有弹框覆盖, 此处不做弹框检测,避免死循环
            else:
                self.sleep(2)  # 可能是未加载完成,等待2s再试
                ocrResList = None  # 置空,下一轮强制重新ocr
        return False

    def tapByTuple(self, posTuple: tuple, deviceId: str = None, times: int = 1, sleepSec: float = 1,
                   printCmdInfo: bool = False) -> bool:
        return self.adbUtil.tapByTuple(posTuple, deviceId=deviceId, times=times, sleepSec=sleepSec,
                                       printCmdInfo=printCmdInfo)

    def init_poco(self):
        """若有需要使用到poco,请启用本方法进行初始化"""
        # if self.poco is None:
        #     self.poco = AndroidUiautomationPoco(device=self.airtest_device,
        #                                         use_airtest_input=True,
        #                                         screenshot_each_action=False)
        return self

    def onRun(self, **kwargs):
        self.runAction(self.informationStreamPageAction, totalSec=self.totalSec, func=self.check_info_stream_valid)

    def canDoOthersWhenInStream(self) -> bool:
        """
        当前正在刷信息流页面时,是否允许跳转到其他页面执行刷金币操作
        在信息流页面每刷一页就会重新计算一次
        """
        minStreamSec: int = self.getStateValue(AbsBaseAir4Android.key_minStreamSecs, 0)  # 最短间隔时长,单位:s
        inStramSec: int = self.getStateValue(AbsBaseAir4Android.key_in_stram_sec, 0)  # 已连续刷信息流的时长,单位:s
        lastStreamTs: float = self.getStateValue(AbsBaseAir4Android.key_lastStreamTs, 0)  # 上次跳转的时间戳, 单位:s
        curTs: float = time.time()
        if inStramSec >= minStreamSec:
            self.logWarn(
                f'canDoOthersWhenInStream true minStreamSec={minStreamSec},inStramSec={inStramSec}'
                f',lastStreamTs={lastStreamTs},curTs={curTs}')
            return True
        else:
            return False

    def check_info_stream_valid(self, forceRecheck: bool = False) -> tuple:
        """
        当前在信息流页面,检测是否可执行赚钱任务,默认是每5min可跳转赚钱任务一次
        :return tuple: (bool,bool)
                        第一个元素表示当前时候仍在信息流页面
                        第二个元素表示是否有跳转执行赚钱任务
        """
        performEarnActions: bool = self.canDoOthersWhenInStream()
        if performEarnActions:
            self.perform_earn_tab_actions()
            self.back_until_info_stream_page()  # 返回首页
            forceRecheck = True  # 可能跳转新页面了,需要重新检测
        return self.check_if_in_info_stream_page(forceRecheck=forceRecheck), performEarnActions

    @log_wrap(print_out_obj=False)
    def perform_earn_tab_actions(self, tag: Union[str, list] = 'earn_page_action', maxSwipeCount: int = 8,
                                 back2HomeStramTab: bool = False, filterFuncNames: set = None):
        """
        跳转到去赚钱页面,然后执行各任务
        :param tag: 需要自行的任务task tag, 可只传入一个,或者list
        :param maxSwipeCount: 在赚钱任务页面最多下滑次数
        :param back2HomeStramTab: 执行完毕后是否回退到首页信息流页面
        :param filterFuncNames: 若非空,则只执行包含的方法
        """
        self.goto_home_earn_tab()
        if not self.check_if_in_earn_page():
            self.logWarn(f'perform_earn_tab_actions fail as not in earn page')
            return self

        earnName, earnKeyword = self.get_earn_monkey_tab_name()
        earnFuncList = list()
        if isinstance(tag, str):
            earnFuncList = TaskManager.getTaskList(tag, taskLifeCycle=TaskLifeCycle.custom)
        elif isinstance(tag, list):
            for tTag in tag:
                tEarnFuncList = TaskManager.getTaskList(tTag, taskLifeCycle=TaskLifeCycle.custom)
                if not CommonUtil.isNoneOrBlank(tEarnFuncList):
                    earnFuncList = earnFuncList + tEarnFuncList

        ocrResList = self.getScreenOcrResult()
        for _ in range(maxSwipeCount):
            for item in earnFuncList:
                funcName: str = item.__name__
                if not CommonUtil.isNoneOrBlank(filterFuncNames) and funcName not in filterFuncNames:
                    continue

                self.logWarn(f'perform_earn_tab_actions action: {funcName},ocrStr={self.composeOcrStr(ocrResList)}')
                consumed = item(baseAir=self, ocrResList=ocrResList, breakIfHitText=earnKeyword)
                if consumed:
                    self.logWarn(f'perform_earn_tab_actions consumed: {funcName}')
                    if not self.check_if_in_earn_page(autoCheckDialog=True):
                        if self.check_if_in_info_stream_page():
                            self.goto_home_earn_tab()
                        else:
                            self.back_until_info_stream_page()
                            self.goto_home_earn_tab()

                        if not self.check_if_in_earn_page(autoCheckDialog=True):
                            self.logWarn(f'当前已不在赚钱页面,退出继续执行赚钱任务')
                            break
                        self.sleep(2)  # 页面信息可能变化, 等待一会再ocr
                        ocrResList = self.getScreenOcrResult()
            self.back_until_earn_page(ocrResList=ocrResList)  # 返回到赚钱页面
            self.swipeUp(minDeltaY=1000, maxDeltaY=1000, keepVerticalSwipe=True, durationMs=1500)  # 下滑一页
            self.check_dialog(breakIfHitText=earnKeyword)  # 检测可能的弹框
            # self.closeDialog(minY=500)  # 可能有一些新型弹框未添加识别, 此处统一尝试进行关闭
            ocrResList = self.getScreenOcrResult()

        self.back_until_earn_page()  # 执行完成,返回到赚钱页面
        if back2HomeStramTab:
            self.back_until_info_stream_page()  # 返回信息流页面
        return self

    def common_log_info(self) -> str:
        if self.airtest_device is None:
            return ''
        serialNo = self.airtest_device.serialno
        if self.deviceId != serialNo:
            NetUtil.push_to_robot(f'当前设备号与air dev序列号不符,serialNo={serialNo},deviceId={self.deviceId}',
                                  self.notificationRobotDict)
        return ''


if __name__ == '__main__':
    air = AbsBaseAir4Android(deviceId='5d4ea2a7')
    # targetText: str = r'\d{2}:\d{2}:\d{2}.再开.次'
    # targetText: str = r'立即开宝箱'
    # prefixText: str = r'(已开启|已开后|再开\d+次|必得全部奖励)'
    targetText: str = r'(看视频最高得\d+金.|看.告视频再.\d+金.|看.{0.6}直播.{0,6}赚\d+金.)'
    prefixText: str = r'(宝箱|恭.*得|明日签到|签到成功|本轮宝箱已开启|已开启|已开后|再开\d+次|必得全部奖励)'
    pos1, ocr_str, _ = air.findTextByOCR(targetText=targetText, prefixText=prefixText,
                                         maxSwipeRetryCount=1, saveDirPath='H:/wool_cache/')
    print('ocr_str=%s' % ocr_str)
    print('pos=%s' % pos1)
    cx, cy = air.calcCenterPos(pos1)
    print('cx,cy=%s,%s' % (cx, cy))
    air.adbUtil.tap(cx, cy)
