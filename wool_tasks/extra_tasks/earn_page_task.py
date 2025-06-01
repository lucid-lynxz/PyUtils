# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import random
import re
import time
from typing import Union

from base.TaskManager import taskWrapper, TaskLifeCycle
from util.CommonUtil import CommonUtil
from wool_tasks.base_airtest import AbsBaseAir4Android

"""
赚钱页面任务分解
要求当前已在赚钱页面才触发相关方法
"""

__tag = 'earn_page_action'


def _find_pos(baseAir: AbsBaseAir4Android, ocrResList: Union[list, None],
              targetText: str, prefixText: str = None, subfixText: str = None,
              fromX: int = 0, fromY: int = 0, height: int = 0,
              maxDeltaX: int = 0, maxDeltaY: int = 0, appendStrFlag: str = ' ',
              maxSwipeRetryCount: int = 1) -> tuple:
    """
    :param maxDeltaY: 匹配到的文本允许的最大高度差, 此处单行文本计为70像素, 默认最大4行文本
    返回tuple:
        元素0: 按钮位置tuple
        元素1: ocr识别文本字符串
        元素2: 完整的cnocr识别结果list, 若入参 ocrResList 非空,则返回的是入参值
    """
    if CommonUtil.isNoneOrBlank(ocrResList):
        pos, ocrStr, ocrResList = baseAir.findTextByOCR(targetText=targetText, prefixText=prefixText,
                                                        subfixText=subfixText, appendStrFlag=appendStrFlag,
                                                        fromX=fromX, fromY=fromY, height=height,
                                                        maxDeltaX=maxDeltaX, maxDeltaY=maxDeltaY,
                                                        maxSwipeRetryCount=maxSwipeRetryCount)
    else:
        pos, ocrStr, _ = baseAir.findTextByCnOCRResult(ocrResList, targetText=targetText, prefixText=prefixText,
                                                       subfixText=subfixText,
                                                       appendStrFlag=appendStrFlag, fromX=fromX, fromY=fromY,
                                                       maxDeltaX=maxDeltaX, maxDeltaY=maxDeltaY)
    pos = baseAir.calcCenterPos(pos)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.logWarn(
            f'${__tag} _find_pos hit targetText={targetText},prefixText={prefixText}'
            f',subfixText={subfixText},pos={pos},ocrStr={ocrStr}')
    return pos, ocrStr, ocrResList


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def dao_fandian_ling_fanbu(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                           fromX: int = 0, fromY: int = 0) -> bool:
    """
    ks '去赚钱' -> '到饭点领饭补' 按钮 '去查看'/'去领取' ->
    页面顶部: '到点领饭补金币'
    饭补补贴按钮: '00:05:23 后领取夜宵补贴' / '领取饭补40金币'
    底部按钮 '看视频'/'看直播

    早饭饭补: 05:00-09:00  42金币
    午饭饭补: 11:00-14:00 32金币
    晚饭饭补: 17:00-20:00 36金币
    夜宵饭补: 21:00-24:00 40金币

    点击 '领取饭补xx金币' 后, 弹框 '恭喜获得夜宵补贴', '看视频再领40金币'
    底部的 '看视频' 按钮大概可以看10个视频, 每个10~26s, 收益固定60金币
    底部的 '看直播' 可以看10个不同的直播,每个看10s即可, 大部分10金币, 也有见过125金币的
    若无法跳转会toast: '任务已完成,明天再来吧~'
    最后回到赚钱页面
    """
    key = 'dao_fandian_ling_fanbu'  # 是否还有机会领饭补,当前仅考虑看直播/看视频的机会
    if not baseAir.getStateValue(key, True):
        return False

    # 去赚钱页面按钮信息
    titleText: str = r'到饭点领饭补'  # 去赚钱页面的领取饭补item标题内容
    btnText: str = r'(^去查看$|^去领取$)'  # 取赚钱页面的领取饭补按钮名称
    subTitleText: str = r'(错过饭点也能领.*点击立得|好好吃饭)'  # 子标题内容
    targetText: str = subTitleText

    # 饭补页面的信息
    btnText4Fanbu: str = r'领取饭补\d+金.'  # 在饭补页面,底部领取饭补按钮名称
    title4Fanbu: str = r'(到点领.*饭补金.|领.*补贴)'  # 饭补页面顶部标题,用于判断是否跳转成功
    _, earnPageKeyWord = baseAir.get_earn_monkey_tab_name()

    # 尝试跳转到领取饭补页面
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=titleText,
                                        fromX=fromX, fromY=fromY)
    if not baseAir.tapByTuple(pos):
        return False

    if baseAir.check_if_in_page(targetText=earnPageKeyWord, autoCheckDialog=False):  # 跳转是失败,当前仍在赚钱任务页面
        baseAir.logWarn(f'当前仍在earn页面,领饭补失败 {ocrStr}')
        baseAir.check_dialog(ocrResList=ocrResList, breakIfHitText=breakIfHitText)
        return False

    # 尝试点击 '领取饭补42金币' 按钮
    baseAir.sleep(3)
    pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText=btnText4Fanbu, prefixText=title4Fanbu)
    if baseAir.tapByTuple(pos):
        baseAir.check_dialog(breakIfHitText=title4Fanbu)  # 检测金币弹框,按需跳转查看视频,最后返回当前页面
        baseAir.sleep(2)  # 可能需要等待下, 下方的 '看视频'/'看直播'按钮才会显示

    # 检测是否还在饭补页面
    if not baseAir.check_if_in_page(targetText=title4Fanbu, autoCheckDialog=False):
        baseAir.logWarn(f'当前已不在饭补页面,返回首页赚钱页面')
        if baseAir.check_if_in_page(targetText=earnPageKeyWord, autoCheckDialog=False):
            return True

        baseAir.back_until_earn_page()
        return True

    # 点击 '看视频' 按钮
    baseAir.logWarn(f'到饭点...看视频start')
    pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText='^看视频', prefixText=title4Fanbu)
    for _ in range(10):
        if not baseAir.tapByTuple(pos):
            break
        # 此处不复用pos变量,避免需要重新ocr
        tempPos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText='^看视频', prefixText=title4Fanbu)
        if CommonUtil.isNoneOrBlank(tempPos):  # 跳转成功
            baseAir.continue_watch_ad_videos(breakIfHitText=title4Fanbu)
        else:  # 未跳转成功, 应该是不能再看了
            break

    # 点击 '看直播' 按钮
    baseAir.logWarn(f'到饭点...看直播start')
    if baseAir.check_if_in_page(targetText=title4Fanbu, autoCheckDialog=False):
        pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText='^看直播.?$', prefixText=title4Fanbu)
        if baseAir.tapByTuple(pos):
            pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText='^看直播.?$', prefixText=title4Fanbu)
            if CommonUtil.isNoneOrBlank(pos):  # 跳转成功
                baseAir.kan_zhibo_in_page(count=10, max_sec=90, autoBack2Home=False)
    baseAir.logWarn(f'到饭点...看直播 end')
    baseAir.updateStateKV(key, False)
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def watch_ad_video(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                   fromX: int = 0, fromY: int = 0) -> bool:
    """
    ks: '去赚钱' -> '看视频得5000金币' 按钮 '领福利'
    ks: '去赚钱' -> '看广告得2400金币' 按钮 '领福利'
                    副标题: 当日最高赚2400金币, 0/3
    dy: '来赚钱' -> '看广告赚金币' 按钮 '去领取' 每5min/20min可以看一次, 不一定,偶尔也觃
         副标题: '每5分钟完成一次广告任务,单日最高可赚20000金币'  共2行
    """
    minDurationSec: int = 30  # 至少间隔多久才可以再次尝试看视频, ks没限制,连续几次可能会一次限制30s, 1min或更长间隔才能继续
    if baseAir.pkgName == 'com.ss.android.ugc.aweme.lite':  # dy 每5min可以刷一次广告
        minDurationSec = 5 * 60

    key = f'watch_ad_video_ts_{__tag}'  # 上次观看广告视频的时间戳
    lastTs = baseAir.getStateValue(key, 0)  # 上一次观看视频广告的时间戳,单位:s
    curTs = time.time()
    if curTs - lastTs < minDurationSec:
        baseAir.logWarn('watch_ad_video fail as curTs=%s,lastTs=%s,min=%s' % (curTs, lastTs, minDurationSec))
        return False

    btnText: str = r'(^领福利$|^去领取$)'
    titleText: str = r'(^看视频得\d+金.|^看广告赚金.|看广告得\d+金.)'
    subTitleText: str = r'(单日最高|广告任务)'
    targetText: str = subTitleText
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=targetText, prefixText=titleText,
                                        fromX=fromX, fromY=fromY)
    if not baseAir.tapByTuple(pos, sleepSec=5):
        return False

    # 可能跳转后无广告自动返回,此时也需要重新ocr
    if baseAir.check_if_in_earn_page(autoCheckDialog=False):
        return True

    baseAir.logWarn(f'watch_ad_video start')
    baseAir.updateStateKV(key, curTs)  # 上一次观看视频广告的时间戳,单位:s
    baseAir.continue_watch_ad_videos(breakIfHitText=titleText)  # 继续观看直到无法继续, 最终会返回到当前页面
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def search_ks(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
              fromX: int = 0, fromY: int = 0) -> bool:
    """
    '去赚钱' -> '搜索 "xxx" 赚金币' 可能没有中间的双引号部分
    每次要求搜索的关键字可能有有要求, 因此需要提取ocr结果字符串进行提取
    """
    if baseAir.pkgName != 'com.kuaishou.nebula':
        return False

    titleText: str = r'\s*搜索(.*?)赚金.'
    subTileText: str = r'\d+/\d+'
    btnText: str = '去搜索'

    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=btnText, prefixText=titleText,
                                        subfixText=subTileText, fromX=fromX, fromY=fromY)
    if CommonUtil.isNoneOrBlank(pos):
        return False

    # 预设的搜索关键字
    keyword_arr = ['云韵', '美杜莎', '焰灵姬', '绯羽怨姬',
                   'flutter', 'android binder', 'jetpack compose',
                   'espresso', 'aidl', 'arouter', 'transformer']

    pattern = re.compile(titleText)
    resultList = pattern.findall(ocrStr)
    if CommonUtil.isNoneOrBlank(resultList):
        index = int(random.random() * len(keyword_arr))
        keyword = keyword_arr[index]
        keyword_arr.remove(keyword)
    else:
        keyword = resultList[0].replace('"', '')
    baseAir.logWarn('search_ks keyword=%s, ocrPatternResultList=%s' % (keyword, resultList))

    try:
        # baseAir.tapByTuple(pos).text(keyword, True, printCmdInfo=True)
        baseAir.tapByTuple(pos)  # 跳转到去搜索, ks会自动定位到搜索页面的输入框

        # 由于使用 yosemite 等输入直接键入文本时,获得金币约等于无,此处尝试只输入一半内容,然后通过下拉提示列表进行点击触发关键字输入
        # 上滑浏览搜索内容,共计浏览20s
        baseAir.search_by_input(keyword)
    finally:
        pass
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kan_zhibo(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
              fromX: int = 0, fromY: int = 0) -> bool:
    """
    标题: '看直播得3000金币' 或者 '看直播广告可得1.3万金币 或者 '看6次直播领金币'
    按钮:'领福利'
    ks可以看6个, dy可以看10个
    """
    key = 'kan_zhibo'  # 是否已完成
    if baseAir.getStateValue(key, False):
        return False

    titleText: str = r'看.{0,2}直播.{0,10}金.'  # 赚钱任务页面中的看直播item标题
    subTileText: str = r'\d+/\d+'  # 赚钱任务的看直播item子标题
    btnText: str = '领福利'  # 赚钱页面的看直播按钮名称
    zhiboHomePageTitle: str = r'看直播领金.'  # 直播列表首页的标题名,用于判断是否跳转到直播详情成功

    pos, ocr_result, ocrResList = _find_pos(baseAir=baseAir, ocrResList=ocrResList, targetText=btnText,
                                            prefixText=titleText, subfixText=subTileText,
                                            fromX=fromX, fromY=fromY)
    if CommonUtil.isNoneOrBlank(pos):
        return False

    # 计算剩余次数
    completeCount, totalCount = baseAir.get_rest_chance_count(title=titleText, subTitle=subTileText,
                                                              cnocr_result=ocrResList)
    count = totalCount - completeCount  # 总共需要看几次直播
    baseAir.updateStateKV(key, count <= 0 < completeCount)
    if count <= 0:
        return False

    if baseAir.tapByTuple(pos):
        baseAir.kan_zhibo_in_page(count=count, max_sec=90, zhiboHomePageTitle=zhiboHomePageTitle,
                                  autoBack2Home=False)
        baseAir.back_until_earn_page()
        return True
    else:  # 未找到按钮, 检查是否剩余次数
        return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def jinbi_gouhuasuan_qiandao(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                             fromX: int = 0, fromY: int = 0) -> bool:
    """
    '去赚钱'  -> '金币购划算' -> '今日签到' 每天可以签到一次 , '看直播可领' 300金币, 看三个直播视频
    """
    func_name = 'jinbi_gouhuasuan_qiandao'
    if not baseAir.getStateValue(func_name, True):
        return False

    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'^金.购划算$',
                                        fromX=fromX, fromY=fromY)
    if not baseAir.tapByTuple(pos):
        return False

    baseAir.sleep(3)
    for i in range(3):  # 今日签到
        pos, ocrStr, ocrResList = baseAir.findTextByOCR(targetText=r'^今日签到$', height=800, maxSwipeRetryCount=1)
        success = baseAir.tapByTuple(baseAir.calcCenterPos(pos))
        if success:
            break
        else:
            pos, _, _ = _find_pos(baseAir=baseAir, ocrResList=ocrResList, targetText=r'^明日签到$', prefixText='订单')
            if CommonUtil.isNoneOrBlank(pos):
                baseAir.sleep(2)  # 额外等一会,可能是还没加载完成
            else:  # 已经签到过了
                break

    # 看直播可领300金币
    pos, ocrStr, ocrResList = _find_pos(baseAir=baseAir, ocrResList=ocrResList, targetText=r'^看直播可领')
    if baseAir.tapByTuple(pos):
        baseAir.sleep(3)  # 可能会加载一下
        baseAir.kan_zhibo_in_page(count=3, max_sec=90, zhiboHomePageTitle='爆款好物')
    baseAir.updateStateKV(func_name, False)  # 一次性任务,每天跑一次即可
    baseAir.back_until(targetText=breakIfHitText)  # 返回去赚钱页
    baseAir.logWarn(f'jinbi_gouhuasuan_qiandao end ocrStr: {ocrStr}')
    return True


