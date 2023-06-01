# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

import re
from airtest.core.api import *
from wool_tasks.base_airtest_bd_jsb import BDJsbBaseAir
from util.CommonUtil import CommonUtil

auto_setup(__file__)


class DyAir(BDJsbBaseAir):
    PKG_NAME = 'com.ss.android.ugc.aweme.lite'

    def __init__(self, deviceId: str, forceRestart: bool = True, totalSec: int = 180):
        super().__init__(deviceId=deviceId, pkgName=DyAir.PKG_NAME,
                         splashActPath='com.ss.android.ugc.aweme.splash.SplashActivity',
                         homeActPath='com.ss.android.ugc.aweme.splash.SplashActivity',
                         appName='抖音极速版',
                         totalSec=totalSec,
                         forceRestart=forceRestart)
        using(os.path.dirname(__file__))
        self.updateStateKV('searchDuration', 5 * 60)  # 搜索间隔

    def initStateDict(self):
        super().initStateDict()

    def check_info_stream_valid(self, forceRecheck: bool = False) -> bool:
        if self.canDoOthersWhenInStream():
            self.guangjie()  # 逛街赚金币
            self.watch_ad_video(minDurationSec=5 * 60)
            forceRecheck = True
        return super().check_info_stream_valid(forceRecheck=forceRecheck)

    # @log_wrap
    def onRun(self, **kwargs):
        super().onRun(**kwargs)
        self.runAction(self.search, count=10).runAction(self.qiandao) \
            .runAction(self.kan_xiaoshuo).runAction(self.watch_ad_video)

    def guangjie(self, btnText: str = r'去逛街',  # 按钮名称,用于跳转到逛街页面
                 title: str = r'^逛街赚钱',  # 逛街item的标题
                 subTitle: str = r'(\d{1,2}/\d{1,2})次$',  # 逛街item的子标题,用于获取可完成次数
                 minSecEachTime: int = 100,  # 每次浏览的时长,页面要求90s左右,增加加载时长等因素,留10%左右的冗余量
                 minDurationSec: int = 10 * 60,  # 连续两次逛街之间的时间间隔,单位: s
                 back2Home: bool = True  # 是否需要自动返回首页
                 ):
        """
        '来赚钱' -> '逛街赚钱' 每天可以做10次
        """
        key = 'guangjie_ts'
        key_rest_count = 'guangjie_rest_count'
        rest_count: int = self.getStateValue(key_rest_count, 10)
        lastTs = self.getStateValue(key, 0)
        curTs = time.time()
        if curTs - lastTs < minDurationSec and rest_count > 0:
            return

        self.logWarn('去逛街赚钱 start')
        self.goto_home_sub_tab()  # 跳转到 '来赚钱' 页面
        pos, ocrStr, ocrResList = self.findTextByOCR(targetText=btnText, prefixText=title,
                                                     swipeOverlayHeight=300, height=1300, appendStrFlag='')
        # 检测当前是否有金币奖励
        pattern = re.compile(r'(\d{2}):(\d{2})后浏览')
        result = pattern.findall(ocrStr)
        if not CommonUtil.isNoneOrBlank(result):
            self.logWarn(f'当前逛街浏览商品暂无金币奖励,下次再试 {result}')
            if back2Home:
                self.back2HomePage()
            return

        # 检测要浏览的时长
        pattern = re.compile(r'浏览.*商品(\d+)秒.*')
        result = pattern.findall(ocrStr)
        if CommonUtil.isNoneOrBlank(result):
            self.logWarn(f'当前逛街浏览商品暂无金币奖励,下次再试 {result}')
            if back2Home:
                self.back2HomePage()
            return
        else:
            secs = max(int(result[0]), 60)
            minSecEachTime = max(int(secs * 1.1), minSecEachTime)
            self.logWarn(f'可浏览低价商品获得金币,本次至少需要浏览 {secs} 秒, 最终设定 {minSecEachTime}')

        # 点击'去逛街' 跳转商品浏览页面
        completeCount, totalCount = self.get_rest_chance_count(title=title, subTitle=subTitle, cnocr_result=ocrResList)
        if totalCount > 0:
            self.logWarn(f'逛街赚金币,今日已完成{completeCount}/{totalCount}')
            self.updateStateKV(key_rest_count, totalCount - completeCount)

        if completeCount >= totalCount > 0:
            self.logWarn(f'今日逛街赚金币活动均已完成,无需再试')
            if back2Home:
                self.back2HomePage()
            return

        # 点击 '去逛街' 按钮,跳转到商品浏览界面
        success = self.tapByTuple(self.calcCenterPos(pos))
        if not success:
            self.logWarn(f'去逛街赚钱 失败, 未找到按钮,已完成次数:{completeCount}/{totalCount}')
            return

        self.sleep(5)
        pos, ocrStr, _ = self.findTextByOCR(r'浏览\d+秒可领\d+金.', height=1000, maxSwipeRetryCount=1)
        if CommonUtil.isNoneOrBlank(pos):
            self.logWarn(f'guangjie 失败,页面上未找到 浏览xxx秒可领xxx金币 信息:{ocrStr}')
            if back2Home:
                self.back2HomePage()
            return

        self.updateStateKV(key, curTs)
        totalSec: float = 0  # 本次已浏览的时长,单位: s
        maxTotalSec: float = minSecEachTime * 1.5
        startTs: float = time.time()
        while True:
            sec = self.sleep(minSec=2, maxSec=5)
            totalSec = totalSec + sec
            self.swipeUp()  # 上滑
            beyondMaxSecs: bool = time.time() - startTs >= maxTotalSec
            if totalSec > minSecEachTime or beyondMaxSecs:
                self.adbUtil.back()  # 浏览时长足够后, 返回上一页
                # 可能返回失败
                pos, _, ocrResList = self.findTextByOCR(targetText=r'(^继续完成$|^继续观看$)', prefixText='坚持退出',
                                                        maxSwipeRetryCount=1, fromY=300)
                if beyondMaxSecs:  # 已超过最大时长
                    pos, _, _ = self.findTextByCnOCRResult(cnocr_result=ocrResList, targetText='坚持退出',
                                                           prefixText=r'(^继续完成$|^继续观看$)')
                    if self.tapByTuple(self.calcCenterPos(pos)):  # 坚持退出
                        break
                else:
                    success = self.tapByTuple(self.calcCenterPos(pos))
                    if success:  # 尚未完成浏览任务, 额外浏览10s
                        totalSec = totalSec - 10
                    else:
                        break
        #  通过不断按下返回键, 自动返回视频页面,正常3次就够了
        if back2Home:
            self.back2HomePage()
        if totalCount > 0:
            self.updateStateKV(key_rest_count, totalCount - completeCount - 1)
        self.logWarn(f'逛街赚钱 end {completeCount + 1}/{totalCount},')

    def search(self, count: int = 6, minDurationSec: int = -1,
               titlePattern: str = r'^搜索(.*?)赚金.',
               subTilePattern: str = r'搜索.*浏览.*已.*完成(\d{1,2}/\d{1,2})',
               btnText: str = '去搜索'):
        # 预设的搜索关键字
        keyword_arr = ['云韵', '美杜莎', '焰灵姬', '绯羽怨姬',
                       'flutter', 'android binder', 'jetpack compose',
                       'espresso', 'aidl', 'arouter', 'transformer']

        # 跳转去搜索页面
        for i in range(3):
            pos = self.exists(Template(r"tpl1683642143406.png", record_pos=(0.44, -0.894), resolution=(1080, 2340)))
            if pos:
                self.touch(pos)
                break
            self.sleep(1)
            if i >= 2:  # 尝试3次都未找到搜索按钮,则退出
                return

        # 确定搜索词, dy要求每次搜索词都不同,可搜索10次
        for i in range(count):
            index = i % len(keyword_arr)
            keyword = keyword_arr[index]
            self.search_by_input(keyword, viewSec=20)

            # 顶部搜索栏的 清空按钮
            hit = False
            for j in range(3):
                pos = self.exists(
                    Template(r"tpl1683642926933.png", record_pos=(0.294, -0.898), resolution=(1080, 2340)))
                if pos:
                    self.touch(pos)  # 清空,光标自动定位到输入框
                    hit = True
                self.sleep(1)

            if not hit:  # 未找到清空按钮,则直接通过坐标定位到输入框
                # 1080x2340 手机的顶部搜索框中心位置为: 500,200
                # 得到相对位置为: 500/1080=0.4629   185/2340=0.0791
                self.logWarn('未找到搜索框的清空按钮, 直接通过坐标定位到搜索框 %s' % self.appName)
                self.tapByTuple(self.convert2AbsPos(0.4629, 0.0791))  # 定位到搜索框, 重新进行下一次输入
            self.sleep(1)

        # 搜索完成, 退出搜索页面,返回首页
        self.adbUtil.back()
        self.sleep(1)
        self.adbUtil.back()

    def qiandao(self, title: str = r'^签到', subTitle: str = r'^已连续签到\d+天', btnText: str = '^签到$'):
        """
        dy: '来攒钱' -> 日常任务 '签到'
        """
        key_can_do = 'qiandao_state'
        canDo = self.getStateValue(key_can_do, True)
        if not canDo:
            return self

        self.goto_home_sub_tab()
        pos, _, _ = self.findTextByOCR(targetText=btnText, prefixText=title, swipeOverlayHeight=300, height=1000)
        if self.tapByTuple(self.calcCenterPos(pos)):
            self.check_coin_dialog()


