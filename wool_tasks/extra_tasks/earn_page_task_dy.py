# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import re
from typing import Union

from airtest.core.api import *

from base.TaskManager import taskWrapper, TaskLifeCycle
from util.CommonUtil import CommonUtil
from wool_tasks.base_airtest_4_android_impl import AbsBaseAir4Android

"""
赚钱页面任务分解
要求当前已在赚钱页面才触发相关方法
"""

__tag = 'earn_page_action_dy'


def _find_pos(baseAir: AbsBaseAir4Android, ocrResList: Union[list, None],
              targetText: str, prefixText: str = None, subfixText: str = None,
              fromX: int = 0, fromY: int = 0, height: int = 0,
              maxDeltaX: int = 0, maxDeltaY: int = 0, appendStrFlag: str = ' ',
              maxSwipeRetryCount: int = 1) -> tuple:
    """
    :param maxDeltaY: 匹配到的文本允许的最大高度差, 此处单行文本计为70像素
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
def qiandao(baseAir: AbsBaseAir4Android, ocrResList: list,
            breakIfHitText: str = None, fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy: '来赚钱' -> 日常任务 '签到'
    """
    title: str = r'签到'
    subTitle: str = r'连续签到\d+天'
    targetText: str = subTitle
    key_can_do = f'qiandao_state_{__tag}'
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=targetText, prefixText=title,
                                        fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        _, earnKeyword = baseAir.get_earn_monkey_tab_name()
        baseAir.check_dialog(breanIfHitText=earnKeyword)
        baseAir.updateStateKV(key_can_do, False)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def guangjie(baseAir: AbsBaseAir4Android, ocrResList: list,
             breakIfHitText: str = None, fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy '来赚钱' -> '逛街赚钱' 每天可以做10次, 有些可以20次
    标题: '逛街领金币'
         '浏览低价商品领金币完成0/10'
    按钮: '去逛街'

    标题: '逛街赚钱'
         '低价好物等你挑,02:04后浏览还可得金币,下单再得海量金币,每日可完成3/10次'  --> 多行, 当前无金币奖励的情况
          '浏览低价商品60秒即得189金币,下单再得海量金币,每日可完成3/10次'  --> 多行, 当前有金币奖励的提示语
    按钮: '去逛街'
    """
    minDurationSec: int = 5 * 60  # 连续两次逛街之间的时间间隔,单位: s
    key_last_ts = f'guangjie_ts_{__tag}'  # 上一次逛街的时间戳,单位:s
    key_rest_count = f'guangjie_rest_count_{__tag}'  # 剩余逛街次数
    rest_count: int = baseAir.getStateValue(key_rest_count, 10)
    lastTs = baseAir.getStateValue(key_last_ts, 0)
    curTs = time.time()
    if rest_count < 0:
        baseAir.logWarn(f'逛街失败, 剩余可逛次数为: {rest_count}')
        return False

    btnText: str = r'去逛街'  # 按钮名称,用于跳转到逛街页面
    title: str = r'(.街赚钱|.街领金.)'  # 逛街item的标题 逛街偶尔会识别为 狂街 迁街
    subTitle: str = r'(\d{1,2}/\d{1,2})'  # 逛街item的子标题,用于获取可完成次数
    minSecEachTime: int = 90  # 每次浏览的时长,页面要求90s左右,增加加载时长等因素,留10%左右的冗余量

    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=btnText, subfixText=subTitle,
                                        prefixText=title, fromX=fromX, fromY=fromY)
    if CommonUtil.isNoneOrBlank(pos):
        baseAir.logWarn(f'未找到逛街赚钱按钮,ocrStr={ocrStr}')
        return False

    # 检测当前是否有金币奖励,并重置时间戳
    pattern = re.compile(r'(\d{2}):(\d{2})后浏览')
    result = pattern.findall(ocrStr)
    if not CommonUtil.isNoneOrBlank(result):
        minutes = CommonUtil.convertStr2Int(result[0][0], 0)
        secs = minutes * 60 + CommonUtil.convertStr2Int(result[0][1], 0)
        lastTs = lastTs + minDurationSec - secs
        baseAir.logWarn(f'当前逛街浏览商品暂无金币奖励,下次再试 {result},secs={secs}秒')
        baseAir.updateStateKV(key_last_ts, lastTs)
        return False

    # 检测要浏览的时长
    pattern = re.compile(r'浏览.*(\d{2,3})秒.*')
    result = pattern.findall(ocrStr)
    if CommonUtil.isNoneOrBlank(result):
        baseAir.logWarn(f'当前逛街浏览商品暂无金币奖励,下次再试 {result}')
        return False
    else:
        secs = max(int(result[0]), 60)
    minSecEachTime = max(int(secs), minSecEachTime)
    baseAir.logWarn(f'可逛街浏览低价商品获得金币,本次至少需要浏览 {secs} 秒, 最终设定 {minSecEachTime}')

    # 点击'去逛街' 跳转商品浏览页面
    completeCount, totalCount = baseAir.get_rest_chance_count(title=title, subTitle=subTitle, cnocr_result=ocrResList)
    if totalCount > 0:
        baseAir.logWarn(f'逛街赚金币,今日已完成{completeCount}/{totalCount}')
        baseAir.updateStateKV(key_rest_count, totalCount - completeCount)

    if completeCount >= totalCount > 0:
        baseAir.logWarn(f'今日逛街赚金币活动均已完成,无需再试')
        return False

    # 点击 '去逛街' 按钮,跳转到商品浏览界面
    if not baseAir.tapByTuple(pos, sleepSec=5):
        baseAir.logWarn(f'去逛街赚钱 失败, 未找到按钮,已完成次数:{completeCount}/{totalCount}')
        return False

    baseAir.sleep(10)
    startTs: float = time.time()
    baseAir.check_dialog(needSwipeUp=True, breakIfHitText=breakIfHitText, guangjie_secs=secs)
    baseAir.updateStateKV(key_last_ts, curTs)
    totalSec: float = time.time() - startTs  # 本次已浏览的时长,单位: s
    maxTotalSec: float = minSecEachTime * 1.2
    swipeUp: bool = True
    while totalSec <= 2 * minSecEachTime:
        sec = baseAir.sleep(minSec=2, maxSec=5)
        totalSec = totalSec + sec
        if swipeUp:
            baseAir.swipeUp(durationMs=2000)  # 上滑
        else:
            baseAir.swipeDown(durationMs=2000)  # 下滑
        swipeUp = not swipeUp

        restSecs: float = maxTotalSec - (time.time() - startTs)
        beyondMaxSecs: bool = restSecs <= 0
        ocrResList = baseAir.check_dialog(canDoOtherAction=True, needSwipeUp=True, breakIfHitText=breakIfHitText,
                                          maxTotalSec=restSecs, guangjie_secs=secs)

        if totalSec > minSecEachTime or beyondMaxSecs:
            if baseAir.back_until(targetText=breakIfHitText, ocrResList=ocrResList, maxRetryCount=1,
                                  autoCheckDialog=True, needSwipeUp=True):
                return True

            # 可能返回失败
            pos, _, ocrResList = baseAir.findTextByOCR(targetText=r'(^继续完成$|^继续观看$)', prefixText='坚持退出',
                                                       maxSwipeRetryCount=1, fromY=300)
            if beyondMaxSecs:  # 已超过最大时长
                pos, _, _ = baseAir.findTextByCnOCRResult(cnocr_result=ocrResList, targetText='坚持退出',
                                                          prefixText=r'(^继续完成$|^继续观看$)')
                baseAir.tapByTuple(baseAir.calcCenterPos(pos))  # 坚持退出
                return True
            else:
                success = baseAir.tapByTuple(baseAir.calcCenterPos(pos))
                if success:  # 尚未完成浏览任务, 额外浏览10s
                    totalSec = totalSec - 10
                    baseAir.swipeUp(durationMs=1500)  # 上滑
                else:
                    return True
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def search(baseAir: AbsBaseAir4Android, ocrResList: list,
           breakIfHitText: str = None, fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy '来赚钱' -> '搜索赚金币'
    """
    key_rest_chance = f'key_rest_search_chance_{__tag}'  # 剩余有奖励的搜索次数
    count: int = baseAir.getStateValue(key_rest_chance, 5)  # 可搜索次数
    if count <= 0:
        return False

    titlePattern: str = r'^搜索(.*?)赚金.'
    subTilePattern: str = r'(\d{1,2}/\d{1,2})'
    btnText: str = '去搜索'

    # 从 '来赚钱' 页面跳转搜索入口页, 也就是首页
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=btnText, prefixText=titlePattern,
                                        subfixText=subTilePattern, fromX=fromX, fromY=fromY)
    if not baseAir.tapByTuple(pos):
        return False

    # 在首页进行图片匹配搜索入口
    pos = baseAir.exists(
        Template(r"dyjsb/tpl1683642143406.png", record_pos=(0.44, -0.894), resolution=(1080, 2340)))
    if not pos or not baseAir.adbUtil.tapByTuple(pos):  # 跳转失败则返回赚钱页面
        baseAir.back_until_info_stream_page()
        baseAir.goto_home_earn_tab()
        return False

    # 检测还有多少次搜索机会
    ocrResList = baseAir.getScreenOcrResult(toY=800)
    completeCount, totalCount = baseAir.get_rest_chance_count(title='搜索', subTitle=r'已完成(\d+/\d+)',
                                                              cnocr_result=ocrResList)
    if totalCount > 0:
        count = totalCount - completeCount
        baseAir.updateStateKV(key_rest_chance, count)
    baseAir.logWarn(f'dy search count={count},progress={completeCount}/{totalCount}')
    if count < 0:
        return True

    # 预设的搜索关键字
    keyword_arr = ['云韵', '美杜莎', '焰灵姬', '绯羽怨姬', '萧薰儿', '快雪时晴', '霁无暇', '明珠夫人', '潮女妖', '紫女',
                   'Flutter', 'Android', 'Binder', 'Jetpack', 'Compose',
                   'Espresso', 'AIDL', 'ARouter', 'transformer', 'hilt',
                   '组件化', '插件化', 'threadLocal', 'CAS', 'AQS']
    count = min(count, len(keyword_arr))

    # 确定搜索词, dy要求每次搜索词都不同,可搜索10次
    for i in range(count):
        # 可能会弹出 添加搜索框到桌面 等弹框
        baseAir.check_dialog(canDoOtherAction=True, breakIfHitText=breakIfHitText)

        index = i % len(keyword_arr)
        keyword = keyword_arr[index]
        baseAir.search_by_input(keyword, viewSec=20)

        # 顶部搜索栏的清空按钮
        hit = False
        pos = baseAir.exists(
            Template(r"dyjsb/tpl1683642926933.png", record_pos=(0.294, -0.898), resolution=(1080, 2340)))
        if pos:
            baseAir.tapByTuple(pos)  # 清空,光标自动定位到输入框
            hit = True

        if not hit:  # 未找到清空按钮,则直接通过坐标定位到输入框
            # 1080x2340 手机的顶部搜索框中心位置为: 500,200
            # 得到相对位置为: 500/1080=0.4629   185/2340=0.0791
            baseAir.logWarn('未找到搜索框的清空按钮, 直接通过坐标定位到搜索框')
            baseAir.tapByTuple(baseAir.convert2AbsPos(0.4629, 0.0791))  # 定位到搜索框, 重新进行下一次输入

    # 搜索完成
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def rexiao_baopin(baseAir: AbsBaseAir4Android, ocrResList: list,
                  breakIfHitText: str = None, fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题:  '逛热销爆品赚金币'
    子标题: '浏览180s得305金币'
    上述两行文本单行大概70像素, 两行总高度大概140像素
    按钮: '赚金币'
    跳转到爆品页面后, 需要一直滑动才会计时
    """
    key_consumed = f'rexiao_baopin_consumed_{__tag}'
    consumed: bool = baseAir.getStateValue(key_consumed, False)  # 是否已浏览过
    if consumed:
        return False

    btnText: str = r'(赚金币|去抢购)'  # 按钮名称,用于跳转到逛街页面
    title: str = r'逛热销爆品'
    subTitle: str = r'浏览(\d+)[秒s].*[赚得].*'
    targetText: str = subTitle
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=targetText,
                                        prefixText=title, fromX=fromX, fromY=fromY, maxDeltaY=140)
    if CommonUtil.isNoneOrBlank(pos):
        return False

    # 检测要浏览的时长
    pattern = re.compile(subTitle)
    result = pattern.findall(ocrStr)
    secs: int = 60  # 需要浏览的时长
    if not CommonUtil.isNoneOrBlank(result):
        secs = max(int(result[0]), secs)
    secs = int(1.1 * secs)  # 额外冗余10%

    baseAir.tapByTuple(pos)  # 点击跳转到浏览爆款页面
    baseAir.sleep(5)
    targetText: str = r'超值爆款'  # 超值爆款划算购
    ocrResList = baseAir.getScreenOcrResult(toY=1000)
    if not baseAir.check_if_in_page(targetText=targetText, ocrResList=ocrResList):
        baseAir.logWarn(f'当前未在超值爆款页面,返回上一页: {baseAir.composeOcrStr(ocrResList)}')
        baseAir.back_until(targetText=breakIfHitText, maxRetryCount=3)
        return True

    baseAir.check_dialog(breakIfHitText=breakIfHitText)
    totalSecs: int = 0  # 已浏览时长
    swipeUp: bool = True
    cnt = 0
    while totalSecs <= secs:
        if swipeUp:
            baseAir.swipeUp(durationMs=2000)
        else:
            baseAir.swipeDown(durationMs=2000)

        # 隔一段时间检测一次弹框
        cnt = (cnt + 1) % 10
        if cnt == 0:
            baseAir.check_dialog(breakIfHitText=breakIfHitText)

        swipeUp = not swipeUp
        baseAir.sleep(0.5)
        totalSecs += 2
    baseAir.updateStateKV(key_consumed, True)
    baseAir.back_until(targetText=breakIfHitText, maxRetryCount=3)
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def liulan_baokuan(baseAir: AbsBaseAir4Android, ocrResList: list,
                   breakIfHitText: str = None, fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '浏览爆款赚金币'
         '浏览爆款得金币'
         '逛热销爆品赚金币'

    子标题: '浏览180s得305金币'
          '浏览120秒最高得305金币,已完成0/10'

    按钮: '赚金币'  '去抢购'
    """
    key_consumed = f'liulan_baokuan_consumed_{__tag}'
    consumed: bool = baseAir.getStateValue(key_consumed, False)  # 是否已浏览过
    if consumed:
        return False

    btnText: str = r'(赚金币|去抢购)'  # 按钮名称,用于跳转到逛街页面
    title: str = r'浏览爆款.金币'
    subTitle: str = r'浏览(\d+)[秒s].*[赚得].*'  # ocr时subTile不一定是在btnText之后,谨慎使用
    targetText: str = subTitle
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=targetText,
                                        prefixText=title, fromX=fromX, fromY=fromY, maxDeltaY=140)
    if CommonUtil.isNoneOrBlank(pos):
        return False

    # 检测要浏览的时长
    pattern = re.compile(subTitle)
    result = pattern.findall(ocrStr)
    secs: int = 20  # 需要浏览的时长
    if not CommonUtil.isNoneOrBlank(result):
        secs = max(int(result[0]), secs)
    secs = int(1.1 * secs)  # 额外冗余10%

    baseAir.tapByTuple(pos, sleepSec=10)  # 点击跳转到浏览爆款页面
    ocrResList = baseAir.getScreenOcrResult(toY=1000)
    if baseAir.check_if_in_earn_page(ocrResList=ocrResList):
        baseAir.logWarn(f'当前未跳转到新页面')
        return True

    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'点击领取')
    if baseAir.tapByTuple(pos):  # 尝试领取奖励
        ocrResList = baseAir.getScreenOcrResult(toY=1000)

    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'(浏览.金币|上滑继续浏览)')
    if baseAir.tapByTuple(pos):  # 尝试浏览赚金币
        totalSecs: int = 0  # 已浏览时长
        while totalSecs <= secs:
            baseAir.swipeUp(durationMs=3000)
            totalSecs += 3
        baseAir.updateStateKV(key_consumed, True)
    baseAir.back_until(targetText=breakIfHitText, maxRetryCount=3)
    return True


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def wanan_xiaodao(baseAir: AbsBaseAir4Android, ocrResList: list,
                  breakIfHitText: str = None, fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy: 标题: '晚安小岛'  按钮: '去小岛'
        副标题: '和朋友说晚安领金币'
        20:00~6:00 可执行
    """
    key_consumed = f'wanan_xiaodao_consumed_{__tag}'
    consumed: bool = baseAir.getStateValue(key_consumed, False)  # 是否已浏览过
    if consumed:
        return False

    lt = time.localtime()
    hour = lt.tm_hour
    if hour < 20 or hour > 6:
        return False

    title: str = r'晚安小岛'
    targetText: str = r'去小岛'
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=targetText,
                                        prefixText=title, fromX=fromX, fromY=fromY)
    if not baseAir.tapByTuple(pos, sleepSec=6):
        return False

    ocrResList = baseAir.getScreenOcrResult(fromY=800)
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=r'我睡觉了',
                                        prefixText=r'我的日常', fromX=800)
    baseAir.updateStateKV(key_consumed, True)
    if baseAir.tapByTuple(pos, sleepSec=5):
        # 会弹框选择此刻状态
        ocrResList = baseAir.getScreenOcrResult(fromY=800)
        pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=r'(美滋滋|充实|失眠中|好梦|平静|疲惫)',
                                            prefixText=r'此刻状态', fromX=800)
        if baseAir.tapByTuple(pos):
            pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=r'发布动态',
                                                prefixText=r'此刻状态', fromX=800)
            baseAir.tapByTuple(pos, sleepSec=5)
        baseAir.closeDialog()  # 关闭可能弹出的祝福卡弹框
        baseAir.check_dialog()

    baseAir.back_until(targetText=breakIfHitText, maxRetryCount=3)
    return True
