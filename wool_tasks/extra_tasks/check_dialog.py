# !/usr/bin/env python3
# -*- coding:utf-8 -*-

from base.TaskManager import taskWrapper, TaskLifeCycle
from util.CommonUtil import CommonUtil
from wool_tasks.base_airtest import AbsBaseAir


def _find_pos(baseAir: AbsBaseAir, ocrResList: list, targetText: str, prefixText: str = None,
              fromX: int = 0, fromY: int = 0, appendStrFlag: str = ' ') -> tuple:
    """
    返回tuple:
        元素0: 按钮位置tuple
        元素1: ocr识别文本字符串
        元素2: 完整的cnocr识别结果list, 若入参 ocrResList 非空,则返回的是入参值
    """
    if CommonUtil.isNoneOrBlank(ocrResList):
        pos, ocrStr, ocrResList = baseAir.findTextByOCR(targetText=targetText, prefixText=prefixText,
                                                        appendStrFlag=appendStrFlag, maxSwipeRetryCount=1)
    else:
        pos, ocrStr, _ = baseAir.findTextByCnOCRResult(ocrResList, targetText=targetText, prefixText=prefixText,
                                                       appendStrFlag=appendStrFlag, fromX=fromX, fromY=fromY)
    return baseAir.calcCenterPos(pos), ocrStr, ocrResList


@taskWrapper('check_coin_dialog', taskLifeCycle=TaskLifeCycle.custom)
def check_contacts_update_dialog(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                                 fromX: int = 0, fromY: int = 0) -> bool:
    """
    检测版本更新弹框或者通讯录弹框,进行跳过
    """
    prefixText: str = r'(检测到更新|发现通讯录朋友)'
    targetText: str = r'(^以后再说|^拒绝$)'
    updateNowBtn: str = r'(^立即升级|^继续$)'

    pos, _, ocrResList = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText,
                                   fromX=fromX, fromY=fromY)

    success = baseAir.tapByTuple(pos)
    if success:
        baseAir.logWarn(f'check_contacts_update_dialog检测到更新/通讯录弹框,并已跳过')
    else:
        pos, _, _ = baseAir.findTextByCnOCRResult(cnocr_result=ocrResList, targetText=updateNowBtn)
        if not CommonUtil.isNoneOrBlank(pos):
            img_path = baseAir.saveScreenShot('check_contacts_update_dialog', autoAppendDateInfo=True)
            baseAir.logWarn(f'check_contacts_update_dialog检测到升级选项,img_path={img_path}')
            baseAir.closeDialog()
            return True
    return success


@taskWrapper('check_coin_dialog', taskLifeCycle=TaskLifeCycle.custom)
def gongxi_huode_manfe_hongbao(baseAir: AbsBaseAir, ocrResList: list,
                               breakIfHitText: str = None, fromX: int = 0, fromY: int = 0) -> bool:
    """恭喜获得免费红包 弹框, 无法通过返回取消"""
    targetText = r'点击立得奖励'
    prefixText = r'恭喜获得免费红包'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    pass


@taskWrapper('check_coin_dialog', taskLifeCycle=TaskLifeCycle.custom)
def check_sign(baseAir: AbsBaseAir, ocrResList: list,
               breakIfHitText: str = None, fromX: int = 0, fromY: int = 0) -> bool:
    """
    检测签到弹框
    """
    targetText: str = r'(^立即签到|^明天签到|^立即领取$|^开心收下|好的|^点击领取$|^我知道了)'
    prefixText: str = r'(领|天降红包|发放的红包|恭喜.*获得|今日可领|今日签到可领|明天可领|明日签到|每日签到|签到成功|连签\d天必得|签到专属福利|青少年模式|成长护航)'

    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper('check_coin_dialog', taskLifeCycle=TaskLifeCycle.custom)