if __name__ == '__main__':
    # air = DyAir(deviceId='0A221FDD40006J')
    air = DyAir(deviceId='93LAX08UCR')
    air.check_coin_dialog()
    # air.guangjie()
    # pos, ocr_result = air.findTextByOCR('看视频得5000金.', fromY=330, height=500,
    #                                     swipeOverlayHeight=100,
    #                                     maxSwipeRetryCount=15,
    #                                     saveAllImages=True,
    #                                     saveDirPath='D:\\temp\\watch_ad_earn_money')
    # self.logWarn('pos=%s' % pos)
    # air.search()
    # air.guangjie()

    # img_fp = 'D:\\Downloads\\LocalSend\\1684636741986.jpg'
    # ocrResList = air.cnocrImpl.ocr(img_fp)
    # print(f'ocr_result:{ocrResList}')
    #
    # # btnText: str = r'去逛街'  # 按钮名称,用于跳转到逛街页面
    # # title: str = r'逛街赚钱'  # 逛街item的标题
    # # subTitle: str = r'浏览.*低价商品.*每日可完成(\d+/\d{1,2})'
    # # pos, ocrStr, ocrResList = air.findTextByOCR(targetText=btnText, prefixText=title, swipeOverlayHeight=300,
    # #                                             height=1000,
    # #                                             maxSwipeRetryCount=10)
    # completeCount, totalCount = air.get_rest_chance_count(title='逛街赚钱',
    #                                                       subTitle=r'浏览.*低价商品.*每日可完成(\d+/\d{1,2})',
    #                                                       cnocr_result=ocrResList)
    # print(f'completeCount={completeCount},total={totalCount}')
