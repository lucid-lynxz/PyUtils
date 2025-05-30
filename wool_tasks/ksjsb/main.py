# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from airtest.core.api import *
from airtest.core.helper import using

from util.CommonUtil import CommonUtil
from wool_tasks.base_airtest_bd_jsb import BDJsbBaseAir

auto_setup(__file__)


class KsAir(BDJsbBaseAir):
    PKG_NAME = 'com.kuaishou.nebula'

    def __init__(self, deviceId: str, forceRestart=True, totalSec: int = 180, minInfoStreamSec: int = 180):
        super().__init__(deviceId=deviceId, pkgName=KsAir.PKG_NAME,
                         homeActPath='com.yxcorp.gifshow.HomeActivity',
                         appName='快手极速版',
                         minInfoStreamSec=minInfoStreamSec,
                         totalSec=totalSec,
                         forceRestart=forceRestart)
        using(os.path.dirname(__file__))
        self.updateStateKV('searchDuration', 5 * 60)  # 搜索间隔

    def get_earning_info(self, coinPattern: str = r'金.:\s*(\d+)\s*',  # 偶尔会识别为: 金币 / 金市
                         cashPatter: str = r'抵用金:\s*(\d+\.?\d+)\s*',
                         ocrResList: list = None,
                         ocrHeight: int = 500) -> tuple:
        return super().get_earning_info(coinPattern=coinPattern,
                                        cashPatter=cashPatter,
                                        ocrResList=ocrResList,
                                        ocrHeight=ocrHeight)

    def zaoqi_daka(self, back2Home: bool = False):
        """
        '去赚钱' ->'早起打卡瓜分金币'
        每天早上8-12点打开页面即可,报名费300金币,通常有 150 的收益, 最后自行返回首页
        """
        key = 'zaoqi_daka'  # 是否已打卡
        hit = self.stateDict.get(key, False)
        if hit:  # 已打过卡
            return
        key_ts = 'zaoqi_daka_ts'  # 上次尝试打卡时间戳,单位: s
        lastTs = self.stateDict.get(key_ts, 0)
        # 8点-9点, 每10min中尝试一次

        lt = time.localtime()
        hour = lt.tm_hour
        sec = lt.tm_sec
        cutTs = time.time()  # 当前时间戳
        if 8 < hour < 11 and cutTs - lastTs >= 10 * 60:
            self.logWarn('zaoqi_daka start')
            self.stateDict[key_ts] = cutTs
            _, earnKeyword = self.get_earn_monkey_tab_name()
            self.goto_home_earn_tab()
            # 8点钱 "去查看"  8-12点  "领金币"  领完金币 "去查看"
            posList, _, _ = self.findTextByOCR(targetText='领金.', prefixText='早起打卡.*金.',
                                               swipeOverlayHeight=300, height=1000)
            centerPos = self.calcCenterPos(posList)
            if not CommonUtil.isNoneOrBlank(centerPos):
                self.tapByTuple(centerPos)  # 点击跳转进行打卡
                self.updateStateKV(key, True)
                self.sleep(3)
                self.check_dialog(breakIfHitText=earnKeyword)
                self.closeDialog()  # 关闭打卡成功
                self.sleep(3)  # 等待刷新

                posList, _, _ = self.findTextByOCR(targetText=r'\d+金.报名', prefixText='本期可.分金.奖池',
                                                   maxSwipeRetryCount=1)
                centerPos = self.calcCenterPos(posList)
                if not CommonUtil.isNoneOrBlank(centerPos):
                    self.tapByTuple(centerPos)  # 点击进行报名
                    self.sleep(3)
                    self.closeDialog()  # 关闭打卡成功
                self.back_until(maxRetryCount=1)  # 回到 '去赚钱'页面

            if back2Home:
                self.back2HomePage()  # 返回首页
                self.goto_home_sub_tab(name='首页')
            self.logWarn('zaoqi_daka end')

    # def onRun(self, **kwargs):
    #     # super().onRun(**kwargs)
    #     self.updateStateKV('startTs', time.time())  # 开始执行时间
    #     coin, cash = self.get_earning_info()  # 开始时的金币/现金信息
    #     self.updateStateKV('coin_begin', coin)
    #     self.updateStateKV('cash_begin', cash)
    #
    #     # 发送推送消息
    #     deviceDict: dict = self.adbUtil.getDeviceInfo(self.deviceId)
    #     model = deviceDict.get('model')  # 设备型号,如:pixel 5
    #     msg = '%s 开始挂机\napp:%s\ndeviceId=%s\n金币:%s个\n现金:%s元' % (
    #         model, self.pkgName if CommonUtil.isNoneOrBlank(self.appName) else self.appName, self.deviceId, coin, cash)
    #     NetUtil.push_to_robot(msg, self.notificationRobotDict)
    #     self.runAction(self.video_stream_page)

    # 首页 -> '去赚钱' -> '看视频得xx元' -> 跳转视频流页面, 持续刷视频
    def video_stream_page(self, minSec: float = 2, maxSec=5) -> float:
        """
        信息流页面操作，比如视频流页面的不断刷视频，直到达到指定时长
        :param minSec: 每个视频停留观看的最短时长，单位：s
        :param maxSec: 每个视频停留观看的最长时长，单位：s
        :return: 总共看视频的时长
        """
        self.logWarn(f'video_stream_page start totalSec={self.totalSec}')
        # 不通过 '去赚钱' 页面跳转了, 直接切到 '首页' 浏览20min视频
        self.goto_home_information_tab()

        threshold_retry_times: int = 20  # 连续多少个非视频页面就退出测试
        cur_retry_times: int = 0  # 已尝试的次数
        valid_secs: float = 0  # 看视频的时长,单位:s
        total_secs: float = 0  # 总累计时长,单位:s
        startTs = time.time()  # 开始时间戳,单位:s

        while True:
            # 检测当前页面是否是首页视频奖励页面
            valid = self.check_info_stream_valid()
            if not valid:
                self.swipeUp()
                self.sleep(1)
                cur_retry_times += 1
                if cur_retry_times > threshold_retry_times:
                    return valid_secs
                continue

            cur_retry_times = 0  # 有奖励的页面则重置等待次数
            watch_secs = self.sleep(minSec=minSec, maxSec=maxSec)  # 等待，模拟正在观看视频

            valid_secs += watch_secs  # 累计已看视频时长
            total_secs = time.time() - startTs  # 累计耗时,单位:s
            # 视频观看结束后，上滑切换到下一个视频
            self.swipeUp()

            # 计算总耗时，若超过totalSec，则退出, 此处适当放宽限制,冗余10%,减少因与app算法误差导致未刷够时长
            self.logWarn('video_stream_page valid_secs=%s,max=%s,total_secs=%s,deviceId=%s' % (
                valid_secs, self.totalSec, total_secs, self.deviceId))
            if valid_secs >= self.totalSec or total_secs >= self.totalSec * 1.1:
                break

        self.logWarn(
            'video_stream_page end 总共看视频 %s 秒,总耗时:%s,deviceId=%s' % (valid_secs, total_secs, self.deviceId))
        return valid_secs

    def get_earn_monkey_tab_name(self) -> tuple:
        """
        获取 去赚钱 页面的跳转按钮名称和目标页面的关键字(用于确认有跳转成功)
        """
        return '去赚钱', '(任务中心|抵用金|现金收益|开宝箱得金.|金.收益|赚钱任务|交友广场|金.购划算)'

    def shipin_biaotai(self, count: int = 36, minDurationSec: int = -1,
                       titlePattern: str = r'给视频表态赚金.',
                       subTilePattern: str = r'看到更多好作品.*(\d{1,2}/\d{1,2})',
                       btnText: str = r'去表态', back2Home: bool = False):
        """
        对视频进行表态：满意、不满意、不确定
        ks: '去赚钱' -> 新手任务 '给视频表态赚金币'  按钮 '去表态'
        :param count:待表态的视频数, 会根据子标题行的实际值进行调整,若识别失败,才使用外部传入值
        """
        key_can_do = f'shipin_biaotai_state'
        key_last_ts = f'shipin_biaotai_last_ts'

        canDo = self.getStateValue(key_can_do, True)
        if not canDo:
            return
        last_search_ts = self.getStateValue(key_last_ts, 0)
        curTs = time.time()
        if curTs - last_search_ts < minDurationSec:
            return

        self.logWarn(f'shipin_biaotai 赚金币 start')
        self.goto_home_sub_tab()

        pos, ocrStr, ocrResList = self.findTextByOCR(targetText=btnText, prefixText=titlePattern,
                                                     swipeOverlayHeight=300, height=1000)
        completeCount, totalCount = self.get_rest_chance_count(title=titlePattern, subTitle=subTilePattern,
                                                               cnocr_result=ocrResList)
        if completeCount > 0 and totalCount > 0:
            count = totalCount - completeCount

        success = self.tapByTuple(self.calcCenterPos(pos))
        if not success:
            if back2Home:
                self.back2HomePage()
            self.logWarn(f'shipin_biaotai 未找到 {btnText} 按钮,应是已不可表态了: {completeCount}/{totalCount}')
            self.updateStateKV(key_can_do, False)
            return
        self.updateStateKV(key_last_ts, curTs)
        self.sleep(2)  # 首次跳转等待
        w, h = self.getWH()
        fromY = h * 0.75
        # 视频评价按钮的点击位置，依次对应： 满意，不满意，不确定
        pos_rating_arr: list = [(), (), ()]
        success = False
        for loopIndex in range(5):
            pos, ocrStr, ocrResList = self.findTextByOCR('满意', prefixText='视频是否满意', fromY=fromY,
                                                         maxSwipeRetryCount=1)
            self.logWarn(f'表态 {loopIndex}: ocrStr:{ocrStr}')
            pos_rating_arr[0] = self.calcCenterPos(pos)
            pos, _, _ = self.findTextByCnOCRResult(ocrResList, '不满意', prefixText='满意', fromY=fromY)
            pos_rating_arr[1] = self.calcCenterPos(pos)
            pos, _, _ = self.findTextByCnOCRResult(ocrResList, '不确定', prefixText='不满意', fromY=fromY)
            pos_rating_arr[2] = self.calcCenterPos(pos)

            if not CommonUtil.isNoneOrBlank(pos_rating_arr[0]) and not CommonUtil.isNoneOrBlank(
                    pos_rating_arr[1]) and not CommonUtil.isNoneOrBlank(pos_rating_arr[2]):
                success = True
                break
            self.swipeUp()  # 换下一个视频,可能更好识别
            self.sleep(3)

        if not success:
            self.logWarn(f'shipin_biaotai fail 因为未找到三个按钮位置信息: {completeCount}/{totalCount}')
            self.back_until(maxRetryCount=1)  # 返回到 '去赚钱' 页面
            if back2Home:
                self.back2HomePage()
            return

        self.logWarn(f'shipin_biaotai 开始进行表态,当前已完成: {completeCount}/{totalCount},按钮位置:{pos_rating_arr}')
        import random
        evaluatedCount = 0  # 已表态的数量
        while True:
            self.sleep(minSec=3, maxSec=5)
            index = round(random.random() * 3)  # 表态的序号：0-满意 1-不满意 2-不确定 其他值-不表态，跳转下一个视频
            if index <= 2:
                if self.tapByTuple(pos_rating_arr[index]):
                    evaluatedCount += 1
                    self.sleep(minSec=1, maxSec=3)
            self.swipeUp()  # 上滑到下一个视频
            if evaluatedCount >= count:
                self.updateStateKV(key_can_do, False)
                break
        self.back_until(maxRetryCount=1)  # 返回去赚钱页面
        if back2Home:
            self.back2HomePage()
        self.logWarn(f'shipin_biaotai end')


if __name__ == '__main__':
    # KsAir(deviceId='', forceRestart=False).search()
    ksAir = KsAir(deviceId='7b65fc7a', forceRestart=False)
    # ksAir.kan_zhibo(count=8)

    _, ocrStr, _ = ksAir.findTextByOCR(r'(\d+).后.*奖励', maxSwipeRetryCount=1)
    print(f'ocrStr={ocrStr}')
    # print(f'curAct={ksAir.adbUtil.getCurrentActivity()}')