def check_sign2(baseAir: AbsBaseAir, ocrResList: list,
                breakIfHitText: str = None, fromX: int = 0, fromY: int = 0) -> bool:
    # 可能会自动弹出签到提醒
    targetText: str = r'(邀请好友.*赚.*现金|打开签到提醒.*金.|签到专属福利|\d天必得.*金.)'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.logWarn(f'check_coin_dialog 关闭邀请好友/打开签到提醒等弹框')
        baseAir.closeDialog()
        return True
    return False


@taskWrapper('check_coin_dialog', taskLifeCycle=TaskLifeCycle.custom)
def remind_rest(baseAir: AbsBaseAir, ocrResList: list,
                breakIfHitText: str = None, fromX: int = 0, fromY: int = 0) -> bool:
    """ 夜间提醒休息弹框 """
    targetText = r'(^取消$|^退出$)'
    prefixText = r'(累了吧.*休息一下$|^猜你喜欢$)'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper('check_coin_dialog', taskLifeCycle=TaskLifeCycle.custom)
def kai_baoxiang(baseAir: AbsBaseAir, ocrResList: list,
                 breakIfHitText: str = None, fromX: int = 0, fromY: int = 0) -> bool:
    """ 点击开宝箱得金币logo """
    # 第一步尝试开宝箱
    name, keyword = baseAir.get_earn_monkey_tab_name()
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=r'(^开宝箱得金.)', prefixText=keyword,
                          fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper('check_coin_dialog', taskLifeCycle=TaskLifeCycle.custom)
def kai_baoxiang2(baseAir: AbsBaseAir, ocrResList: list,
                  breakIfHitText: str = None, fromX: int = 0, fromY: int = 0) -> bool:
    """宝箱开启过程检测"""
    targetText = r'(^宝箱开启中|^恭喜获得.*福袋)'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, fromX=fromX, fromY=fromY)
    if CommonUtil.isNoneOrBlank(pos):
        return False

    for _ in range(3):
        baseAir.sleep(2)
        pos, _, _ = _find_pos(baseAir, ocrResList=None, targetText=targetText, fromX=fromX, fromY=fromY)
        if CommonUtil.isNoneOrBlank(pos):
            break
    return True


@taskWrapper('check_coin_dialog', taskLifeCycle=TaskLifeCycle.custom)
def kai_baoxiang3(baseAir: AbsBaseAir, ocrResList: list,
                  breakIfHitText: str = None, fromX: int = 0, fromY: int = 0) -> bool:
    """宝箱开启结果检测"""
    targetText: str = r'(看.*视频.*\d+金.|看.*直播.*赚\d+金.)'
    prefixText: str = r'(宝箱|恭喜.*获得|明日签到|签到成功|本轮宝箱已开启)'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)
    if CommonUtil.isNoneOrBlank(pos):
        return False

    if baseAir.tapByTuple(pos):  # 持续观看广告视频,结束后自动返回当前页面
        baseAir.continue_watch_ad_videos(min_secs=90 if '直播' in ocrStr else 30, breakIfHitText=breakIfHitText)
    return True


@taskWrapper('check_coin_dialog', taskLifeCycle=TaskLifeCycle.custom)
def lingqu_jiangli(baseAir: AbsBaseAir, ocrResList: list,
                   breakIfHitText: str = None, fromX: int = 0, fromY: int = 0) -> bool:
    """宝箱开启结果检测"""
    targetText: str = r'(^领取奖励$|^继续观看)'
    prefixText: str = r'(再看.*获得|点击额外获取|看了这么久|关注一下|对这些直播感兴趣|下载并体验|打开并体验|营销推广|更多主播.*不容错过)'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)
    if CommonUtil.isNoneOrBlank(pos):
        return False

    if baseAir.tapByTuple(pos):  # 持续观看广告视频,结束后自动返回当前页面
        baseAir.continue_watch_ad_videos(min_secs=90 if '直播' in ocrStr else 30, breakIfHitText=breakIfHitText)
    return True
