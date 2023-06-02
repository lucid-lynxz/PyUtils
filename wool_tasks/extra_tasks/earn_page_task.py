# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import random
import re
import time
from typing import Union

from base.TaskManager import taskWrapper, TaskLifeCycle
from util.CommonUtil import CommonUtil
from wool_tasks.base_airtest import AbsBaseAir

"""
赚钱页面任务分解
要求当前已在赚钱页面才触发相关方法
"""

__tag = 'earn_page_action'


def _find_pos(baseAir: AbsBaseAir, ocrResList: Union[list, None], targetText: str, prefixText: str = None,
              fromX: int = 0, fromY: int = 0, height: int = 0, appendStrFlag: str = ' ',
              maxSwipeRetryCount: int = 1) -> tuple:
    """
    返回tuple:
        元素0: 按钮位置tuple
        元素1: ocr识别文本字符串
        元素2: 完整的cnocr识别结果list, 若入参 ocrResList 非空,则返回的是入参值
    """
    if CommonUtil.isNoneOrBlank(ocrResList):
        pos, ocrStr, ocrResList = baseAir.findTextByOCR(targetText=targetText, prefixText=prefixText,
                                                        appendStrFlag=appendStrFlag,
                                                        fromX=fromX, fromY=fromY, height=height,
                                                        maxSwipeRetryCount=maxSwipeRetryCount)
    else:
        pos, ocrStr, _ = baseAir.findTextByCnOCRResult(ocrResList, targetText=targetText, prefixText=prefixText,
                                                       appendStrFlag=appendStrFlag, fromX=fromX, fromY=fromY)
    return baseAir.calcCenterPos(pos), ocrStr, ocrResList


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def dao_fandian_ling_fanbu(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
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

    titlePattern: str = r'到.*点领饭补'  # 去赚钱页面的领取饭补item标题内容
    subTilePattern: str = r'(错过饭点也能领.*点击立得|明天继续领饭补)'  # 子标题内容
    btnText: str = r'(^去查看$|^去领取$)'  # 取赚钱页面的领取饭补按钮名称
    btnText4Fanbu: str = r'领取饭补\d+金.'  # 在饭补页面,底部领取饭补按钮名称
    title4Fanbu: str = r'(到点领.*饭补金.|领.*补贴)'  # 饭补页面顶部标题,用于判断是否跳转成功
    _, earnPageKeyWord = baseAir.get_earn_monkey_tab_name()

    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, btnText, prefixText=titlePattern, fromX=fromX, fromY=fromY)
    baseAir.tapByTuple(pos)  # 尝试跳转到领取饭补页面
    if baseAir.check_if_in_page(targetText=earnPageKeyWord, autoCheckDialog=False):  # 跳转是失败,当前仍在赚钱任务页面
        baseAir.logWarn(f'当前仍在earn页面,领饭补失败 {ocrStr}')
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
    if baseAir.check_if_in_page(targetText=title4Fanbu, autoCheckDialog=False):
        pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText='^看直播.?$', prefixText=title4Fanbu)
        if baseAir.tapByTuple(pos):
            pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText='^看直播.?$', prefixText=title4Fanbu)
            if CommonUtil.isNoneOrBlank(pos):  # 跳转成功
                baseAir.kan_zhibo_in_page(count=10, max_sec=30, autoBack2Home=False)
    baseAir.updateStateKV(key, False)
    baseAir.back_until_earn_page()
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def search_ks(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
              fromX: int = 0, fromY: int = 0) -> bool:
    """
    '去赚钱' -> '搜索 "xxx" 赚金币' 可能没有中间的双引号部分
    每次要求搜索的关键字可能有有要求, 因此需要提取ocr结果字符串进行提取
    """
    if baseAir.pkgName != 'com.kuaishou.nebula':
        return False

    titlePattern: str = r'\s*搜索(.*?)赚金.'
    subTilePattern: str = r'\s*搜索.*已完成(\d/\d )'
    btnText: str = '去搜索'

    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=btnText, prefixText=titlePattern,
                                        fromX=fromX, fromY=fromY)
    if CommonUtil.isNoneOrBlank(pos):
        return False

    # 预设的搜索关键字
    keyword_arr = ['云韵', '美杜莎', '焰灵姬', '绯羽怨姬',
                   'flutter', 'android binder', 'jetpack compose',
                   'espresso', 'aidl', 'arouter', 'transformer']

    pattern = re.compile(titlePattern)
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

    baseAir.back_until_earn_page()
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kan_zhibo(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
              fromX: int = 0, fromY: int = 0) -> bool:
    """
    '去赚钱' -> '看直播得3000金币'
    ks可以看6个, dy可以看10个
    """
    key = 'kan_zhibo'  # 是否已完成
    if baseAir.getStateValue(key, False):
        return False

    titlePattern: str = r'看直播.*金.'  # 赚钱任务页面中的看直播item标题
    subTilePattern: str = r'单日最高可得.*奖励.*(\d+/\d+ )'  # 赚钱任务的看直播item子标题
    btnText: str = '领福利'  # 赚钱页面的看直播按钮名称
    zhiboHomePageTitle: str = r'看直播领金.'  # 直播列表首页的标题名,用于判断是否跳转到直播详情成功

    pos, ocr_result, ocrResList = _find_pos(baseAir=baseAir, ocrResList=ocrResList, targetText=btnText,
                                            prefixText=titlePattern, fromX=fromX, fromY=fromY)
    if CommonUtil.isNoneOrBlank(pos):
        return False

    # 计算剩余次数
    completeCount, totalCount = baseAir.get_rest_chance_count(title=titlePattern, subTitle=subTilePattern,
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
def jinbi_gouhuasuan_qiandao(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                             fromX: int = 0, fromY: int = 0) -> bool:
    """
    '去赚钱'  -> '金币购划算' -> '今日签到' 每天可以签到一次 , '看直播可领' 300金币, 看三个直播视频
    :param targetText1: '金币购划算' 入口名称
    :param targetText2: '签到' 按钮名称
    :param kanzhiboText: '看直播可领' 按钮名称
    """
    func_name = 'jinbi_gouhuasuan_qiandao'
    if not baseAir.getStateValue(func_name, True):
        return False

    targetText1: str = r'^金.购划算$'
    targetText2: str = r'^今日签到$'
    kanzhiboText: str = r'^看直播可领$'
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=targetText1,
                                        fromX=fromX, fromY=fromY)
    if not baseAir.tapByTuple(pos):
        return False

    baseAir.sleep(3)
    for i in range(3):  # 今日签到
        pos, ocrStr, ocrResList = baseAir.findTextByOCR(targetText=targetText2, height=800, maxSwipeRetryCount=1)
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
    pos, ocrStr, ocrResList = _find_pos(baseAir=baseAir, ocrResList=ocrResList, targetText=kanzhiboText)
    if baseAir.tapByTuple(pos):
        baseAir.sleep(3)  # 可能会加载一下
        baseAir.kan_zhibo_in_page(count=3, max_sec=90, zhiboHomePageTitle='爆款好物')
    baseAir.updateStateKV(func_name, False)  # 一次性任务,每天跑一次即可
    baseAir.back_until(targetText=breakIfHitText)  # 返回去赚钱页
    baseAir.logWarn(f'jinbi_gouhuasuan_qiandao end ocrStr: {ocrStr}')
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kan_xiaoshuo(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0) -> bool:
    """
    dy: '来赚钱' -> '看小说赚金币' -> '看更多'
    """
    key = 'kan_xiaoshuo_secs'
    key_last_ts = 'kan_xiaoshuo_last_ts'  # 上一次看小说的时间,单位:s

    maxReadSec: int = 30 * 60  # 总共最多只需要看30min即可
    minDuration: int = 5 * 60  # 两次看小说之间的时间间隔, 单位:s
    hasReadSecs = baseAir.getStateValue(key, 0)  # 已读时长,单位:s
    lastReadTs = baseAir.getStateValue(key_last_ts, 0)
    if hasReadSecs >= maxReadSec or time.time() - lastReadTs <= minDuration:
        return False

    itemBtnText: str = r'(^看小说$|^看更多$)'  # 跳转到看小说首页的按钮正则名称
    itemTitle: str = r'[看|读]小说.*?赚金.'  # 看小说item信息标题
    eachNovelSec: float = 5 * 60  # 每本小说阅读时长,单位:s
    earnName, earnKeyword = baseAir.get_earn_monkey_tab_name()
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=itemBtnText, prefixText=itemTitle,
                                        fromX=fromX, fromY=fromY)
    if not baseAir.tapByTuple(pos):  # 跳转到读小说页面
        baseAir.logError(f'kan_xiaoshuo 未找到按钮 {itemBtnText} {itemTitle},ocrStr={ocrStr}')
        return False

    if baseAir.check_if_in_page(earnKeyword):
        baseAir.logWarn(f'kan_xiaoshuo 跳转失败,当前仍在赚钱页面')
        return False

    baseAir.logWarn(f'kan_xiaoshuo start')
    baseAir.updateStateKV(key_last_ts, time.time())
    baseAir.check_dialog()  # 关闭弹框

    # 检测 '一键领取' 按钮
    pos, _, _ = _find_pos(baseAir, ocrResList=None, targetText=r'(^.键领取$|^·健领取$)', prefixText='^认真阅读.金.')
    baseAir.tapByTuple(pos)  # 直接点击,仅有toast提示结果而已
    baseAir.forLoop(baseAir.swipeUp, times=3, sec=0, durationMs=1200)  # 上滑三次
    # baseAir.check_dialog()

    # 点击具体小说名, 跳转到小说阅读详情页面
    btnText: str = r'(?:每读\(0/\d+\)|\d\.\d分)'
    pos, _, ocrResList = _find_pos(baseAir, None, targetText=btnText, maxSwipeRetryCount=5)
    baseAir.tapByTuple(pos, sleepSec=3)  # 点击跳转到小说页面进行阅读

    keywordInNovelDetail: str = r'(书籍介绍|第.{1,7}章|继续阅读下一页|\d+金.|下一章|左滑开始阅读)'
    if not baseAir.check_if_in_page(keywordInNovelDetail, autoCheckDialog=True):
        baseAir.logError(f'跳转小说阅读详情页失败,退出读小说')
        baseAir.back_until_earn_page()  # 回到赚钱页面
        return False

    baseAir.check_dialog(breakIfHitText=keywordInNovelDetail)  # 偶尔会有作者发放的红包金币, 点击立即领取即可
    baseAir.swipeLeft()  # 首次阅读时会有引导提示, 左滑一次可以关闭, 即使没有引导,左滑也可以作为翻页操作
    baseAir.adbUtil.tap(500, 500)  # ks在引导页面无法通过左滑关闭,因此点击一次

    # 开始阅读小说
    curNovelSecs = 0  # 当前小说已阅读时长,单位:s
    while True:
        startTs = time.time()
        ocrResList = baseAir.check_dialog(breakIfHitText=keywordInNovelDetail)  # 检测是否有红包或弹框
        baseAir.logWarn(f'阅读小说检测 已读{curNovelSecs}秒: {baseAir.composeOcrStr(ocrResList)}')
        baseAir.sleep(minSec=3, maxSec=6) + 1  # 随机读一会

        # 解锁章节后继续阅读
        pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText='立即解锁章节')
        sec = time.time() - startTs
        if baseAir.tapByTuple(pos) and not baseAir.check_if_in_page(targetText=keywordInNovelDetail,
                                                                    ocrResList=None,
                                                                    autoCheckDialog=False):
            ocrResList = None
            baseAir.continue_watch_ad_videos(breakIfHitText=keywordInNovelDetail)

        if baseAir.check_if_in_page(targetText=keywordInNovelDetail, ocrResList=ocrResList):
            baseAir.swipeLeft(maxY=500)  # 左滑到下一页面
        else:
            baseAir.logWarn(f'当前已不在小说页面,退出循环')
            break

        # 若已达到阅读时长要求,则退出当前小说的阅读返回小说首页
        curNovelSecs = round(curNovelSecs + sec, 1)
        if curNovelSecs >= eachNovelSec:
            baseAir.back_until(targetText=itemBtnText)
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
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=r'(^.键领取$|^·健领取$)', prefixText='^认真阅读赢金.')
    baseAir.tapByTuple(pos)  # 直接点击,仅有toast提示结果而已
    baseAir.back_until_earn_page()  # 返回到去赚钱页面
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def watch_ad_video(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                   fromX: int = 0, fromY: int = 0) -> bool:
    """
    ks: '去赚钱' -> '看视频得5000金币' 按钮 '领福利'
    dy: '来赚钱' -> '看广告赚金币' 按钮 '去领取' 每5min/20min可以看一次, 不一定
    """
    minDurationSec: int = 5 * 60  # 每5分钟可再次尝试看视频
    key = 'watch_ad_video'
    lastTs = baseAir.getStateValue(key, 0)  # 上一次观看视频广告的时间戳,单位:s
    curTs = time.time()
    if curTs - lastTs < minDurationSec:
        baseAir.logWarn('watch_ad_video fail as curTs=%s,lastTs=%s,min=%s' % (curTs, lastTs, minDurationSec))
        return False

    btnText: str = r'(^领福利$|^去领取$)'
    titleText: str = r'(^看视频得\d+金.|^看广告赚金.)'
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=btnText, prefixText=titleText,
                                        fromX=fromX, fromY=fromY)
    if not baseAir.tapByTuple(pos):
        return False

    # 可能跳转后无广告自动返回,此时也需要重新ocr
    if baseAir.check_if_in_earn_page(autoCheckDialog=False):
        return True

    baseAir.logWarn(f'watch_ad_video start')
    baseAir.continue_watch_ad_videos(breakIfHitText=titleText)  # 继续观看知道无法继续, 最终会返回到当前页面
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kanshipin_fanbei(baseAir: AbsBaseAir, ocrResList: list,
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
