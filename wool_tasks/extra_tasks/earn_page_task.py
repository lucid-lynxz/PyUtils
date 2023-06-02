# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import random
import re

from base.TaskManager import taskWrapper, TaskLifeCycle
from util.CommonUtil import CommonUtil
from wool_tasks.base_airtest import AbsBaseAir

"""
赚钱页面任务分解
要求当前已在赚钱页面才触发相关方法
"""


def _find_pos(baseAir: AbsBaseAir, ocrResList: list, targetText: str, prefixText: str = None,
              fromX: int = 0, fromY: int = 0, height: int = 0, appendStrFlag: str = ' ') -> tuple:
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
                                                        maxSwipeRetryCount=1)
    else:
        pos, ocrStr, _ = baseAir.findTextByCnOCRResult(ocrResList, targetText=targetText, prefixText=prefixText,
                                                       appendStrFlag=appendStrFlag, fromX=fromX, fromY=fromY)
    return baseAir.calcCenterPos(pos), ocrStr, ocrResList


@taskWrapper('earn_page_action', taskLifeCycle=TaskLifeCycle.custom)
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

    titlePattern: str = r'到.*点领饭补'  # 去赚钱页面的领取饭补item标题内容
    subTilePattern: str = r'(错过饭点也能领.*点击立得|明天继续领饭补)'  # 子标题内容
    btnText: str = r'(去查看|去领取|明天来领)'  # 取赚钱页面的领取饭补按钮名称
    btnText4Fanbu: str = r'领取饭补\d+金.'  # 在饭补页面,底部领取饭补按钮名称
    title4Fanbu: str = r'(到点领.*饭补金.|领.*补贴)'  # 饭补页面顶部标题,用于判断是否跳转成功
    _, earnPageKeyWord = baseAir.get_earn_monkey_tab_name()

    pos, _, ocrResList = _find_pos(baseAir, ocrResList, btnText, prefixText=titlePattern, fromX=fromX, fromY=fromY)
    baseAir.tapByTuple(pos)  # 尝试跳转到领取饭补页面
    if baseAir.check_if_in_page(targetText=earnPageKeyWord):  # 跳转是失败,当前仍在赚钱任务页面
        baseAir.logWarn(f'当前仍在earn页面,领饭补失败')
        return False

    # 尝试点击 '领取饭补42金币' 按钮
    baseAir.sleep(3)
    pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText=btnText4Fanbu, prefixText=title4Fanbu)
    if baseAir.tapByTuple(pos):
        baseAir.check_coin_dialog(breakIfHitText=title4Fanbu)  # 检测金币弹框,按需跳转查看视频,最后返回当前页面
        baseAir.sleep(2)  # 可能需要等待下, 下方的 '看视频'/'看直播'按钮才会显示

    # 检测是否还在饭补页面
    if not baseAir.check_if_in_page(targetText=title4Fanbu):
        baseAir.logWarn(f'当前已不在饭补页面,返回首页赚钱页面')
        if baseAir.check_if_in_page(targetText=earnPageKeyWord):
            return True

        baseAir.back2HomePage()  # 返回到首页
        baseAir.goto_home_sub_tab()  # 跳转到赚钱页面
        return True

    # 点击 '看视频' 按钮
    pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText='^看视频', prefixText=title4Fanbu)
    for _ in range(10):
        baseAir.tapByTuple(pos)
        # 此处不复用pos变量,避免需要重新ocr
        tempPos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText='^看视频', prefixText=title4Fanbu)
        if CommonUtil.isNoneOrBlank(tempPos):  # 跳转成功
            baseAir.continue_watch_ad_videos(breakIfHitText=title4Fanbu)
        else:  # 未跳转成功, 应该是不能再看了
            break

    # 点击 '看直播' 按钮
    if baseAir.check_if_in_page(targetText=title4Fanbu):
        pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText='^看直播.?$', prefixText=title4Fanbu)
        baseAir.tapByTuple(pos)
        pos, _, ocrResList = _find_pos(baseAir, ocrResList=None, targetText='^看直播.?$', prefixText=title4Fanbu)
        if CommonUtil.isNoneOrBlank(pos):  # 跳转成功
            baseAir.kan_zhibo_in_page(count=14, max_sec=30)
    else:
        baseAir.back2HomePage()  # 返回到首页
        baseAir.goto_home_sub_tab()  # 跳转到赚钱页面
    return True


