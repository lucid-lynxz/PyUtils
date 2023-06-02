# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import re
import sys
import traceback

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)
import random
from airtest.core.api import *

from wool_tasks.base_airtest import AbsBaseAir
from util.CommonUtil import CommonUtil
from util.TimeUtil import TimeUtil
from util.NetUtil import NetUtil
from base.TaskManager import TaskManager, TaskLifeCycle
from wool_tasks.extra_tasks.import_all import *  # 用于触发装饰器
from util.decorator import log_wrap

auto_setup(__file__)
using(os.path.dirname(__file__))


class BDJsbBaseAir(AbsBaseAir):
    def initStateDict(self):
        self.updateStateKV(AbsBaseAir.key_minStreamSecs, 5 * 60)  # 间隔5min
        self.updateStateKV(AbsBaseAir.key_lastStreamTs, 0)
        return self

    def check_info_stream_valid(self, forceRecheck: bool = False) -> bool:
        return super().check_info_stream_valid(forceRecheck=forceRecheck)

    @log_wrap()
    def get_earning_info(self, coinPattern: str = r'金.收益\s*(\d+)\s*',
                         cashPatter: str = r'现金收益\s*(\d+\.?\d+)\s*',
                         ocrResList: list = None,
                         ocrHeight: int = 500) -> tuple:
        """
        获取当前手机账户收益情况 todo 根据ocrResList直接识别
        主要是切换到 '去赚钱' 页面,上滑后, ocr识别顶部内容, 最后停留在当前页面
        :param coinPattern: 金币收益的正则匹配表达式, 负数表示获取失败
        :param cashPatter: 现金收益的正则匹配表达式, 负数表示获取失败
        :param ocrResList: 复用以后的ocr识别结果,要求是从屏幕左上角开始截取的
        :param ocrHeight: 若ocrResList为空,则重新进行屏幕截图后需要识别的局部截图高度(起点是左上角(0,0))
        :return tuple(float,float) 依次表示金币收益和现金收益, 正数才有效
        """
        # self.logWarn('get_earning_info start %s %s' % (self.appName, self.deviceId))
        coin: float = 0  # 金币个数
        cash: float = 0  # 现金数,单位: 元
        earnName, earnPageKeyword = self.get_earn_monkey_tab_name()
        if not self.check_if_in_earn_page(ocrResList=ocrResList) and not self.goto_home_earn_tab():  # 跳转去赚钱页面
            img_path = self.saveScreenShot('get_earning_info_fail', autoAppendDateInfo=True)
            self.logWarn(f'get_earning_info fail as goto_home_sub_tab fail,img_path={img_path}')
            return coin, cash
        for i in range(3):  # 尝试重启获取收益情况
            # self.closeDialog()
            self.swipeUp(minDeltaY=600)  # 上滑一次
            self.saveScreenShot('查看收益全图', autoAppendDateInfo=True)
            _, ocrResult, _ = self.findTextByOCR('', height=ocrHeight, maxSwipeRetryCount=1, imgPrefixName='查看收益_')
            if CommonUtil.isNoneOrBlank(ocrResult):
                self.logWarn('get_earning_info fail as ocrResult is empty')
                return coin, cash

            # self.logWarn('get_earning_info ocrResult=%s' % ocrResult)
            coinP = re.compile(coinPattern)
            cashP = re.compile(cashPatter)

            resultList = coinP.findall(ocrResult)
            coin = coin if CommonUtil.isNoneOrBlank(resultList) else CommonUtil.convertStr2Float(resultList[0], -1)

            resultList = cashP.findall(ocrResult)
            cash = cash if CommonUtil.isNoneOrBlank(resultList) else CommonUtil.convertStr2Float(resultList[0], -1)
            coin = int(coin)

            if coin > 0 and cash > 0:
                break
            elif i <= 2:
                self.check_dialog(breakIfHitText=earnPageKeyword)  # 每次都尝试检测一次弹框,可能会有升级等弹框
                self.sleep(2)
            else:  # 当前有可能跳转到其他子集页面了,导致无法识别到收益情况,进行重启重试
                img_path = self.saveScreenShot('get_earning_info_fail', autoAppendDateInfo=True)
                # 重启app
                self.startApp(forceRestart=True,
                              msg=f'get_earning_info 失败,当前可能位于其他页面,见截图 img_path={img_path}')
                self.sleep(5)
                self.goto_home_earn_tab()
                self.sleep(3)

        self.logWarn(f'get_earning_info end coin={coin},cash={cash}')
        return coin, cash

    def get_earn_monkey_tab_name(self) -> tuple:
        """
        获取 去赚钱 页面的跳转按钮名称和目标页面的关键字(用于确认有跳转成功)
        """
        return '来赚钱', '(任务中心|抵用金|现金收益|开宝箱得金币|金币收益|赚钱任务|交友广场)'

    def get_info_stream_tab_name(self) -> tuple:
        """
        获取 首页 页面的跳转按钮名称和目标页面的关键字(用于确认有跳转成功)
        """
        return '首页', r'(^放映厅$|^同城$|^热榜TOP|^搜索：|^热搜：|^直播卖货|^抢首评|^社会榜TOP.*|作品原声|来一发弹幕)'

    def onRun(self, **kwargs):
        ocrResList = self.check_dialog()  # 检测可能存在的弹框,如:青少年模式
        coin, cash = self.get_earning_info(ocrResList=ocrResList)  # 记录当前收益值
        self.updateStateKV('coin_begin', coin)
        self.updateStateKV('cash_begin', cash)
        self.updateStateKV('startTs', time.time())
        self.logWarn('onRun get_earning_info coin=%s,cash=%s' % (coin, cash))
        # 发送推送消息
        deviceDict: dict = self.adbUtil.getDeviceInfo(self.deviceId)
        model = deviceDict.get('model')  # 设备型号,如:pixel 5
        msg = '%s 开始挂机\napp:%s\ndeviceId=%s\n金币:%s个\n现金:%s元' % (
            model, self.pkgName if CommonUtil.isNoneOrBlank(self.appName) else self.appName, self.deviceId, coin, cash)
        self.logWarn(msg)
        NetUtil.push_to_robot(msg, self.notificationRobotDict)

        inInfoStreamPage = self.back_until_info_stream_page()  # 回退到首页
        if not inInfoStreamPage:
            inInfoStreamPage = self.goto_home_information_tab(enableByRestartApp=True)
        if inInfoStreamPage or self.check_if_in_info_stream_page():
            super().onRun(**kwargs)  # 刷视频
        else:
            img_path = self.saveScreenShot('', autoAppendDateInfo=True)
            msg = '%s 挂机失败\napp:%s\ndeviceId=%s\n未能正确回到首页信息流页面\nimg:%s' % (
                model, self.pkgName if CommonUtil.isNoneOrBlank(self.appName) else self.appName, self.deviceId,
                img_path)
            self.logWarn(msg)
            NetUtil.push_to_robot(msg, self.notificationRobotDict)

    def onFinish(self, **kwargs):
        self.logWarn('onFinish')
        startTs = self.getStateValue('startTs', 0)
        duration = time.time() - startTs
        duration = TimeUtil.convertSecsDuration(duration)  # 统计总耗时

        # 计算本次挂机收益
        coin, cash = self.get_earning_info()
        coinStart = self.getStateValue('coin_begin', 0)
        cashStart = self.getStateValue('cash_begin', 0)
        deltaCoin = coin - coinStart
        deltaCash = cash - cashStart
        self.logWarn(
            'onFinish get_earning_info coinStart=%s,cashStart=%s,coin=%s,cash=%s' % (coinStart, cashStart, coin, cash))

        deviceDict: dict = self.adbUtil.getDeviceInfo(self.deviceId)
        model = deviceDict.get('model')  # 设备型号,如:pixel 5

        # 发送推送消息
        msg = '%s 完成挂机\napp:%s\ndeviceId=%s\n耗时:%s\n金币:%s -> %s \n现金:%s -> %s\n本次收益:\n金币:%s个\n现金:%s元' % (
            model, self.pkgName if CommonUtil.isNoneOrBlank(self.appName) else self.appName, self.deviceId, duration,
            coinStart, coin, cashStart, cash, deltaCoin, deltaCash)
        self.logWarn(msg)
        NetUtil.push_to_robot(msg, self.notificationRobotDict)
        self.adbUtil.exeShellCmds(['ime reset'], self.deviceId)

    # 看广告视频得xxx奖励
    @log_wrap()
    def watch_ad_video(self, count: int = 1,  # 每轮可以看广告视频的个数
                       btnText: str = r'(^领福利$|^去领取$)',
                       titleText: str = r'(^看视频得\d+金.|^看广告赚金.)',
                       minDurationSec: int = 10 * 60, back2Home: bool = False) -> bool:
        """
        ks: '去赚钱' -> '看视频得5000金币' 按钮 '领福利' -> 一共可以看10个
        dy: '来赚钱' -> '看广告赚金币' 按钮 '去领取' 每5min/20min可以看一次, 不一定
        """
        key = 'last_watch_ad_video_sec'
        lastTs = self.getStateValue(key, 0)  # 上一次观看视频广告的时间戳,单位:s
        curTs = time.time()
        if curTs - lastTs < minDurationSec:
            self.logWarn('watch_ad_video fail as curTs=%s,lastTs=%s,min=%s' % (curTs, lastTs, minDurationSec))
            return False
        self.logWarn(f'watch_ad_video start count={count}')
        success: bool = self.goto_home_earn_tab()  # 跳转到赚钱任务页面
        if not success:
            self.logWarn(f'watch_ad_video end fail as goto_home_sub_tab fail')
            return False

        for _ in range(count):
            pos, _, _ = self.findTextByOCR(btnText, prefixText=titleText, swipeOverlayHeight=300, height=1400)
            success = self.tapByTuple(self.calcCenterPos(pos))  # 点击 '领福利' 跳转到视频广告页面
            if success:  # 跳转到赚钱页面
                self.updateStateKV(key, curTs)  # 无论是否跳转成功都尝试更新时间戳

                # 可能当前无广告, 因此会跳转失败,仍在赚钱页面,此处做下判断
                _, targetKeyword = self.get_earn_monkey_tab_name()  # 去赚钱页面关键字
                pos, _, _ = self.findTextByOCR(targetKeyword, maxSwipeRetryCount=1)  # 查看当前是否仍在赚钱页面
                if CommonUtil.isNoneOrBlank(pos):
                    self.continue_watch_ad_videos(breakIfHitText=titleText)  # 继续观看知道无法继续, 最终会返回到当前页面
                success = True
            else:
                break
        if back2Home:
            self.back2HomePage()
            self.goto_home_information_tab()
        self.logWarn(f'watch_ad_video end success={success}')
        return success

    @log_wrap()
    def kan_zhibo(self, count: int = 1,  # 总共需要看几次直播
                  minDurationSec: int = -1,  # 两次直播之间的间隔时长,单位:s
                  sec: int = 90,  # 每个直播需要观看的时长
                  titlePattern: str = r'看直播.*金.',  # 赚钱任务页面中的看直播item标题
                  subTilePattern: str = r'当日最高可得.*奖励.*(\d/\d )',  # 赚钱任务的看直播item子标题
                  btnText: str = '领福利',  # 赚钱页面的看直播按钮名称
                  zhiboHomePageTitle: str = r'看直播领金.',  # 直播列表首页的标题名,用于判断是否跳转到直播详情成功
                  autoBack2Home: bool = True):
        """
        '去赚钱' -> '看直播得3000金币'
        ks可以看6个, dy可以看10个
        """
        key_can_do = 'zhibo_state'  # 是否还可以看直播
        key_last_ts = 'last_zhibo_ts'  # 上次看直播的时间,单位:s

        canDo = self.stateDict.get(key_can_do, True)
        if not canDo:
            return
        minDurationSec = minDurationSec if minDurationSec >= 0 else self.getStateValue('kanZhiBoDuration', 0)
        last_ts = self.getStateValue(key_last_ts, 0)
        curTs = time.time()
        if curTs - last_ts < minDurationSec:
            return

        self.goto_home_earn_tab()
        pos, ocr_result, _ = self.findTextByOCR(targetText=btnText, prefixText=titlePattern, swipeOverlayHeight=300,
                                                height=1400, maxSwipeRetryCount=10)
        success = self.tapByTuple(self.calcCenterPos(pos))
        if success:
            self.kan_zhibo_in_page(count=count, max_sec=sec, zhiboHomePageTitle=zhiboHomePageTitle,
                                   autoBack2Home=autoBack2Home)
        else:  # 未找到按钮, 检查是否剩余次数
            self.logWarn('未找到 "%s" 按钮,尝试查找剩余次数' % btnText)
            completeCount, totalCount = self.get_rest_chance_count_zhibo()
            if totalCount == 0:
                self.stateDict[key_can_do] = False
            else:
                self.stateDict[key_can_do] = completeCount < totalCount
                self.logWarn('已完成看直播:complete=%s,total=%s' % (completeCount, totalCount))

        if autoBack2Home:
            self.adbUtil.back()  # 当前位于去赚钱页面,直接返回一次即可到首页

    @log_wrap()
    def kan_zhibo_in_page(self, count: int = 1,  # 总共需要看几次直播
                          max_sec: int = 60,  # 每个直播最多需要观看的时长
                          zhiboHomePageTitle: str = r'^看直播领金.',  # 直播列表首页的标题名,用于判断是否跳转到直播详情成功
                          autoBack2Home: bool = False):
        """
        当前已在直播首页列表页面,点击观看指定场数的直播,每场直播观看指定时长sec
        测试路径ks:
         a. '去赚钱' -> '看直播得300金币'
         b. '去赚钱' -> '到饭点领饭补' -> '看直播'
         :param count:要看直播个数
         :param max_sec: 每个直播最多需要观看的时长
         :param zhiboHomePageTitle:直播列表页面标题
         :param autoBack2Home: 观看结束后是否自动回到首页
        """
        inZhiboHomePage: bool = self.check_if_in_page(targetText=zhiboHomePageTitle, height=500, autoCheckDialog=False)
        if not inZhiboHomePage:
            return

        w, h = self.getWH()
        for index in range(count):  # 观看直播视频
            # 随便点击一个
            posX = w * 4 / 5 if index % 2 == 1 else w / 3
            self.tapByTuple((posX, h / 2))  # 优先点击第一个
            # 检测已不在直播列表首页: 判断是否跳转直播页面成功
            inZhiboHomePage = self.check_if_in_page(targetText=zhiboHomePageTitle, height=500, autoCheckDialog=False)
            self.logWarn(
                f'kan_zhibo_in_page 跳转:{not inZhiboHomePage},count={count},sec={max_sec},title={zhiboHomePageTitle}')
            if inZhiboHomePage:  # 未跳转到直播详情页面
                self.swipeUp(durationMs=1000, minDeltaY=h / 2, maxDeltaY=h / 2)  # 上滑,观看下一个直播
                continue
            else:  # 跳转直播详情成功
                self.continue_watch_ad_videos(maxVideos=1, max_secs=max_sec + index,
                                              breakIfHitText=zhiboHomePageTitle)  # 观看直播
            if count > 1 and index % 2 == 1:
                # inZhiboHomePage: bool = self.check_if_in_page(targetText=zhiboHomePageTitle, height=500)
                self.logWarn(f'直播列表 上滑一次 index={index}/{count}')
                self.swipeUp(durationMs=1000, minDeltaY=h / 2, maxDeltaY=h / 2)  # 上滑,观看下一个直播
        self.back_until_earn_page()  # 退出直播首页列表,返回到去赚钱页面
        if autoBack2Home:
            self.back2HomePage()

    def get_rest_watch_ad_videos_secs(self, ocrResList: list = None, max_secs: int = 180) -> int:
        """
        查找看广告视频/直播页面中的剩余时长,目前包含两种: '倒计时00:18' 和 '26s后可领取奖励'
        :param ocrResList: 屏幕ocr信息
        :param max_secs: 最大有效的时长,若超出,则无效,返回-1
        :return 得到的倒计时时长信息,单位:s
        """
        extra_wait_secs = 0  # 检测到的倒计时时长,单位:s
        waitSecKeyword = r'(\d+).后.*奖励'
        if CommonUtil.isNoneOrBlank(ocrResList):
            ocrResList = self.getScreenOcrResult()
        _, ocrStr, _ = self.findTextByCnOCRResult(cnocr_result=ocrResList, targetText=waitSecKeyword)
        pattern = re.compile(waitSecKeyword)
        result = pattern.findall(ocrStr)
        if CommonUtil.isNoneOrBlank(result):
            waitSecKeyword = r'.*(\d{2}):(\d{2})'
            pos, ocrStr, _ = self.findTextByCnOCRResult(cnocr_result=ocrResList, targetText=waitSecKeyword)
            pattern = re.compile(waitSecKeyword)
            result = pattern.findall(ocrStr)
            hit = not CommonUtil.isNoneOrBlank(result)
            if hit:
                rest_minutes = CommonUtil.convertStr2Int(result[0][0], 0)
                rest_sec = CommonUtil.convertStr2Int(result[0][1], 0)
                extra_wait_secs = rest_minutes * 60 + rest_sec
        else:
            secStr = result[0]
            extra_wait_secs = CommonUtil.convertStr2Int(secStr, 10)

        if extra_wait_secs > max_secs:
            extra_wait_secs = -1
        self.logWarn(f'get_rest_watch_ad_videos_secs extra_wait_secs={extra_wait_secs},ocrStr={ocrStr}')
        return extra_wait_secs

    @log_wrap(print_out_obj=False)
    def continue_watch_ad_videos(self, max_secs: float = 90,  # 最多要观看的时长, 之后会通过检测 '已领取' / '已成功领取奖励' 来决定是否继续观看
                                 min_secs: float = 5,
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
        self.logWarn(f'continue_watch_ad_videos start maxVideos={maxVideos},breakIfHitText={breakIfHitText}')
        if maxVideos < 1:
            maxVideos = 10

        deltaSec: float = max(6.0, max_secs - min_secs)
        ocrResList = None
        for i in range(maxVideos):
            if not CommonUtil.isNoneOrBlank(breakIfHitText) and self.check_if_in_page(ocrResList=ocrResList,
                                                                                      targetText=breakIfHitText,
                                                                                      autoCheckDialog=False):
                break
            self.sleep(min_secs)  # 先观看一会,倒计时信息也有可能是晚几秒才出现的

            # 获取剩余观看时长,并进行等待
            startTs: float = time.time()
            ocrResList = self.getScreenOcrResult()
            extra_wait_secs = self.get_rest_watch_ad_videos_secs(ocrResList=ocrResList)
            extra_wait_secs = max(0.0, extra_wait_secs - (time.time() - startTs) + 1)
            if extra_wait_secs > 0:
                self.logWarn(f'continue_watch_ad_videos find extra_wait_secs={extra_wait_secs}秒')
                self.sleep(extra_wait_secs)

            deltaSec = deltaSec - (time.time() - startTs)
            deltaSec = max(deltaSec, 6)  # 至少再额外等待一会
            self.logWarn(
                f'continue_watch_ad_videos index={i},deltaSec={deltaSec}秒,extra_wait_secs={extra_wait_secs}秒')

            # 返回前先检测金币是否领取成功
            ocrResList = self.getScreenOcrResult()
            for loopIndex in range(int(deltaSec / 2)):
                pos, _, ocrResList = self.findTextByCnOCRResult(cnocr_result=ocrResList,
                                                                targetText=r'(^已领取|已成功领取奖励|领取成功|^已完成$|^直播已结束$)')
                if not CommonUtil.isNoneOrBlank(pos):
                    self.logWarn(f'已领取了奖励,尝试退出观看广告 index={loopIndex}')
                    self.adbUtil.back()  # 尝试退出
                    self.logWarn(f'已领取了奖励并返回一次,尝试关闭弹框')
                    ocrResList = self.check_dialog(canDoOtherAction=False)
                    self.logWarn(f'已领取了奖励并返回一次,关闭弹框结束')
                    break

                # 检测是否尚未观看完毕
                # 未找到 倒计时信息也无成功领取奖励的提示, 目前可能两个原因:
                # 1. 视频观看结束后,自动跳转了新页面
                # 2. 当前视频并无奖励
                # 因此执行操作: 返回到视频首页
                startTs = time.time()
                extra_wait_secs = self.get_rest_watch_ad_videos_secs(ocrResList=ocrResList, max_secs=30)
                extra_wait_secs = extra_wait_secs - (time.time() - startTs)
                if extra_wait_secs <= 0:
                    # 检测是否已退出了视频页面
                    if self.check_if_in_page(targetText=breakIfHitText, ocrResList=ocrResList, autoCheckDialog=False):
                        self.logWarn(f'当前已回到直播首页,无需继续等待: {breakIfHitText}')
                        break
                    else:
                        self.logWarn(f'未检测到剩余时长,尝试返回一次 index={loopIndex}')
                        self.adbUtil.back()  # 可能跳转了新页面,尝试返回上一页
                        self.logWarn(f'未检测到剩余时长,尝试关闭弹框start')
                        ocrResList = self.check_dialog(canDoOtherAction=False)
                        self.logWarn(f'未检测到剩余时长,尝试关闭弹框end')
                else:  # 尚未看完视频,继续观看
                    self.logWarn(f'检测到剩余时长 {extra_wait_secs},尝试等待start index={loopIndex}')
                    self.sleep(extra_wait_secs)
                    self.logWarn(f'检测到剩余时长 {extra_wait_secs},尝试等待end')
                    ocrResList = self.getScreenOcrResult()
                    self.logWarn(f'检测到剩余时长 {extra_wait_secs},等待完成并重新ocr')
                    continue

        self.back_until(targetText=breakIfHitText, maxRetryCount=3, autoCheckDialog=True)  # 尝试返回2次即可
        # ocrResList = self.check_dialog(breakIfHitText=breakIfHitText, canDoOtherAction=True)
        return self

    @log_wrap()
    def check_if_in_info_stream_page(self, auto_enter_stream_page: bool = True,
                                     forceRecheck: bool = False, autoCheckDialog: bool = True) -> bool:
        tabName, keywordInPage = self.get_info_stream_tab_name()
        valid = super().check_if_in_info_stream_page(auto_enter_stream_page=auto_enter_stream_page,
                                                     autoCheckDialog=autoCheckDialog)
        self.logWarn('check_current_at_info_stream_page start valid=%s' % valid)

        key = f'check_current_at_info_stream_page_{keywordInPage}'
        state: int = self.getStateValue(key, 0)  # 上一次检测处于特定页面的结果 0-未知(未检测过) 1-处于指定页面 -1-未处于指定页面
        forceRecheck = not valid or forceRecheck or state != 1

        if forceRecheck:
            pos, _, ocrResList = self.findTextByOCR(keywordInPage, maxSwipeRetryCount=1)
            valid = not CommonUtil.isNoneOrBlank(pos)
            if valid:  # 当前位于目标页面,检测是否有翻倍奖励
                pos, _, _ = self.findTextByCnOCRResult(ocrResList, targetText='点击翻倍', prefixText=keywordInPage)
                self.tapByTuple(self.calcCenterPos(pos))
            else:  # 未检测到目标页面关键字
                if auto_enter_stream_page:
                    self.back_until_info_stream_page()  # 回到首页
                    valid = self.goto_home_information_tab()  # 尝试进入到信息流页面
            self.logWarn('check_current_at_info_stream_page end valid=%s' % valid)
            self.updateStateKV(key, 1 if valid else -1)
            return valid
        return state == 1

    # 跳转子tab页面,默认是 '去赚钱' 页面
    @log_wrap()
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
        tEarnName, tEarnPageKeyword = self.get_earn_monkey_tab_name()
        if CommonUtil.isNoneOrBlank(name):
            name = tEarnName
            if CommonUtil.isNoneOrBlank(targetPageKeyword):
                targetPageKeyword = tEarnPageKeyword

        self.logWarn(f'goto_home_sub_tab name={name},prefixText={prefixText},targetPageKeyword={targetPageKeyword}')

        # 部分版本点击一次后是跳转新页面,因此需要判断按钮是否存在
        w, h = self.getWH()
        # 底部导航条从屏幕85%开始进行ocr
        # 同一版本,在不同机型上, 赚钱按钮可能在底部也可能在顶部搜索按钮边上...
        by = int(h * 0.85)  # 优先判断底部
        inTargetPage: bool = False
        ocrResList: list = None
        try:
            for index in range(4):
                if inTargetPage:
                    break

                ocrStartTs: float = time.time()
                pos, ocrResStr, ocrResList = self.findTextByOCR(name, prefixText=prefixText, fromY=by,
                                                                maxSwipeRetryCount=1)
                durationSec: float = round(time.time() - ocrStartTs, 2)
                self.logWarn(f'ocr duration={durationSec}秒,name={name},prefixText={prefixText},by={by}')

                pos = self.calcCenterPos(pos)
                valid = not CommonUtil.isNoneOrBlank(pos)
                if not valid:  # 未找到按钮
                    if index >= 2 and enableByRestartApp:
                        self.startApp(forceRestart=True)
                        self.sleep(5)  # 等待启动完成
                        continue

                    img_path = self.saveScreenShot('goto_home_sub_tab_start_%s_%s_%s' % (name, index, valid),
                                                   autoAppendDateInfo=True)
                    self.logWarn(f'goto_home_sub_start {valid} name={name},prefixText={prefixText},'
                                 f'img_path={img_path},ocrResult={ocrResStr}')
                    # 优先检测是否已在目标页面了, 若是则不用再做跳转
                    if self.check_if_in_page(targetText=targetPageKeyword, ocrResList=ocrResList, minOcrLen=10):
                        inTargetPage = True
                        break

                    # 当前未找到按钮也并非处于目标页面时, 尝试:
                    # 1. 判断顶部是否有赚钱按钮(这张图的ocr识别准确率太差)
                    # 2. 上滑/返回一次, 然后重新做ocr识别和跳转
                    if name == tEarnName:
                        pos = self.exists(Template(r"bd_assets/tpl1684501149238.png", record_pos=(0.306, -0.939),
                                                   resolution=(1080, 2340)))
                        if pos:
                            self.touch(pos)  # 点击进行跳转,肯定是新页面了
                            break
                else:
                    self.tapByTuple(pos)  # 可能会跳转新页面, 也可能只是当前页面的一个tab
                    break

            # 首次加载可能耗时比较长,此处进行验证
            ocrResList = self.getScreenOcrResult()
            for loopIndex in range(3):
                inTargetPage = self.check_if_in_page(targetText=targetPageKeyword, ocrResList=ocrResList,
                                                     autoCheckDialog=False)
                if inTargetPage:
                    self.logWarn(f'goto_home_sub_tab success index={loopIndex} name={name},已在目标页面,跳转加载已完成')
                    break
                else:
                    ocrResList = self.check_dialog(ocrResList=ocrResList, breakIfHitText=targetPageKeyword)

            # 已尝试进行了跳转页面
            if sleepSecsInPage > 0:
                self.sleep(sleepSecsInPage)  # 跳转后等待指定时长再继续往下执行

            # 检测签到,看视频等弹框, 并返回最后一次ocr的结果
            self.logWarn(f'goto_home_sub_tab {name} check_dialog')
            ocrResList = self.check_dialog(breakIfHitText=targetPageKeyword, ocrResList=ocrResList)

            #  尝试再点击一次tab标题, 使页面回到开始处
            if inTargetPage and tEarnName == name:
                # 肯定是从底部点击的, 避免误触 '赚钱任务' 页面的其他同名的任务按钮
                pos, _, _ = self.findTextByCnOCRResult(cnocr_result=ocrResList, targetText=name, prefixText=prefixText)
                pos = self.calcCenterPos(pos)

                # 未能第二次点击tab名称,可能无法回到页面起始位置,因此手动做N次下滑操作
                if not self.tapByTuple(pos):  # 首页是视频流, 无需下滑, 否则观看的是已看过的视频
                    for j in range(10):
                        self.swipeDown(maxDeltaY=1500)
            return inTargetPage
        except Exception as e:
            traceback.print_exc()
            img_path = self.saveScreenShot('exception_goto_sub_tab_%s' % name, autoAppendDateInfo=True)
            model = self.adbUtil.getDeviceInfo(self.deviceId).get('model', self.deviceId)
            msg = '%s %s %s\ngoto_home_sub_tab exception name=%s,prefixText=%s,targetPageKeyword=%s\nimg_path=%s' % (
                model, self.appName, self.deviceId, name, prefixText, targetPageKeyword, img_path)
            self.logWarn(msg)
            NetUtil.push_to_robot(msg, self.notificationRobotDict)

        return False

    _tpl1 = Template(r"bd_assets/tpl1685538417207.png", record_pos=(-0.002, 0.49), resolution=(1080, 2340))
    _tpl2 = Template(r"bd_assets/tpl1683813537693.png", record_pos=(0.432, 0.415), resolution=(1080, 2340))
    _tpl3 = Template(r"bd_assets/tpl1685198790981.png", record_pos=(-0.342, -0.44), resolution=(1080, 1920))
    _tpl4 = Template(r"bd_assets/tpl1685283403820.png", record_pos=(-0.004, 0.603), resolution=(1080, 2340))
    _tpl5 = Template(r"bd_assets/tpl1685624986007.png", record_pos=(0.362, -0.515), resolution=(1080, 2160))

    # 可能会弹出获得金币弹框, 点击关闭按钮
    # 耗时有点长, 4张图片大概7s
    def closeDialog(self, extraImg: str = None, autoClick: bool = True,
                    minX: int = 200, minY: int = 200, maxX: int = 0, maxY: int = 0) -> tuple:
        """
        搜索并点击关闭弹框
        :param extraImg: 其他自定义的关闭按钮图片相对路径
        :param autoClick: 匹配到关闭按钮后是否直接点击
        :param minX:匹配到的按钮必须满足的指定的区间才认为合法
        :param maxX:匹配到的按钮必须满足的指定的区间才认为合法
        :param minY:匹配到的按钮必须满足的指定的区间才认为合法
        :param maxY:匹配到的按钮必须满足的指定的区间才认为合法
        :return tuple:(float,float) 表示匹配到的按钮坐标值, 若为空,则表示未匹配到
        """
        w, h = self.getWH()
        maxX = w if maxX <= 0 else maxX
        maxY = h if maxY <= 0 else maxY
        extraTpl = None if CommonUtil.isNoneOrBlank(extraImg) else Template(extraImg)
        tpl_list = [extraTpl, self._tpl5, self._tpl1, self._tpl2, self._tpl3, self._tpl4]
        for tpl in tpl_list:
            try:
                pos = None if tpl is None else self.exists(tpl)
                if pos and minX <= pos[0] <= maxX and minY <= pos[1] <= maxY:  # 避免误点击二级页面左上角的关闭按钮
                    self.logWarn(f'closeDialog hit: {pos[0]},{pos[1]},tpl={tpl}')

                    if autoClick:
                        self.touch(pos)
                        self.sleep(1)
                    return pos[0], pos[1]
            except Exception as e:
                traceback.print_exc()
                self.logWarn('closeDialog exception')
        return ()

    @log_wrap()
    def get_rest_chance_count_search(self, titlePattern: str = r'\s*搜索(.*?)赚金.',
                                     subTilePattern: str = r'\s*搜索.*已完成(\d/\d )',
                                     cnocr_result: list = None
                                     ) -> tuple:
        return self.get_rest_chance_count(title=titlePattern, subTitle=subTilePattern,
                                          cnocr_result=cnocr_result)

    @log_wrap()
    def get_rest_chance_count_zhibo(self, titlePattern: str = r'看直播.*金.',  # 赚钱任务页面中的看直播item标题
                                    subTilePattern: str = r'当日最高可得.*奖励.*(\d/\d )',  # 赚钱任务的看直播item子标题
                                    cnocr_result: list = None) -> tuple:
        return self.get_rest_chance_count(title=titlePattern, subTitle=subTilePattern,
                                          cnocr_result=cnocr_result)

    @log_wrap()
    def search(self, count: int = 1, minDurationSec: int = -1,
               titlePattern: str = r'\s*搜索(.*?)赚金.',
               subTilePattern: str = r'\s*搜索.*已完成(\d/\d )',
               btnText: str = '去搜索'):
        """
        '去赚钱' -> '搜索 "xxx" 赚金币' 可能没有中间的双引号部分
        每次要求搜索的关键字可能有有要求, 因此需要提取ocr结果字符串进行提取
        :param count:本轮要搜索的次数,默认一次(部分版本要求两次搜索要20min间隔,部分版本又可以连续搜索...)
        :param minDurationSec:两轮搜索之间的间隔时长,单位:s, 传入负数则通过 self.stateDict.get('searchDuration', 0) 获取
        :param titlePattern: 标题行内容正则匹配表达式
        :param subTilePattern: 子标题栏内容表达式,主要是为了提取已搜索次数
        :param btnText: 搜索按钮的文本, 会进行ocr识别后得到坐标,之后进行点击跳转
        """
        key_can_do = 'search_state'  # 是否还可以搜索
        key_last_ts = 'last_search_ts'  # 上次搜索的时间,单位:s

        canSearch = self.getStateValue(key_can_do, True)
        if not canSearch:
            return
        minDurationSec = minDurationSec if minDurationSec >= 0 else self.getStateValue('searchDuration', 0)
        last_search_ts = self.getStateValue(key_last_ts, 0)
        curTs = time.time()
        if curTs - last_search_ts < minDurationSec:
            return
        self.logWarn('搜索赚金币 %s' % self.deviceId)
        # 预设的搜索关键字
        keyword_arr = ['云韵', '美杜莎', '焰灵姬', '绯羽怨姬',
                       'flutter', 'android binder', 'jetpack compose',
                       'espresso', 'aidl', 'arouter', 'transformer']
        self.goto_home_earn_tab()

        for index in range(count):
            pos, ocr_result, ocrResList = self.findTextByOCR(targetText=btnText, prefixText=titlePattern,
                                                             swipeOverlayHeight=300, appendStrFlag='',
                                                             height=1400, maxSwipeRetryCount=10)
            pos = self.calcCenterPos(pos)
            if CommonUtil.isNoneOrBlank(pos):
                completeCount, totalCount = self.get_rest_chance_count_search(titlePattern=titlePattern,
                                                                              subTilePattern=subTilePattern,
                                                                              cnocr_result=ocrResList)
                if totalCount > 0:
                    self.updateStateKV(key_can_do, completeCount < totalCount)
                self.logWarn(f'未找到 {btnText} 按钮, 已完成搜索次数 {completeCount}/{totalCount}')

                if not self.getStateValue(key_can_do, True):
                    break

            # 仍可搜索,则尝试确定是否有搜索关键字的要求
            pattern = re.compile(titlePattern)
            resultList = pattern.findall(ocr_result)
            if CommonUtil.isNoneOrBlank(resultList):
                index = int(random.random() * len(keyword_arr))
                keyword = keyword_arr[index]
                keyword_arr.remove(keyword)  # 剔除该关键字,避免相同的搜索关键字
            else:
                keyword = resultList[0].replace('"', '')
            self.logWarn('search keyword=%s, ocrPatternResultList=%s' % (keyword, resultList))

            try:
                # self.tapByTuple(pos).text(keyword, True, printCmdInfo=True)
                self.tapByTuple(pos)  # 跳转到去搜索, ks会自动定位到搜索页面的输入框

                # 由于使用 yosemite 等输入直接键入文本时,获得金币约等于无,此处尝试只输入一半内容,然后通过下拉提示列表进行点击触发关键字输入
                success = self.search_by_input(keyword)

                # 上滑浏览搜索内容,共计浏览20s
                if success:
                    self.updateStateKV(key_last_ts, curTs)  # 更新上次搜索的时间戳
                    self.adbUtil.back(times=2)  # 返回去赚钱页面
                    self.sleep(1)  # 搜索一次后, '去搜索' 按钮可能变成倒计时状态
            finally:
                pass

        self.goto_home_information_tab()  # 返回首页继续刷视频

    @log_wrap()
    def search_by_input(self, keyword: str, hintListKeyword: str = r'搜索有奖', viewSec: int = 20) -> bool:
        return super().search_by_input(keyword, hintListKeyword, viewSec)

    @log_wrap()
    def kan_xiaoshuo(self, jump2NovelHomeBtnText: str = r'(^看小说$|^看更多$)',
                     prefixText: str = r'[看|读]小说.*?赚金.',
                     jump2NovelDetailBtnText: str = r'(?:每读\(0/\d+\)|\d\.\d分)',
                     keywordInNovelDetail: str = r'(书籍介绍|第.{1,7}章|继续阅读下一页|\d+金.|下一章)',
                     eachNovelSec: float = 16 * 60, novelCount: int = 1):
        """
        dy: '来赚钱' -> '看小说赚金币' -> '看更多'
        :param jump2NovelHomeBtnText: 跳转到看小说首页的按钮正则名称
        :param prefixText: jump2NovelHomeBtnText 前面的文本
        """
        self.logWarn(f'kan_xiaoshuo start')
        self.goto_home_earn_tab()
        pos, ocrStr, ocrResList = self.findTextByOCR(targetText=jump2NovelHomeBtnText, prefixText=prefixText,
                                                     saveAllImages=False,
                                                     swipeOverlayHeight=300, fromY=200, height=1300,
                                                     imgPrefixName='小说_')
        success = self.tapByTuple(self.calcCenterPos(pos), printCmdInfo=True)  # 跳转到读小说页面
        if not success:
            self.logError(f'未找到看小说的按钮 {jump2NovelHomeBtnText} {prefixText},ocrStr={ocrStr}')
            return

        self.read_novel_detail(jump2NovelDetailBtnText=jump2NovelDetailBtnText,
                               keywordInNovelDetail=keywordInNovelDetail, eachNovelSec=eachNovelSec,
                               novelCount=novelCount)

    @log_wrap()
    def read_novel_detail(self, jump2NovelDetailBtnText: str = r'(?:每读\(0/\d+\)|\d\.\d分)',
                          jumpPrefixText: str = None,
                          keywordInNovelDetail: str = r'(书籍介绍|第.{1,7}章|继续阅读下一页|\d+金.|下一章)',
                          eachNovelSec: float = 16 * 60, novelCount: int = 1):
        """
        要求当前已在小说首页列表页, 选择具体小说进行阅读
        :param jump2NovelDetailBtnText: 从小说首页找到具体小说item的文本关键字正则表达式, 点击后跳转到读小说页面
        :param keywordInNovelDetail: 小说阅读时,必须存在的关键字,若不存在表明已跳转到广告等二级页面, 需要做一次back操作
        :param eachNovelSec: 每本小说阅读时长,单位:s 不包含看广告等时间
        :param novelCount: 需要阅读的小说本数,默认1本
        """
        # 跳转到小说列表首页, 可能有 '立即签到' 弹框
        self.logWarn(f'read_novel_detail start')
        self.check_dialog(breakIfHitText=jump2NovelDetailBtnText)  # 可能回头签到弹框, 先进行一次检测

        for loopIndex in range(4):
            self.sleep(1)
            # 首次看小说会有选择男生小说/女生小说的弹框,由于文字是竖向排列的, 因此仅识别一个 '男' 字即可
            pos, _, ocrResList = self.findTextByOCR('男', prefixText='选择兴趣得金.', maxSwipeRetryCount=1)
            pos = self.calcCenterPos(pos)
            if CommonUtil.isNoneOrBlank(pos):
                # 可能有 '番茄小说' 的下载提示框
                pos, _, _ = self.findTextByCnOCRResult(cnocr_result=ocrResList, targetText='立即下载',
                                                       prefixText='新人下载.*领.*红包$')
                pos = self.calcCenterPos(pos)
                if not CommonUtil.isNoneOrBlank(pos):
                    if loopIndex <= 1:
                        self.closeDialog()  # 关闭弹框
                        ocrResList = None
                        continue
                    elif loopIndex <= 4:
                        self.adbUtil.back()  # 尝试通过返回取消弹框
                        ocrResList = None
                        continue
                    else:  # 若通过返回键无法取消弹框,则重启
                        self.startApp(forceRestart=True, msg=f'关闭立即下载弹框失败,尝试重启app')
                        self.sleep(10)
                        self.kan_xiaoshuo()  # 重新尝试看小说
                        return
            else:
                self.tapByTuple(pos, times=2)  # 点击两次才会消失
                pos, _, ocrResList = self.findTextByOCR('', maxSwipeRetryCount=1)  # 重新识别

            pos, _, ocrResList = self.findTextByCnOCRResult(cnocr_result=ocrResList, targetText='立即签到',
                                                            prefixText='今日(签到?)可领')
            success = self.tapByTuple(self.calcCenterPos(pos))  # 立即签到
            if success:
                self.closeDialog()  # 关闭签到结果弹框
                pos, _, ocrResList = self.findTextByOCR('', maxSwipeRetryCount=1)  # 重新识别
                break

        # ks 若已有阅读时长,可以额外领取金币时, 点击: '一键领取'
        self.forLoop(self.swipeDown, times=5, sec=0)
        pos, _, _ = self.findTextByOCR(targetText='一键领取', prefixText='认真阅读.金.', maxSwipeRetryCount=1)
        self.tapByTuple(self.calcCenterPos(pos))  # 直接点击,仅有toast提示结果而已

        # 向上滑动一下,下面的书籍金币可能比较多
        cnt = int(random.random() * 3) + 1
        for i in range(cnt):
            self.swipeUp(durationMs=1000)
        # self.sleep(1)  # 等待滑动停止

        # 点击具体小说名, 跳转到小说阅读详情页面
        for index in range(novelCount):
            pos, _, _ = self.findTextByOCR(jump2NovelDetailBtnText, prefixText=jumpPrefixText, maxSwipeRetryCount=10,
                                           swipeOverlayHeight=300)  # 每读
            success = self.tapByTuple(self.calcCenterPos(pos))  # 点击跳转到小说页面进行阅读
            if not success:
                self.logError('未找到 "%s" 信息,退出读小说ocr index=%s deviceId=%s,%s' % (
                    jump2NovelDetailBtnText, index, self.deviceId, self.appName))
                self.back_until_earn_page()  # 返回到赚钱任务页面
                return

            for i in range(2):
                # 偶尔会有作者发放的红包金币, 点击立即领取即可
                self.sleep(1)
                pos, ocrStr, ocrResList = self.findTextByOCR('立即领取', maxSwipeRetryCount=1, appendStrFlag='')
                if not CommonUtil.isNoneOrBlank(pos):
                    pass
                elif CommonUtil.isNoneOrBlank(ocrStr) or len(ocrStr) <= 10:
                    # 可能网络问题,首次加载空白页面
                    for _ in range(5):
                        if CommonUtil.isNoneOrBlank(ocrStr) or len(ocrStr) <= 10:
                            self.sleep(3)
                            pos, ocrStr, ocrResList = self.findTextByOCR('立即领取', maxSwipeRetryCount=1,
                                                                         appendStrFlag='')
                        else:
                            break

                success = self.tapByTuple(self.calcCenterPos(pos))  # 立即领取会跳转到看视频页面
                if success:
                    self.continue_watch_ad_videos(breakIfHitText=keywordInNovelDetail)  # 看视频,最后会返回小说页面
                    # self.adbUtil.back()  # 返回到小说页面

                self.swipeLeft()  # 首次阅读时会有引导提示, 左滑一次可以关闭, 即使没有引导,左滑也可以作为翻页操作
                self.adbUtil.tap(500, 500)  # ks在引导页面无法通过左滑关闭,因此点击一次

            # 开始阅读小说
            curNovelSecs = 0  # 当前小说已阅读时长,单位:s
            while True:
                pos, ocrStr, ocrResList = self.findTextByOCR('立即领取', maxSwipeRetryCount=1)
                self.logWarn(f'kanxiaoshuo 已读时长:{curNovelSecs}/{eachNovelSec},ocrStr={ocrStr}')
                # 恭喜获得阅读奖励弹框, 按钮名称:'看完视频再领xxx金币'
                if CommonUtil.isNoneOrBlank(pos):
                    pos, _, _ = self.findTextByCnOCRResult(ocrResList, r'看.*视频.*\d+金.', prefixText=r'(恭喜|金币)')
                else:
                    self.logWarn(f'发现天降红包,进行领取 {self.calcCenterPos(pos)}')
                success = self.tapByTuple(self.calcCenterPos(pos))  # 立即领取会跳转到看视频页面
                if success:
                    self.continue_watch_ad_videos(breakIfHitText=keywordInNovelDetail)  # 持续观看广告视频
                    # self.adbUtil.back()  # 返回到小说阅读页面
                sec = self.sleep(minSec=3, maxSec=6) + 1  # 随机读一会

                # 确定当前仍在阅读页面, 若不是则按下返回键
                for i in range(6):
                    pos, _, ocrResList = self.findTextByOCR(keywordInNovelDetail, maxSwipeRetryCount=1)
                    pos = self.calcCenterPos(pos)
                    if not CommonUtil.isNoneOrBlank(pos):
                        pos, _, _ = self.findTextByOCR('立即解锁章节', maxSwipeRetryCount=1)
                        success = self.tapByTuple(self.calcCenterPos(pos))  # 会跳转到看视频页面
                        if success:
                            self.continue_watch_ad_videos(breakIfHitText=keywordInNovelDetail)
                            # self.adbUtil.back()  # 返回阅读页面
                        break
                    elif i <= 3:  # 可能被其他弹框遮住了关键信息,因此等待一会
                        self.sleep(3)
                    else:
                        self.adbUtil.back()  # 返回到小说阅读页面
                        self.sleep(1)
                        # 可能会弹框:  "继续观看" "放弃奖励"
                        pos, _, ocrResList = self.findTextByOCR('^继续观看', prefixText=r'再看\d+秒.{0,5}可获得奖励',
                                                                maxSwipeRetryCount=1)
                        if not CommonUtil.isNoneOrBlank(pos):
                            self.tapByTuple(self.calcCenterPos(pos))
                            self.continue_watch_ad_videos(breakIfHitText=keywordInNovelDetail)
                            # self.adbUtil.back()
                            # self.sleep(1)
                        else:
                            _, targetKeyword = self.get_earn_monkey_tab_name()  # 去赚钱页面关键字
                            pos, _, _ = self.findTextByOCR(targetKeyword, maxSwipeRetryCount=1)  # 查看当前已回到赚钱页面
                            if not CommonUtil.isNoneOrBlank(pos):
                                return

                pos, _, ocrResList = self.findTextByOCR(keywordInNovelDetail, maxSwipeRetryCount=1)
                if CommonUtil.isNoneOrBlank(pos):  # 已不在小说阅读页面
                    break
                else:
                    self.swipeLeft(maxY=400, printCmdInfo=True)  # 左滑到下一页面

                # 若已达到阅读时长要求,则退出当前小说的阅读返回小说首页
                curNovelSecs = curNovelSecs + sec
                if curNovelSecs >= eachNovelSec:
                    self.adbUtil.back()
                    # 可能底部会弹出 '加入书架' 弹框, 点击加入,弹框消失后会自动返回一次, 有可能是居中弹框
                    pos, _, ocrResList = self.findTextByOCR('^加入书架$', prefixText='^暂不加入$', maxSwipeRetryCount=1)
                    if not self.tapByTuple(self.calcCenterPos(pos)):
                        pos, _, _ = self.findTextByCnOCRResult(cnocr_result=ocrResList, targetText=r'^取消$',
                                                               prefixText='喜欢这本书就加入书架吧')
                        self.tapByTuple(self.calcCenterPos(pos))  # 取消加入书架, 会回到书籍首页
                    else:
                        pos, _, _ = self.findTextByCnOCRResult(cnocr_result=ocrResList,
                                                               targetText='喜欢这本书的用户也喜欢')
                        if not CommonUtil.isNoneOrBlank(pos):
                            self.closeDialog()  # 关闭弹框后会自动回到小说列表首页
                    break

            # 继续读下一本, 随机上滑一小段,避免重复读到相同的书籍
            minDy = 100
            maxDy = random.random() * 200 + minDy
            self.swipeUp(minDeltaY=minDy, maxDeltaY=maxDy, durationMs=1200)

        # 阅读结束, 返回到页面最开头看下是否有 '一键领取' 金币选项
        self.forLoop(self.swipeDown, times=5, sec=0)
        pos, _, _ = self.findTextByCnOCRResult(ocrResList, targetText='一键领取', prefixText='认真阅读赢金.')
        success = self.tapByTuple(self.calcCenterPos(pos))  # 直接点击,仅有toast提示结果而已

        self.back2HomePage()  # 返回首页
        self.goto_home_earn_tab()  # 返回到赚钱任务页面

    @log_wrap(exclude_arg=['self', 'ocrResList'], print_out_obj=False, print_caller=True)
    def check_dialog(self, ocrResList: list = None, fromX: int = 0, fromY: int = 0, retryCount: int = 6,
                     breakIfHitText: str = None, *args, **kwargs) -> list:
        """
        检测当前界面的弹框,并统一处理:
        1. 对于领取红包的, 直接领取
        2. 对于看广告视频的, 点击进行跳转观看, 观看结束后返回当前页面
        :param ocrResList: cnorcr识别结果,避免重复截图识别,若为None则会重新截图及ocr
        :param fromX: ocrResList 非 None 时有效, 用于表示 ocrResList 的在屏幕上的偏移量
        :param fromY: 同上
        :param retryCount: 检测次数
        :param breakIfHitText: 观看广告视频返回到指定页面时,要停止继续返回,默认是None表示不检测
        :param kwargs: 目前支持: 'canDoOtherAction'
        :return list: 最后一次cnocr识别结果
        """
        if CommonUtil.isNoneOrBlank(ocrResList):
            ocrResList = self.getScreenOcrResult()
            fromX = 0
            fromY = 0

        canDoOtherAction: bool = kwargs.get('canDoOtherAction', True)
        checkFuncList = TaskManager.getTaskList('check_dialog', taskLifeCycle=TaskLifeCycle.custom)
        retry: int = 0

        lastHitFuncName = None  # 上一次命中的函数名
        lastHitFuncCount = 0  # 该函数总共连续命中了几次
        maxHitFuncCount = 3  # 最终只允许连续命中上次,超过就跳过该函数,因此可能识别出错了
        while True:
            self.logWarn(
                f'check_dialog loop start,canDoOtherAction={canDoOtherAction},ocrStr={self.composeOcrStr(ocrResList)}')
            consumed: bool = False
            funcSize: int = len(checkFuncList)
            for item in checkFuncList:
                funcName = item.__name__
                self.logWarn(f'check_dialog try: {funcName},total={funcSize}')
                if lastHitFuncCount >= maxHitFuncCount:
                    self.logWarn(f'lastHitFuncName={lastHitFuncName},hitCnt={lastHitFuncCount},skip current')
                    lastHitFuncName = None
                    lastHitFuncCount = 0
                    continue

                consumed = item(baseAir=self, ocrResList=ocrResList, breakIfHitText=breakIfHitText,
                                fromX=fromX, fromY=fromY, *args, **kwargs)
                if consumed:
                    self.sleep(2)
                    self.logWarn(f'check_dialog consumed {retry}/{retryCount}: {funcName}')
                    ocrResList = self.getScreenOcrResult()  # 重新ocr并继续执行后续的按钮
                    if lastHitFuncName is None or funcName == lastHitFuncName:
                        lastHitFuncName = funcName
                        lastHitFuncCount = lastHitFuncCount + 1

            retry = retry + 1
            if retry >= retryCount:
                self.logWarn(f'check_dialog exceed {retryCount},exit')
                break
            if consumed:
                ocrResList = self.getScreenOcrResult()
            else:
                break
        return ocrResList

    def back2HomePage(self, funcDoAfterPressBack=None):
        # super().back2HomePage(funcDoAfterPressBack)
        super().back_until_info_stream_page()
        if funcDoAfterPressBack is not None:
            funcDoAfterPressBack()
