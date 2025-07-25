# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import inspect
import re
import time
from typing import Union

from base.TaskManager import taskWrapper, TaskLifeCycle
from util.CommonUtil import CommonUtil
from wool_tasks.base_airtest_4_android_impl import AbsBaseAir4Android

"""
检测弹框
注意: 方法若需调用 check_if_in_page() 请将 autoCheckDialog 设置为 False,避免死循环
请将模态弹框检测方法放到前面
"""

__tag = 'check_dialog'


def _match_max_retry_count(curFuncName: str, maxHitCount: int = 2, **kwargs) -> bool:
    """
    当前方法是否已经连续触发过最大次数,若是,建议选择退出执行
    """
    lastHitFuncName = kwargs.get('lastHitFuncName', '')
    if CommonUtil.isNoneOrBlank(lastHitFuncName) or CommonUtil.isNoneOrBlank(
            curFuncName) or curFuncName != lastHitFuncName:
        return False
    lastHitFuncCount = kwargs.get('lastHitFuncCount', 0)
    return lastHitFuncCount >= maxHitCount


def _find_pos(baseAir: AbsBaseAir4Android, ocrResList: Union[list, None],
              targetText: str, prefixText: str = None, subfixText: str = None,
              fromX: int = 0, fromY: int = 0, height: int = 0,
              maxDeltaX: int = 0, maxDeltaY: int = 0, appendStrFlag: str = ' ',
              maxSwipeRetryCount: int = 1) -> tuple:
    """
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
        caller_func_name = inspect.getframeinfo(inspect.currentframe().f_back)[2]
        baseAir.logWarn(
            f'${__tag} _find_pos hit fromCaller={caller_func_name},targetText={targetText},prefixText={prefixText}'
            f',subfixText={subfixText},pos={pos},ocrStr={ocrStr}')
    return pos, ocrStr, ocrResList


def _can_do_other_action(defaultValue: bool = True, **kwargs) -> bool:
    """
    除了关闭弹框外,是否还可以继续执行后续操作,比如:观看广告视频
    """
    return kwargs.get('canDoOtherAction', defaultValue)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def anr(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
        fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '抖音极速版没有响应'
    按钮: '关闭应用'  等待
    """
    pos, _, _ = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'等待',
                          prefixText=rf'{baseAir.appName}没有响应', fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        baseAir.logWarn(f'anr 检测到anr弹框,尝试进行等待')
        baseAir.sleep(5)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def anr(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
        fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '抖音极速版没有响应'
    按钮: '关闭应用'  等待
    """
    pos, _, _ = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'等待',
                          prefixText=rf'{baseAir.appName}没有响应', fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        baseAir.logWarn(f'anr 检测到anr弹框,尝试进行等待')
        baseAir.sleep(5)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def restart(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
            fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '抖音极速版已停止运行'
    按钮: '重新打开应用'
    """
    pos, _, _ = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'重新打开应用',
                          prefixText=rf'{baseAir.appName}已停止运行', fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        baseAir.logWarn(f'anr 检测到app停止运行弹框,尝试进行启动并等待')
        baseAir.sleep(10)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def shoujihao_shouquan(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                       fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    手机卡广告可能会弹出授权获取手机号的弹框
    标题: '橙子建站 申请授权使用'
         '你的登录手机号'
         '请阅读并同意<授权书>, 系统将自动获取你的登录手机号, 用于本次及后续表单自动填写'
    按钮: '允许' '拒绝'
    """
    prefixText: str = r'你的登录手机号'
    targetText: str = r'拒绝'
    pos, _, ocrResList = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText,
                                   fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def check_contacts_update_dialog(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
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
def wufa_lianjie_wangluo(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                         fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    无法连接到网络弹框
    标题: '无法连接到网络，请稍后重试'
    按钮: '点击重试'
    """
    targetText: str = r'点击重试'
    prefixText: str = r'无法连接到网络'

    pos, _, ocrResList = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText,
                                   fromX=fromX, fromY=fromY)

    success = baseAir.tapByTuple(pos)
    if success:
        baseAir.logWarn(f'wufa_lianjie_wangluo 重试')
    return success


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def faxian_tongxunlu_pengyou(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                             fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """发现通讯录朋友弹框2,无文字按钮关闭"""
    targetText = r'(发现通讯录朋友|你可能认识的人)'
    prefixText = r'朋友推荐'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685624986007.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def confirm_exit(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '确认退出吗'
         '现在退出将失去当前进度任务进度噢'
    按钮: '坚持退出' '继续完成'
    """
    targetText = r'坚持退出'
    prefixText = r'确认退出吗'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def gongxi_huode_mianfei_hongbao(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
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
def zhaocaiya(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
              fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    招财鸭弹框
    标题: '主人,'
         '我等你很久了!'
         '你有一只 [招财鸭] 待领取
    按钮: '领养一只'  右上角有关闭按钮
    """
    targetText = r'领养一只'
    prefixText = r'.*招财鸭.*待领取'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog()
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def search_kaqi_dignwei_fuwu(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                             fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    搜索时,可能会要求开启定位服务, 无法通过返回取消
    标题: '开启定位服务'
         '为了向您推荐附近的作品和服务'  有多行, 此处省略
    按钮: '以后再说' '确认'
    """
    targetText = r'^以后再说'
    prefixText = r'开启定位服务'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def search_add_desktop_widget(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                              fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    搜索时,可能会弹出添加搜索框到桌面的提示, 右上角有关闭按钮
    标题: '添加搜索到桌面'
    按钮: '查看搜索攻略'   或者 '查看添加攻略'
    """
    targetText = r'^查看.*攻略'
    prefixText = r'添加搜索到桌面'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog()
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def gongxi_zhouzhou_zhuanjianbi(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """恭喜获得金币大礼包 周周赚金币弹框, 无法通过返回取消"""
    targetText = r'点击领取金.'  # '点击领取金币' '提现至微信秒到账'
    prefixText = r'周周赚金.'  # '超级星期五 周周赚金币'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685624986007.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def pk_jinbi(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
             fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    pk获得金币弹框, 无法通过返回取消
    标题: '你有588PK金币待领取'
         '点击即领,手慢无'
    按钮: '去领取'  右上角有关闭按钮
    """
    targetText = r'点击即领.手慢.'
    prefixText = r'有\d+PK金.*待领取'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685198790981.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def fanqie_mianfei_xiaoshuo(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                            fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy 看小说弹出番茄免费小说弹框, 无法通过返回取消
    标题: '番茄免费小说'
         '今日可赚'
         '10000+金币'
    按钮: '去APP赚金币'  右上角有关闭按钮

    标题: '番茄免费小说'
         '新人下载 领免费红包'
         '29元 最高'
    按钮: '立即下载'  右上角有关闭按钮

    标题: '去番茄小说读1分钟'
         '12888金币'
         '23:59:59后过期'
    按钮: '立即下载'  右上角有关闭按钮
    """
    targetText = r'(去APP赚金.|立即下载)'
    prefixText = r'(番茄免费小说|去番茄小说读)'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685624986007.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def dati_ying_xianjin(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                      fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    答题赢现金弹框, 无法通过返回取消
    标题: '答题赢现金'
         '多答多赚,每题必有钱'
    按钮: '参与答题赚钱'  右上角有关闭按钮
    """
    targetText = r'^参与答题赚钱'
    prefixText = r'^答题赢现金'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685624986007.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def dati_ying_xianjin(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                      fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy逛街等页面弹出下单赚金币弹框, 无法通过返回取消
    标题: '当前活动页下单，立得大额金币'
         '7088金币'
    按钮: '立即购物拿金币'  右上角有关闭按钮
    """
    targetText = r'立即购物拿金,'
    prefixText = r'当前活动页下单'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685624986007.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def download_url(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    看广告视频偶尔会误点下载app的按钮,出现弹框:
    标题: 无, 是一串网址
    内容: '确认要下载此链接吗？'
    按钮: '取消'  '确定'
    """
    targetText = r'^取消'
    prefixText = r'确认要下载此链接吗'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def shuige_haojiao(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                   fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    太晚了还在看视频会弹框提醒
    标题: '很晚了，睡个好觉'
         '设置睡觉提醒, 开启健康生活'
    按钮: '取消'  '提醒我睡觉'

    标题: '早点睡觉吧'
         '设置提醒,养成健康作息'
    按钮: '取消' '提醒我睡觉'
    """
    targetText = r'^取消'
    prefixText = r'(设置睡觉提醒|早点睡觉)'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def fanqie_mianfei_xiaoshuo2(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                             fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy 看小说弹出番茄免费小说弹框2
    标题: '去番茄小说读1分钟'
         '12888金币'
         '23:58:59 后过期'
    按钮: '立即下载'  右上角有关闭按钮
    """
    targetText = r'^立即下载$'
    prefixText = r'^去番茄小说读\d+分钟'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685198790981.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def gognxi_huode_manjian_quanyi(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
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
    targetText = r'立即使用'
    prefixText = r'恭喜获得满减权益'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685624986007.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def gongxi_xingyun_yonghu(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                          fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '恭喜成为幸运用户'
         '平台专属福利'  '下单更优惠'
         '15元'  '优惠券'
         '满150元可用'  '限定优惠活动商品'
    按钮: '立即收下'
    下方有关闭按钮
    """
    targetText = r'立即收下'
    prefixText = r'喜成为幸运用户'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog()  # 用默认的 bd_assets/tpl1685624986007.png 可匹配到
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def gouwu_najinbi(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                  fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '当前活动页下单，立得大额金币'
         '7288金币'
    按钮: '立即购物拿金币'
         '确认收货7日后到账，可用去【金币收益】 中查看'
    右上角有关闭按钮
    """
    targetText = r'立即购物拿金.'
    prefixText = r'活动页下单'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1683813537693.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def pengzhang_youhuiquan(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                         fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '恭喜获得'
         '领取膨胀优惠券机会'
         中间是优惠券信息
    按钮: '膨胀'
    下方有关闭按钮
    """
    targetText = r'膨胀'
    prefixText = r'领取膨胀优惠券机会'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1684931855744.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def hudong_youhuiquan(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                      fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '参与互动，领取优惠券福利'
    按钮: '继续互动'  ‘坚持退出’
    下方有关闭按钮
    """
    targetText = r'坚持退出'
    prefixText = r'参与互动.*优惠券'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog(r'bd_assets/tpl1685198790981.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def zhubo_kaibo(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '你关注的主播正在开播哦'
    按钮: '立即去看'  ‘退出直播间’
    右上角有关闭按钮
    """
    targetText = r'退出直播间'
    prefixText = r'主播正在开播'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)
    # if not CommonUtil.isNoneOrBlank(pos):
    #     baseAir.closeDialog(r'bd_assets/tpl1685198790981.png')
    #     return True
    # return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kan_xiaoshuo_tianjiang_hongbao(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                                   fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    看小说的天降红包,点击后会跳转视频播放页面
    """
    targetText: str = r'(立即领取|^领取$)'
    prefixText: str = r'(^领|天降红包|发放的红包)'  # '天降红包' 偶尔会识别为:'女天降红包'

    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        if _can_do_other_action(**kwargs):
            baseAir.continue_watch_ad_videos(breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def haoyou_kan_shipin(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                      fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '恭喜获得好友看视频奖励'
         ' 1588金币'
    按钮: '继续邀请赚89元' 左上角有关闭按钮
    """
    targetText = r'继续邀请.{1,6}元'
    prefixText = r'好友看视频奖励'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog()
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def jiaru_paihang(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                  fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    在dy赚钱任务页面,每天首次跳转后可能弹出签到弹框,又额外覆盖加入排行弹框
    标题: '加入排行'
         '加入排行榜,和好友以及同城用户们一起连续签到,争取更高排名吧'
    按钮: '查看搜索攻略'
    """
    targetText = r'^加入排行'
    prefixText = r'加入排行'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog()
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kaitong_tongzhi(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                    fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '通知设置'
         '为保证成功过收到直播提醒，请在手机设置中开启通知、日历'
    按钮: '开启通知' 左上角有关闭按钮
    """
    targetText = r'^开启通知'
    prefixText = r'通知设置'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog()
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def wangluo_cuowu(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                  fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '网络错误'
         '当前无网络，请检查后重试'
    按钮: '刷新'

    标题: '无法连接网络，请稍后重试'
    按钮: '点击重试'

    标题: '请检查网络连接是否正常'
    按钮: '刷新'
    """
    targetText = r'(^刷新|点击重试)'
    prefixText = r'(网络错误|无法连接网络|请检查网络)'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        baseAir.sleep(3)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def xiadan_zhifu(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '下单并支付'
         '可外获得400金币'
         中间是产品介绍
    按钮: '去下单'
         '放弃奖励'  '我已下单'
    """
    targetText = r'放弃奖励'
    prefixText = r'下单并支付'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def haoping(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
            fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '喜欢就给个好评吧'
    按钮: '我要吐槽'  '妥妥好评'  右上角有关闭按钮
    """
    targetText = r'我要吐槽'
    prefixText = r'喜欢就给个好评'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog()
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def downlaod_app(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    底部弹框
    标题: '当前为非Wi-Fi环境,应用已加入下载队列'
    按钮: '继续下载'  '取消'
    """
    targetText = r'取消'
    prefixText = r'应用已加入下载队列'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def jixu_guankan(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    视频未观看结束就按下返回键,  弹出继续观看的弹框
    逛街赚金币也会弹出类似的弹框,但点击 '继续观看' 后需要上滑才会继续计时
    标题: '再看3s可领奖励'
         '+18金币'
    按钮: '继续观看'  '坚持退出' '换一个'

    形式2:
    标题: '再看6秒，可获得奖励'
    按钮: '继续观看' '放弃奖励' '换一个视频'

    形式3:
    标题: '继续观看18秒，可获得奖励'
    按钮: '继续观看' '坚持退出' '换一个'
    """
    targetText: str = r'(继续观看)'
    cancelText: str = r'(坚持退出|放弃奖励)'
    prefixText: str = r'看(\d+).*奖励'
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=targetText,
                                        prefixText=prefixText, fromX=fromX, fromY=fromY)
    if CommonUtil.isNoneOrBlank(pos):
        return False

    cancelPos, _, _ = _find_pos(baseAir, ocrResList, targetText=cancelText,
                                prefixText=prefixText, fromX=fromX, fromY=fromY)

    # 获取剩余最多时长
    restSecs: float = kwargs.get('maxTotalSec', -9999)
    if restSecs != -9999 and restSecs <= 0:  # 已不用继续等待
        return baseAir.tapByTuple(cancelPos)

    # 获取需要观看的时长
    ptn = re.compile(prefixText)
    result = ptn.findall(ocrStr)
    secs: float = 0
    if not CommonUtil.isNoneOrBlank(result):
        secs = CommonUtil.convertStr2Float(result[0][0], 3)
        if secs > restSecs + 1:  # 剩余可用时长已不够,直接退出
            return baseAir.tapByTuple(cancelPos)

        # 本次逛街所需总时长, 弹框时长就是逛街总时长,则肯定是被检测了, 不用再等待
        guangjie_secs = kwargs.get('guangjie_secs', -9999)
        if guangjie_secs != -9999 and secs >= guangjie_secs - 1:
            return baseAir.tapByTuple(cancelPos)

    baseAir.logWarn(f'jixu_guankan secs={secs}, ocrStr={ocrStr}')

    if baseAir.tapByTuple(pos):
        if secs > 0:
            if restSecs == -9999:
                baseAir.sleep(secs)
            elif restSecs >= secs:
                baseAir.sleep(secs)

        if _can_do_other_action(**kwargs):
            if kwargs.get('needSwipeUp', False):
                baseAir.logWarn(f'jixu_guankan needSwipeUp secs={secs}')
                startTs = time.time()
                swipeUp: bool = True
                while True:
                    if swipeUp:
                        baseAir.swipeUp(durationMs=1500)
                    else:
                        baseAir.swipeDown(durationMs=1500)
                    swipeUp = not swipeUp
                    if time.time() - startTs >= secs:
                        break
            else:
                baseAir.continue_watch_ad_videos(max_secs=90 if '直播' in ocrStr else 30, breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def check_sign(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
               fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    检测签到弹框
    '恭喜你获得' 偶尔会识别为 '赫喜你获得'
    形式可能多种,以下格式依次是: 标题   内容     按钮    其他按钮
    * '每日签到'    '已经连续签到2天'     '立即签到+1200金币'       '签到提醒' 开关
    * '每日签到'    '已经连续签到2天'    '签到奖励已翻倍+70金币'      '签到提醒' 开关
    * '每日签到'    '已经连续签到2天'    '看视频签到+400金币金币'     '签到提醒' 开关
    """
    targetText: str = r'(^看.{0,6}视频签到.{0.6}金.|^立即签到|签到奖励已翻倍|明天签到|^立即领取$|^领取$|^开心收下|^好的$|^点击领取$|^我知道了|知道啦)'
    prefixText: str = r'(.喜.*获得|签到礼包|今日可领|今日签到可领|明天可领|明日签到|每日签到|签到成功|连签\d天必得|签到专属福利|青少年模式|成长护航|百科精选|成功领取\d+金.|专属红包|连续签到)'

    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def xiaoshuo_shipin(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                    fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy 看小说后的领金币弹框, 可能会提示看视频额外赚金币
    '恭喜你获得' 偶尔会识别为 '恭喜你庆得'  '恭三你庆得'

    标题:  '恭喜你获得'
          '208金币'
    按钮: '看视频再赚 40 金币' 右上角有关闭按钮

    标题: '恭喜你获得'
         '312金币'
    按钮: '看内容最高可得500金币'
    """
    targetText: str = r'(看.*视频再赚.*金.|看内容最高可得\d+金.)'
    prefixText: str = r'(.喜你.得)'

    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        if _can_do_other_action(**kwargs):
            baseAir.continue_watch_ad_videos(max_secs=60, breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def check_sign2(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    检测签到弹框
    形式可能多种,以下格式依次是: 标题   内容     按钮    其他按钮
    * '明日签到+300金币'    '已经连续签到2天'    '看广告视频再赚65金币'      '签到提醒' 开关
    """
    targetText: str = r'看广告视频再赚'
    prefixText: str = r'明日签到.{0.6}金.'

    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        if _can_do_other_action(**kwargs):
            baseAir.continue_watch_ad_videos(max_secs=90 if '直播' in ocrStr else 30, breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def check_sign3(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    # 可能会自动弹出签到提醒
    targetText: str = r'(邀请好友立赚高额现金|邀请新用户可得|签到提醒|签到专属福利|\d+天必得.*金.)'
    # prefixText: str = r'恭喜你获得'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):

        # 若超过最大次数，则尝试重启app
        if _match_max_retry_count('check_sign3', maxHitCount=3, **kwargs):
            baseAir.killApp()
            baseAir.startApp()
            baseAir.sleep(5)
            return baseAir.goto_home_earn_tab()

        baseAir.logWarn(f'check_dialog 关闭邀请好友/打开签到提醒等弹框')
        baseAir.closeDialog(r'bd_assets/tpl1685624986007.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def song_pengyou(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '已获得52金币'
         '再去 [去朋友页送金币] 得'
         '100金币 最高'
    按钮: '送好友' 右上角有关闭按钮

    标题: '已获得52金币'
         '再去 [逛街赚钱] 得'
         '3000金币 最高'
    按钮: '去逛街' 右上角有关闭按钮
    """
    targetText: str = r'再去.*得'
    prefixText: str = r'已获得\d+金.'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText,
                          fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.logWarn(f'check_dialog 关闭送好友/去逛街得金币等弹框')
        baseAir.closeDialog(r'bd_assets/tpl1685198790981.png')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def cunqianguan(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '送你650金币存钱罐'
         '看视频存满存钱罐,领640金币'
    按钮: '看视频 领金币' 按钮没点击过不清楚效果, 右上角有关闭按钮
    """
    targetText: str = r'(看视频存满存钱罐)'
    prefixText: str = r'(存钱罐)'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog()
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def remind_rest(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """ 夜间提醒休息弹框 """
    targetText = r'(取消|退出)'
    prefixText = r'(累了吧.*休息一下|猜你喜欢|休息提醒|合理分配时间)'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def jiaru_shujia(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy看小说, 小说阅读页面偶尔会弹出加入书架弹框
    标题: '加入书架,方便下次阅读'
         '近期6825人将《xxx》加入书架
    按钮: '以后再说'/'暂不加入'  以及  '加入书架'

    标题:  '加入书架'
          '喜欢这本书就加入书架吧'
    按钮:  '取消'  '确定'
    """
    targetText = r'(以后再说|暂不加入|取消)'
    prefixText = r'(加.书架.方便.*|喜欢这本书就加入书架)'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def yuedu_jiangli(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                  fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    ks看小说, 小说阅读页面偶尔会弹出阅读奖励弹框
    标题: '恭喜获得阅读奖励'
         '+80金币'
    按钮: '看完视频再领80金币' 下方有个关闭按钮
    """
    targetText = r'看完视频再领\d+金.'
    prefixText = r'恭喜获得阅读奖励'
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=targetText, prefixText=prefixText, fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        baseAir.continue_watch_ad_videos(breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def jixu_guankan(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    视频未观看结束就按下返回键,  弹出继续观看的弹框
    逛街赚金币也会弹出类似的弹框,但点击 '继续观看' 后需要上滑才会继续计时

    出现过弹框后继续观看xx秒，依然会继续弹xx秒弹框，导致耗在该方法无法继续挂机
    因此增加连续弹框此处检测，若超过3次，则选择退出

    标题: '再看3s可领奖励'
         '+18金币'
    按钮: '继续观看'  '坚持退出' '换一个'

    形式2:
    标题: '再看6秒，可获得奖励'
    按钮: '继续观看' '放弃奖励' '换一个视频'

    形式3:
    标题: '继续观看18秒，可获得奖励'
    按钮: '继续观看' '坚持退出' '换一个'
    """
    targetText: str = r'(继续观看)'
    cancelText: str = r'(坚持退出|放弃奖励)'
    prefixText: str = r'看(\d+).{1,2}可(领|获得)奖励'
    pos, ocrStr, ocrResList = _find_pos(baseAir, ocrResList, targetText=targetText,
                                        prefixText=prefixText, fromX=fromX, fromY=fromY)
    if CommonUtil.isNoneOrBlank(pos):
        return False

    cancelPos, _, _ = _find_pos(baseAir, ocrResList, targetText=cancelText,
                                prefixText=prefixText, fromX=fromX, fromY=fromY)

    # 获取剩余最多时长
    restSecs: float = kwargs.get('maxTotalSec', -9999)
    if restSecs != -9999 and restSecs <= 0:  # 已不用继续等待
        return baseAir.tapByTuple(cancelPos)

    # 获取需要观看的时长
    ptn = re.compile(prefixText)
    result = ptn.findall(ocrStr)
    secs: float = 0
    if not CommonUtil.isNoneOrBlank(result):
        secs = CommonUtil.convertStr2Float(result[0][0], 3)
        if secs > restSecs:  # 剩余可用时长已不够,直接退出
            return baseAir.tapByTuple(cancelPos)

        # 本次逛街所需总时长, 弹框时长就是逛街总时长,则肯定是被检测了, 不用再等待
        guangjie_secs = kwargs.get('guangjie_secs', -9999)
        if guangjie_secs != -9999 and secs >= guangjie_secs - 1:
            return baseAir.tapByTuple(cancelPos)

    baseAir.logWarn(f'jixu_guankan secs={secs}, ocrStr={ocrStr}')

    # 若超过最大次数，则尝试退出
    if _match_max_retry_count('jixu_guankan', **kwargs):
        cancelPos, _, _ = _find_pos(baseAir, ocrResList, targetText=cancelText,
                                    prefixText=prefixText, fromX=fromX, fromY=fromY)
        if baseAir.tapByTuple(cancelPos):
            return True

    if baseAir.tapByTuple(pos):
        if secs > 0:
            if restSecs == -9999:
                baseAir.sleep(secs)
            elif restSecs >= secs:
                baseAir.sleep(secs)

        if _can_do_other_action(**kwargs):
            if kwargs.get('needSwipeUp', False):
                baseAir.logWarn(f'jixu_guankan needSwipeUp secs={secs}')
                startTs = time.time()
                swipeUp: bool = True
                while True:
                    if swipeUp:
                        baseAir.swipeUp(durationMs=1500)
                    else:
                        baseAir.swipeDown(durationMs=1500)
                    swipeUp = not swipeUp
                    if time.time() - startTs >= secs:
                        break
            else:
                baseAir.continue_watch_ad_videos(max_secs=90 if '直播' in ocrStr else 30, breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def jixu_shanghua(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                  fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '继续上滑浏览60秒可领取'
            '60金币'
    按钮: '继续浏览'   '坚持退出'
    """
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=r'继续浏览',
                               prefixText=r'继续上滑浏览\d+秒可领', fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        pattern = re.compile(r'继续上滑浏览(\d+)秒可领')
        result = pattern.findall(ocrStr)
        if CommonUtil.isNoneOrBlank(result):
            secs = 10
        else:
            secs = int(result[0])
        startTs: float = time.time()
        swipeUp: bool = True
        while True:
            if swipeUp:
                baseAir.swipeUp()
            else:
                baseAir.swipeDown()

            baseAir.sleep(3)
            swipeUp = not swipeUp

            if time.time() - startTs >= secs:
                break
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def shezhi_touxiang(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                    fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    视频流页面误点喜欢或者误切到我的页面,由于没有设置头像会弹出提示框
    标题: '设置头像，更好地表达你的喜爱'  或者 ‘添加你的头像’
         '点击添加头像'
    按钮: '完成' 或者 ‘继续’  右上角有关闭按钮
    """
    targetText: str = r'点击添加头像'
    prefixText: str = r'(设置头像|添加你的头像)'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog()
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def zaikan_yige(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    视频播放完成,按下返回键后,弹出再看一个的弹框,第二种形式
    标题: '再看一个视频额外获得'
         '+18金币
    按钮: '领取奖励' '坚持退出'

    标题: '再看一个视频金币最高可得'
         '+800金币'
    按钮: '领取奖励' '坚持退出'
    """
    targetText: str = r'领取奖励'
    prefixText: str = r'再看一个视频'
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
def zaikan_yige(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    视频播放完成,按下返回键后,弹出再看一个的弹框
    标题: '恭喜你已获得奖励'
         '继续观看视频最高得800金币'  或 '继续观看视频额外得超值奖励'
    按钮: '再看一个'  或者  '再看一个最高得400金币'
          '坚持退出'
    """
    targetText: str = r'^再看一个'
    prefixText: str = r'继续观看视频.*得.*'
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
def lingqu_jiangli(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
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
def chakan_guanggao(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                    fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy: 误点到 '拆红包' 页面会弹出
    标题: '金币奖励'
        '查看下方广告 领取金币'
    按钮:  '好的' '关闭'
    """
    targetText: str = r'^关闭$'
    prefixText: str = r'查看下方广告.*领取金币'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)

    if baseAir.tapByTuple(pos):
        baseAir.back_until(targetText=breakIfHitText, maxRetryCount=3)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def xiazai_tiyan(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    观看广告视频结束后,可能会弹出下载并体验app弹框
    标题: '下载并体验20秒'
         '额外领100金币'
    按钮: '去完成任务'   '放弃奖励'
    """
    targetText: str = r'放弃奖励'
    prefixText: str = r'(下载|打开)并体验.*'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kai_baoxiang2(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
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
def kai_baoxiang3(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                  fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    新人福利, 转盘宝箱,开启完成后停留在转盘页面
    标题: '本轮宝箱已开启'  --> 偶尔识别为: 'AE宝已开启' '本牧主术已开后'
         '再开6次'
          '必得全部奖励'
    按钮: '00:19:59后再开一次' 下方是关闭按钮
         若在弹出框中等待倒计时结束, 则按钮文本会变为: '立即开宝箱' 见 kai_baoxiang4()
    """
    targetText: str = r'\d{2}:\d{2}:\d{2}.再开.次'
    prefixText: str = r'(已开启|已开后|再开\d+次|必得全部奖励)'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        baseAir.closeDialog()
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kai_baoxiang4(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                  fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    新人福利, 转盘宝箱,开启完成后停留在转盘页面
    标题: '本轮宝箱已开启'  --> 偶尔识别为: 'AE宝已开启' '本牧主术已开后'
         '再开6次'
          '必得全部奖励'
    按钮: '00:19:59后再开一次' 下方是关闭按钮
         若在弹出框中等待倒计时结束, 则按钮文本会变为: '立即开宝箱'
    """
    targetText: str = r'立即开宝箱'
    prefixText: str = r'(已开启|已开后|再开\d+次|必得全部奖励)'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos, sleepSec=5)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kai_baoxiang5(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                  fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    宝箱开启结果检测
    '恭喜你获得' 偶尔会识别为 '恭喜你庆得'  '恭三你庆得'
    '看广告视频再赚18金币' 偶尔会识别为 '看厂告机频再赚18金币'
    '看视频最高得400金币'
    '看广告视频再得1200金币'
    '看内容最高可得500金币'
    """
    targetText: str = r'(看视频最高得\d+金.|看.告视频再.\d+金.|看.{0.6}直播.{0,6}赚\d+金.|看内容最高可得\d+金.)'
    prefixText: str = r'(宝箱|恭.*得|明日签到|签到成功|本轮宝箱已开启|已开启|已开后|再开\d+次|必得全部奖励)'
    pos, ocrStr, _ = _find_pos(baseAir, ocrResList, targetText=targetText,
                               prefixText=prefixText, fromX=fromX, fromY=fromY)
    # 持续观看广告视频,结束后自动返回当前页面
    if baseAir.tapByTuple(pos):
        if _can_do_other_action(**kwargs):
            baseAir.continue_watch_ad_videos(max_secs=90 if '直播' in ocrStr else 30, breakIfHitText=breakIfHitText)
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kai_baoxiang(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    点击开宝箱得金币logo
    有两种文本:
    '开宝箱得金币'
    '12倍金币待领' '03分29秒' 后才可领取, 两个文本框上下滚动显示
    """
    # 第一步尝试开宝箱
    name, keyword = baseAir.get_earn_monkey_tab_name()
    pos, _, _ = _find_pos(baseAir, ocrResList, targetText=r'(^开宝箱得金.|\d+倍金.待领)', prefixText=keyword,
                          fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def lingqu_jiangli(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
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


# @taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
# def kanxiaoshuo_xuanze_xingqu(baseAir: AbsBaseAir, ocrResList: list, breakIfHitText: str = None,
#                               fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
#     # 首次看小说会有选择男生小说/女生小说的弹框,由于文字是竖向排列的, 因此仅识别一个 '男' 字即可
#     pos, _, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText='^男', prefixText='^选择兴趣得金.',
#                                    fromX=fromX, fromY=fromY)
#     if not CommonUtil.isNoneOrBlank(pos):
#         baseAir.tapByTuple(pos, times=2)  # 点击两次才会消失
#         return True
#     return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def kanxiaoshuo_tuijian(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                        fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    dy 退出看小说页面时弹出:
    标题: '为你推荐高分热门小说'
    按钮: '换一换' 左上角有关闭按钮
    """
    pos, _, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText='^换一换',
                                   prefixText='^为你推荐高分热门小说',
                                   fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.closeDialog()
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def tuichu_zhibojian(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                     fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    看直播退出时可能会弹框, 可能有以下几种
    标题: '看了这么久,留个关注再走吧!'
    按钮: '关注并退出' 和 '退出直播间'

    标题: '猜你喜欢'
    按钮: '大家还在搜:xxx' 和 '退出'

    标题: '猜你对这些直播感兴趣'
    按钮: '更多直播'  '退出直播间'
    """
    pos, _, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'(退出直播间|退出$)',
                                   prefixText=r'(关注并退出|^大家还在搜.*|猜你对这些直播感兴趣)', fromX=fromX,
                                   fromY=fromY)
    return baseAir.tapByTuple(pos)


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def baozhang_hognbao(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                     fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '哇塞！成功爆涨'
         '已爆涨红包' '84元'
    按钮: '立即邀请'  右上角有关闭按钮
    """
    pos, _, ocrResList = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'立即邀请',
                                   prefixText=r'已爆涨红包', fromX=fromX, fromY=fromY)
    if not CommonUtil.isNoneOrBlank(pos):
        baseAir.logWarn(f'baozhang_hognbao 检测到爆涨红包弹框,尝试进行关闭')
        baseAir.closeDialog()
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def xinren_fuli(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    标题: '新人福利'
         '您有无门槛优惠券待使用'
    按钮: '知道了'  下面有关闭按钮
    """
    pos, _, _ = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'知道了',
                          prefixText=r'您有无门槛优惠券待使用', fromX=fromX, fromY=fromY)
    if baseAir.tapByTuple(pos):
        baseAir.logWarn(f'xinren_fuli 检测无门槛优惠券弹框,尝试进行关闭')
        return True
    return False


@taskWrapper(__tag, taskLifeCycle=TaskLifeCycle.custom)
def jairu_shujia(baseAir: AbsBaseAir4Android, ocrResList: list, breakIfHitText: str = None,
                 fromX: int = 0, fromY: int = 0, *args, **kwargs) -> bool:
    """
    看小说返回时弹框是否加入书架
    标题: '加入书架,方便下次阅读'
         '近期有6825人将<...>加入书架'
    按钮: '以后再说' '加入书架'
    """
    pos, _, _ = _find_pos(baseAir, ocrResList=ocrResList, targetText=r'以后再说',
                          prefixText=r'加入书架.*方便下次阅读', fromX=fromX, fromY=fromY)
    return baseAir.tapByTuple(pos)