def _dy_kan_xiaoshuo_liing_jinbi(baseAir: AbsBaseAir4Android) -> bool:
    """
    dy看小说页面领取金币
    """
    if baseAir.pkgName != 'com.ss.android.ugc.aweme.lite':
        return False
    pos, _, ocrResList = baseAir.findTextByOCR(targetText=r'\d{2,4}金.',
                                               prefixText=r'(排行榜|小说|我的书架)',
                                               fromY=1000,  # 默认位于屏幕下方区域, 可左可右
                                               maxSwipeRetryCount=1)
    if baseAir.tapByTuple(pos):
        prefixText: str = r'(阅读赚金.|看小说赚金.|待领取|今日已赚|再看\d+分钟可得|已领取|待领取|明天签到)'
        for _ in range(6):
            pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText=r'(领取金.|去领取)',
                                           prefixText=prefixText)
            baseAir.logWarn(f'_dy_kan_xiaoshuo_liing_jinbi 检测领取金币 ocrStr2={baseAir.composeOcrStr(ocrResList)}')
            if baseAir.tapByTuple(pos):  # 若可以领金币,则会弹出 "我知道了" 弹框
                baseAir.check_dialog(canDoOtherAction=True, breakIfHitText=prefixText)
            else:
                pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText=r'看小说', prefixText=prefixText)
                baseAir.tapByTuple(pos)  # 点击底部 '看小说' 按钮,回到小说主页面
                break
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kan_xiaoshuo(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0) -> bool:
    """
    dy: '来赚钱' -> '看小说赚金币' -> '看更多'
    """
    key = 'kan_xiaoshuo_secs'  # 累计看小说的时长
    key_last_ts = 'kan_xiaoshuo_last_ts'  # 上一次看小说的时间,单位:s

    maxReadSec: int = 90 * 60  # 总共最多只需要看90min
    minDuration: int = 5 * 60  # 两次看小说之间的时间间隔, 单位:s
    hasReadSecs = baseAir.getStateValue(key, 0)  # 已读时长,单位:s
    lastReadTs = baseAir.getStateValue(key_last_ts, 0)
    if hasReadSecs >= maxReadSec or time.time() - lastReadTs <= minDuration:
        return False

    itemBtnText: str = r'(^看小说|^看更多)'  # 跳转到看小说首页的按钮正则名称
    itemTitle: str = r'[看|读]小说.*?赚金.'  # 看小说item信息标题
    itemSubTitle: str = ''  # r'(最高每分钟可得|精彩小说|看越多)'  # 看小说item信息标题
    eachNovelSec: float = 6 * 60  # 每本小说阅读时长,单位:s
    earnName, earnKeyword = baseAir.get_earn_monkey_tab_name()
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=itemBtnText, prefixText=itemTitle,
                                        subfixText=itemSubTitle, fromX=fromX, fromY=fromY)
    if not baseAir.tapByTuple(pos, sleepSec=5):  # 跳转到读小说页面
        baseAir.logError(f'kan_xiaoshuo 未找到按钮 {itemBtnText} {itemTitle},ocrStr={ocrStr}')
        return False
    baseAir.sleep(20)  # 刷新比较慢, 额外等一会

    ocrResList = baseAir.getScreenOcrResult()
    if baseAir.check_if_in_page(earnKeyword, ocrResList=ocrResList):
        baseAir.logWarn(f'kan_xiaoshuo 跳转失败,当前仍在赚钱页面')
        return False

    baseAir.logWarn(f'kan_xiaoshuo start')
    baseAir.updateStateKV(key_last_ts, time.time())
    ocrResList = baseAir.check_dialog(breakIfHitText=breakIfHitText)  # 关闭弹框

    # 检测 '一键领取' 按钮, 可能会识别为: '一键领取'/'一健领取'/'键建领取'
    pos, _, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'(.键领取|·健领取|.建领取)',
                                   prefixText='认真阅读.金.')
    baseAir.logWarn(f'kan_xiaoshuo 检测一键领取 ocrStr={baseAir.composeOcrStr(ocrResList)}')
    if baseAir.tapByTuple(pos):  # 直接点击,仅有toast提示结果而已
        ocrResList = baseAir.getScreenOcrResult()
    elif _dy_kan_xiaoshuo_liing_jinbi(baseAir):  # 检测抖音的看小说奖励
        ocrResList = baseAir.getScreenOcrResult()

    # 检测是否已完成看小说任务,若已完成则不用再读
    pos, _, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'任务完成')
    if not CommonUtil.isNoneOrBlank(pos) and pos[0] >= 800 and pos[1] >= 200:
        baseAir.logWarn(f'kan_xiaoshuo 今日阅读任务已完成,无需继续阅读')
        baseAir.updateStateKV(key, maxReadSec)
        baseAir.back_until_earn_page()  # 回到赚钱页面
        return True

    baseAir.forLoop(baseAir.swipeUp, times=round(random.random() * 5 + 1), sec=0, durationMs=1200)  # 上滑三次

    # 点击具体小说名, 跳转到小说阅读详情页面
    btnText: str = r'(?:每读\(0/\d+\)|\d\.\d分)'
    pos, _, ocrResList = _find_pos(baseAir, None, targetText=btnText, maxSwipeRetryCount=5)
    baseAir.tapByTuple(pos, sleepSec=3)  # 点击跳转到小说页面进行阅读

    keywordInNovelDetail: str = r'(书籍介绍|书籍简介|第.{1,7}章|弟.{1,7}草|第.{1,7}草|弟.{1,7}章|继续阅读下一页|下一章|左滑开始阅读|\d+.\d+%)'
    if not baseAir.check_if_in_page(keywordInNovelDetail, autoCheckDialog=True):
        baseAir.logError(f'kan_xiaoshuo 跳转小说阅读详情页失败,退出读小说')
        baseAir.back_until_earn_page()  # 回到赚钱页面
        return False

    baseAir.check_dialog(breakIfHitText=keywordInNovelDetail)  # 偶尔会有作者发放的红包金币, 点击立即领取即可
    baseAir.swipeLeft()  # 首次阅读时会有引导提示, 左滑一次可以关闭, 即使没有引导,左滑也可以作为翻页操作
    baseAir.adbUtil.tap(500, 500, times=2)  # ks在引导页面无法通过左滑关闭,因此点击2次,建议人工处理

    # 开始阅读小说
    curNovelSecs = 0  # 当前小说已阅读时长,单位:s
    while True:
        startTs = time.time()
        baseAir.sleep(2)
        ocrResList = baseAir.check_dialog(breakIfHitText=keywordInNovelDetail, canDoOtherAction=True)  # 检测是否有红包或弹框
        baseAir.logWarn(f'kan_xiaoshuo 阅读小说检测 已读{curNovelSecs}秒: {baseAir.composeOcrStr(ocrResList)}')

        # 可能误点广告, 广告又刚好是小说app,因此需要特别剔除
        pos, _, _ = _find_pos(baseAir, ocrResList, targetText=r'(应用名称.*开发者|应用名.*版本号)')
        if not CommonUtil.isNoneOrBlank(pos):
            baseAir.logWarn(f'kan_xiaoshuo 检测到应用名称,尝试返回一次')
            baseAir.back_until(targetText=None, maxRetryCount=1)

        baseAir.sleep(minSec=2, maxSec=4)  # 随机读一会

        # 解锁章节后继续阅读
        pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText='立即解锁章节')
        sec = time.time() - startTs
        if baseAir.tapByTuple(pos) and not baseAir.check_if_in_page(targetText=keywordInNovelDetail,
                                                                    ocrResList=None,
                                                                    autoCheckDialog=False):
            ocrResList = None
            baseAir.continue_watch_ad_videos(breakIfHitText=keywordInNovelDetail)

        if baseAir.check_if_in_earn_page(ocrResList=ocrResList):
            baseAir.logWarn(f'kan_xiaoshuo fail 当前已回到赚钱任务页面,退出看小说任务')
            return True

        if baseAir.check_if_in_page(targetText=keywordInNovelDetail, ocrResList=ocrResList):
            baseAir.swipeLeft(maxY=500)  # 左滑到下一页面
        else:
            baseAir.logWarn(f'kan_xiaoshuo 当前已不在小说页面,可能跳转了新页面,尝试返回')
            if not baseAir.back_until(targetText=keywordInNovelDetail, maxRetryCount=3):
                baseAir.logWarn(f'kan_xiaoshuo 当前未能返回小说页面,退出循环')
                break

        # 若已达到阅读时长要求,则退出当前小说的阅读返回小说首页
        curNovelSecs = round(curNovelSecs + sec, 1)
        if curNovelSecs >= eachNovelSec:
            baseAir.logWarn(f'kan_xiaoshuo 已达到阅读时长 {curNovelSecs}, eachNovelSec={eachNovelSec}')
            # 抖音需要自己点击金币,在弹框中选择 "领取金币", 快手不需要
            ocrResList = baseAir.getScreenOcrResult(toY=400, fromX=400)
            pos, _, _ = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'\d+金.')
            if baseAir.tapByTuple(pos):
                for _ in range(10):
                    pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText=r'(领取金.|去领取)',
                                                   prefixText=r'(阅读赚金.|看小说赚金.)')
                    baseAir.logWarn(f'kan_xiaoshuo 检测领取金币 ocrStr2={baseAir.composeOcrStr(ocrResList)}')
                    if baseAir.tapByTuple(pos):  # 若可以领金币,则会弹出 "我知道了" 弹框
                        baseAir.check_dialog(canDoOtherAction=True, breakIfHitText='阅读赚金.')
                    else:
                        break

            baseAir.logWarn(f'kan_xiaoshuo 尝试返回到earn页面, 并检测加入书架等弹框')
            baseAir.back_until(targetText=itemBtnText, maxRetryCount=1)
            # 可能底部会弹出 '加入书架' 弹框, 点击加入,弹框消失后会自动返回一次, 有可能是居中弹框
            pos, _, ocrResList = baseAir.findTextByOCR('^加入书架$', prefixText='^暂不加入$', maxSwipeRetryCount=1)
            if not baseAir.tapByTuple(baseAir.calcCenterPos(pos)):
                pos, _, _ = baseAir.findTextByCnOCRResult(cnocr_result=ocrResList, targetText=r'^取消$',
                                                          prefixText='喜欢这本书就加入书架吧')
                baseAir.tapByTuple(baseAir.calcCenterPos(pos))  # 取消加入书架, 会回到书籍首页
            else:
                pos, _, _ = baseAir.findTextByCnOCRResult(cnocr_result=ocrResList,
                                                          targetText='喜欢这本书的用户也喜欢')
                if not CommonUtil.isNoneOrBlank(pos):
                    baseAir.closeDialog()  # 关闭弹框后会自动回到小说列表首页
            break

    # 阅读结束, 返回到页面最开头看下是否有 '一键领取' 金币选项
    hasReadSecs = hasReadSecs + curNovelSecs
    baseAir.updateStateKV(key, hasReadSecs)
    baseAir.forLoop(baseAir.swipeDown, times=5, sec=0)
    pos, ocrStr, ocrResList = _find_pos(baseAir, None, targetText=r'(.*键领取|·健领取|.建领取|键领取)',
                                        prefixText='认真阅读.金.')
    baseAir.logWarn(f'kan_xiaoshuo end 再次检测一键领取 pos={pos},ocrStr3={ocrStr}')
    baseAir.tapByTuple(pos)  # 直接点击,仅有toast提示结果而已
    baseAir.back_until_earn_page()  # 返回到去赚钱页面
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kanshipin_fanbei(baseAir: AbsBaseAir4Android, ocrResList: list,
                     breakIfHitText: str = None, fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """ 查看 '去赚钱' 页面是否有金币翻倍特权 """
    key = 'kanshipin_fanbei_ts'  # 上次尝试翻倍的时间戳,单位: s
    minDuration = 10 * 60  # 两次翻倍之间的最小间隔,单位:s

    if time.time() - baseAir.getStateValue(key, 0) <= minDuration:
        return False

    targetText: str = r'^点击翻倍$'  # 翻倍按钮名称
    prefixText: str = r'^开启看视频.*翻倍特权'  # 翻倍按钮前方需存在的文本
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList=ocrResList, targetText=targetText, prefixText=prefixText,
                               fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        baseAir.updateStateKV(key, time.time())
        baseAir.logWarn(f'kanshipin_fanbei end success=,ocrStr={ocrStr}')
        return True
    return False
