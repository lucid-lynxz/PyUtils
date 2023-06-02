# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import re

from base.TaskManager import taskWrapper, TaskLifeCycle
from util.CommonUtil import CommonUtil
from wool_tasks.base_airtest import AbsBaseAir

"""
检测弹框
注意: 方法若需调用 check_if_in_page() 请将 autoCheckDialog 设置为 False,避免死循环
请将模态弹框检测方法放到前面
"""

__tag = 'check_dialog'


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


def _can_do_other_action(defaultValue: bool = True, **kwargs) -> bool:
    """
    除了关闭弹框外,是否还可以继续执行后续操作,比如:观看广告视频
    """
    return kwargs.get('canDoOtherAction', defaultValue)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def check_contacts_update_dialog(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
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
        pos, ocrStr, _ = baseAir.findTextByCnOCRResult(cnocr_result=ocrResList, targetText=updateNowBtn)
        if not CommonUtil.isNoneOrBlank(pos):
            baseAir.logWarn(f'check_contacts_update_dialog检测到升级选项,img_path={ocrStr}')
            baseAir.closeDialog()
            return True
    return success


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def faxian_tongxunlu_pengyou(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                             fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """发现通讯录朋友弹框2,无文字按钮关闭"""
    targetText = r'发现通讯录朋友'
    prefixText = r'朋友推荐'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685624986007.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def gongxi_huode_mianfei_hongbao(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """恭喜获得免费红包弹框, 无法通过返回取消"""
    targetText = r'点击立得奖励'
    prefixText = r'恭喜获得免费红包'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685624986007.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def search_kaqi_dignwei_fuwu(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                             fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """搜索时,可能会要求开启定位服务, 无法通过返回取消"""
    targetText = r'^以后再说$'
    prefixText = r'开启定位服务'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def gongxi_zhouzhou_zhuanjianbi(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """恭喜获得金币大礼包 周周赚金币弹框, 无法通过返回取消"""
    targetText = r'^点击领取金.$'  # '点击领取金币' '提现至微信秒到账'
    prefixText = r'周周赚金币'  # '超级星期五 周周赚金币'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685624986007.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def pk_jinbi(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
             fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    pk获得金币弹框, 无法通过返回取消
    标题: '你有588PK金币待领取'
         '点击即领,手慢无'
    按钮: '去领取'  右上角有关闭按钮
    """
    targetText = r'^点击即领.手慢.'
    prefixText = r'^你有\d+PK金币待领取$'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685198790981.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def fanqie_mianfei_xiaoshuo(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                            fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy 看小说弹出番茄免费小说弹框, 无法通过返回取消
    标题: '番茄免费小说'
         '今日可赚'
         '10000+金币'
    按钮: '去APP赚金币'  右上角有关闭按钮
    """
    targetText = r'^去APP赚金币'
    prefixText = r'^番茄免费小说'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685624986007.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def fanqie_mianfei_xiaoshuo2(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                             fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy 看小说弹出番茄免费小说弹框2
    标题: '去番茄小说读1分钟'
         '12888金币'
         '23:58:59 后过期'
    按钮: '立即下载'  右上角有关闭按钮
    """
    targetText = r'^去番茄小说读\d分钟'
    prefixText = r'^立即下载$'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685198790981.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def gognxi_huode_manjian_quanyi(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy 逛街赚金币 618弹框
    标题: '抖音618好物节'
         '恭喜获得满减权益'
         '25元'
         '每满150元可用' '11天后过期'
    按钮: '立即使用'
    下方有关闭按钮
    """
    targetText = r'^立即使用$'
    prefixText = r'^恭喜获得满减权益'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685624986007.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kan_xiaoshuo_tianjiang_hongbao(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                                   fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    看小说的天降红包,点击后会跳转视频播放页面
    """
    targetText: str = r'(^立即领取$|^领取$)'
    prefixText: str = r'(^领$|天降红包$|发放的红包$)'  # '天降红包' 偶尔会识别为:'女天降红包'

    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        if _can_do_other_action(**kwargs):
            baseAir.continue_watch_ad_videos(breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def check_sign(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
               fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    检测签到弹框
    """
    targetText: str = r'(^立即签到|^明天签到|^立即领取$|^领取$|^开心收下|^好的$|^点击领取$|^我知道了)'
    prefixText: str = r'(恭喜.*获得|今日可领|今日签到可领|明天可领|明日签到|每日签到|签到成功|连签\d天必得|签到专属福利|青少年模式|成长护航)'

    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def check_sign2(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    # 可能会自动弹出签到提醒
    targetText: str = r'(邀请好友.*赚.*现金|打开签到提醒.*金.|签到专属福利|\d天必得.*金.)'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.logWarn(f'check_dialog 关闭邀请好友/打开签到提醒等弹框')
        baseAir.closeDialog()
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def remind_rest(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """ 夜间提醒休息弹框 """
    targetText = r'(^取消$|^退出$)'
    prefixText = r'(累了吧.*休息一下$|^猜你喜欢$)'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def jixu_guankan(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    视频未观看结束就按下返回键,  弹出继续观看的弹框
    标题: '再看3s可领奖励'
         '+18金币'
    按钮: '继续观看'  '坚持退出' '换一个'

    形式2:
    标题: '再看6秒，可获得奖励'
    按钮: '继续观看' '放弃奖励' '换一个视频'
    """
    targetText: str = r'(^继续观看$)'
    prefixText: str = r'^再看(\d+).{1,2}可(领|获得)奖励'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)
    if CommonUtil.isNoneOrBlank(pos):
        return False

    # 获取需要观看的时长
    ptn = re.compile(prefixText)
    result = ptn.findall(ocrStr)
    secs: float = 0
    if not CommonUtil.isNoneOrBlank(result):
        secs = CommonUtil.convertStr2Float(result[0], 5)
    baseAir.logWarn(f'jixu_guankan secs={secs}, ocrStr={ocrStr}')

    if baseAir.tapByTuple(pos):
        baseAir.sleep(secs)
        if _can_do_other_action(**kwargs):
            baseAir.continue_watch_ad_videos(max_secs=90 if '直播' in ocrStr else 30, breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def zaikan_yige(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    视频播放完成,按下返回键后,弹出再看一个的弹框
    标题: '恭喜你一获得奖励'
         '继续观看视频最高得800金币'
    按钮: '再看一个' '坚持退出'
    """
    targetText: str = r'^再看一个$'
    prefixText: str = r'继续观看视频最高得\d+金.'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)

    # 持续观看广告视频,结束后自动返回当前页面
    if baseAir.tapByTuple(pos):
        baseAir.logWarn(f'zaikan_yige hit ocrStr:{ocrStr}')
        if _can_do_other_action(**kwargs):
            baseAir.continue_watch_ad_videos(max_secs=90 if '直播' in ocrStr else 30, breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def zaikan_yige02(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                  fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    视频播放完成,按下返回键后,弹出再看一个的弹框,第二种形式
    标题: '再看一个视频额外获得'
         '+18金币
    按钮: '领取奖励' '坚持退出'
    """
    targetText: str = r'^领取奖励$'
    prefixText: str = r'再看一个视频额外获得'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)

    # 持续观看广告视频,结束后自动返回当前页面
    if baseAir.tapByTuple(pos):
        baseAir.logWarn(f'zaikan_yige02 hit ocrStr:{ocrStr}')
        if _can_do_other_action(**kwargs):
            baseAir.continue_watch_ad_videos(max_secs=90 if '直播' in ocrStr else 30, breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def lingqu_jiangli(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                   fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """宝箱开启结果检测"""
    targetText: str = r'(^领取奖励$|^再看一个$)'
    prefixText: str = r'(再看.*获得|点击额外获取|看了这么久|恭喜.*获得|关注一下|对这些直播感兴趣|(下载|打开)并体验|营销推广|更多主播.*不容错过)'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)

    # 持续观看广告视频,结束后自动返回当前页面
    if baseAir.tapByTuple(pos):
        if _can_do_other_action(**kwargs):
            baseAir.continue_watch_ad_videos(max_secs=90 if '直播' in ocrStr else 30, breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kai_baoxiang(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """ 点击开宝箱得金币logo """
    # 第一步尝试开宝箱
    name, keyword = baseAir.get_earn_monkey_tab_name()
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=r'(^开宝箱得金.)', prefixText=keyword,
                          fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kai_baoxiang2(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                  fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
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


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kai_baoxiang3(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                  fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """宝箱开启结果检测"""
    targetText: str = r'(看.*视频.*\d+金.|看.*直播.*赚\d+金.)'
    prefixText: str = r'(宝箱|恭喜.*获得|明日签到|签到成功|本轮宝箱已开启)'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)

    # 持续观看广告视频,结束后自动返回当前页面
    if baseAir.tapByTuple(pos):
        if _can_do_other_action(**kwargs):
            baseAir.continue_watch_ad_videos(max_secs=90 if '直播' in ocrStr else 30, breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def lingqu_jiangli(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                   fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    观看视频退出时,可能弹框:
    标题: '点击额外获取90金币'
    按钮: '去完成任务' 和 '放弃奖励'
    """
    targetText: str = r'(^放弃奖励$)'
    prefixText: str = r'(^去完成任务$)'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)  # 放弃奖励,无后续弹框


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kanxiaoshuo_xuanze_xingqu(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                              fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    # 首次看小说会有选择男生小说/女生小说的弹框,由于文字是竖向排列的, 因此仅识别一个 '男' 字即可
    pos, _, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText='^男', prefixText='^选择兴趣得金.',
                                   fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.tapByTuple(pos, times=2)  # 点击两次才会消失
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def tuichu_zhibojian(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
                     fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    看直播退出时可能会弹框, 可能有以下几种
    标题: '看了这么久,留个关注再走吧!'
    按钮: '关注并退出' 和 '退出直播间'

    标题: '猜你喜欢'
    按钮: '大家还在搜:xxx' 和 '退出'
    """
    pos, _, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'(^退出直播间$|^退出$)',
                                   prefixText=r'(^关注并退出|^大家还在搜.*)', fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)