@taskWrapper('earn_page_action', taskLifeCycle=TaskLifeCycle.custom)
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

    name, earnKeyword = baseAir.get_earn_monkey_tab_name()
    baseAir.back_until(targetText=earnKeyword)
    return True


@taskWrapper('earn_page_action', taskLifeCycle=TaskLifeCycle.custom)
def kan_zhibo(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
              fromX: int = 0, fromY: int = 0) -> bool:
    """
    '去赚钱' -> '看直播得3000金币'
    ks可以看6个, dy可以看10个
    """
    count: int = 1  # 总共需要看几次直播
    titlePattern: str = r'看直播.*金.'  # 赚钱任务页面中的看直播item标题
    subTilePattern: str = r'当日最高可得.*奖励.*(\d/\d )'  # 赚钱任务的看直播item子标题
    btnText: str = '领福利'  # 赚钱页面的看直播按钮名称
    zhiboHomePageTitle: str = r'看直播领金.'  # 直播列表首页的标题名,用于判断是否跳转到直播详情成功
    autoBack2Home: bool = True

    pos, ocr_result, ocrResList = _find_pos(baseAir=baseAir, ocrResList=ocrResList, targetText=btnText,
                                            prefixText=titlePattern, fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        baseAir.kan_zhibo_in_page(count=count, max_sec=90, zhiboHomePageTitle=zhiboHomePageTitle,
                                  autoBack2Home=autoBack2Home)
        name, earnKeyword = baseAir.get_earn_monkey_tab_name()
        baseAir.back_until(targetText=earnKeyword)
        return True
    else:  # 未找到按钮, 检查是否剩余次数
        return False


@taskWrapper('earn_page_action', taskLifeCycle=TaskLifeCycle.custom)
def jinbi_gouhuasuan_qiandao(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                             fromX: int = 0, fromY: int = 0) -> bool:
    """
    '去赚钱'  -> '金币购划算' -> '今日签到' 每天可以签到一次 , '看直播可领' 300金币, 看三个直播视频
    :param targetText1: '金币购划算' 入口名称
    :param targetText2: '签到' 按钮名称
    :param kanzhiboText: '看直播可领' 按钮名称
    """
    targetText1: str = r'^金.购划算$'
    targetText2: str = r'^今日签到$'
    kanzhiboText: str = r'^看直播可领$'
    back2Home: bool = False
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
            pos, _, _ = baseAir.findTextByCnOCRResult(cnocr_result=ocrResList, targetText=r'^明日签到$',
                                                      prefixText='订单')
            if CommonUtil.isNoneOrBlank(pos):
                baseAir.sleep(2)  # 额外等一会,可能是还没加载完成
            else:  # 已经签到过了
                break

    # 看直播可领300金币
    pos, ocrStr, ocrResList = baseAir.findTextByOCR(targetText=kanzhiboText, height=800, maxSwipeRetryCount=1)
    if baseAir.tapByTuple(baseAir.calcCenterPos(pos)):
        baseAir.sleep(3)  # 可能会加载一下
        baseAir.kan_zhibo_in_page(count=5, max_sec=100, zhiboHomePageTitle='爆款好物')
        pass

    baseAir.adbUtil.back()  # 返回去赚钱页
    baseAir.updateStateKV(key, True)
    if back2Home:
        baseAir.back2HomePage()
        baseAir.goto_home_information_tab()  # 返回首页
    baseAir.logWarn(f'jinbi_gouhuasuan_qiandao end success={success} {ocrStr}')
    return True
