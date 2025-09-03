# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys
import traceback

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

import logging
import re

__author__ = "Lynxz"

from cnocr import CnOcr
from airtest.core.api import *
from airtest.aircv import *
from util.CommonUtil import CommonUtil
from WoolProject import AbsWoolProject
from util.TimeUtil import TimeUtil
from util.TimeUtil import log_time_consume
from util.FileUtil import FileUtil
from util.NetUtil import NetUtil

"""
airtest基类, 所有子类请自行配置下: auto_setup(__file__) 
api文档: https://airtest.readthedocs.io/zh-cn/latest/index.html
"""
auto_setup(__file__)

logger = logging.getLogger("airtest")
logger.setLevel(logging.WARN)


class BaseAir(AbsWoolProject):
    def __init__(self, platform: str, uuid: str, app_name: str = '', cacheDir: str = ''):
        """
        :param platform: 平台, 支持 android 和 windows
        :param uuid: 对于android表示设备序列号  对于Windows表示窗口句柄, ios则表示uuid
        :param app_name: 应用名称
        """
        AbsWoolProject.__init__(self, cacheDir=cacheDir)

        self.platform = platform.lower()  # 当前设备平台, 支持 android 和 windows
        self.poco = None
        self.airtest_device = None  # airtest设备列表中的当前设备
        self.uuid = uuid
        self.appName = app_name
        self.adbUtil = None  # 对于android有效,表示adb工具对象
        self.deviceId = uuid  # 对于android有效,此时uuid表示设备序列号
        self.snapshot_img = None  # 当前屏幕截图对象, 每次调用 snapshot() 后更新

        # 测试使用 cnocr 进行解析
        # 文档: https://cnocr.readthedocs.io/zh/latest/usage/
        # 首次安装运行时会自动下载模型, 若报错下载失败找不到模型文件,可参考下面文案手动下载模型放到报错的路径目录下
        # https://huggingface.co/breezedeus/cnstd-cnocr-models/tree/main/models/cnocr/2.2
        self.cnocrImpl: CnOcr = CnOcr()  # cnocr识别对象

        # 连接设备
        self.connect()

    def isAndroid(self) -> bool:
        return self.platform == 'android'

    def isWindows(self) -> bool:
        return self.platform == 'windows'

    def connect(self):
        try:
            if self.isAndroid():
                from util.AdbUtil import AdbUtil
                connect_device(f"Android:///{self.uuid}?cap_method=javacap&touch_method=adb")
                self.adbUtil = AdbUtil()
            elif self.isWindows():
                connect_device(f"Windows:///{self.uuid}")
            self.airtest_device = device()
        except Exception as e:
            NetUtil.push_to_robot(f'连接{self.platform}设备失败: {e}', printLog=True)
            raise e

    # def connectAndroid(self, deviceId: str):
    #     connect_device("Android:///%s?cap_method=javacap&touch_method=adb" % deviceId)
    #
    # def connectWindows(self, handle_id: str = None, title_re: str = None):
    #     """
    #     连接到指定的windows窗口,支持指定窗口句柄id(优先)或者窗口名称表达式, 若二者都为空,则直接连接整个桌面
    #     具体见airtest文档: https://airtest.doc.io.netease.com/IDEdocs/3.2device_connection/5_windows_connection/#2-windows
    #     :param handle_id 句柄id, 每次重启软件可能变化
    #     :param title_re 窗口标题, 正则表达式
    #     """
    #     isIdEmpty = CommonUtil.isNoneOrBlank(handle_id)
    #     isTitleEmpty = CommonUtil.isNoneOrBlank(title_re)
    #
    #     if isIdEmpty and isTitleEmpty:
    #         auto_setup(__file__, devices=["Windows:///"])  # 连接Windows桌面
    #     elif isIdEmpty:
    #         auto_setup(__file__, devices=[f"Windows:///?title_re={title_re}"])
    #     else:
    #         auto_setup(__file__, devices=[f"Windows:///{handle_id}"])
    #     self.airtest_device = device()
    #     return self

    def calcCenterPos(self, ltrb: list, deltaXY: tuple = (0, 0), default_value: tuple = ()) -> tuple:
        """
        给定矩形框4个顶点的坐标,计算其中心点坐标(x,y)
        :param ltrb: 4个顶点坐标,依次为左上,右上,右下,左下, 每个元素包含是个list, list中包含两个float子元素,依次表示x,y的位置
        :param deltaXY : 偏移量, 依次为x,y的偏移量, 默认为(0,0)
        :param default_value: ltrb不满足需求时,返回的默认值
        :return tuple: 中心点的坐标(x,y) x,y的类型是float, 若输入为空,则返回空白元组 ()
        """
        if CommonUtil.isNoneOrBlank(ltrb) or len(ltrb) < 3:
            return default_value
        lt = ltrb[0]
        rt = ltrb[1]
        rb = ltrb[2]
        # lb = ltrb[3]
        centerX = lt[0] + (rt[0] - lt[0]) / 2
        centerY = rt[1] + (rb[1] - rt[1]) / 2
        return centerX + deltaXY[0], centerY + deltaXY[1]

    def calcSize(self, ltrb: list, deltaXY: tuple = (0, 0), default_value: tuple = ()) -> tuple:
        """
        给定矩形框4个顶点的坐标,计算其宽高尺寸(width,height)
        :param ltrb: 4个顶点坐标,依次为左上,右上,右下,左下, 每个元素包含是个list, list中包含两个float子元素,依次表示x,y的位置
        :param deltaXY : 偏移量, 依次为width,height的偏移量, 默认为(0,0)
        :param default_value: ltrb不满足需求时,返回的默认值
        :return tuple: (width,height) width,height的类型是float, 若输入为空,则返回空白元组 ()
        """
        if CommonUtil.isNoneOrBlank(ltrb) or len(ltrb) < 3:
            return default_value
        lt = ltrb[0]
        rt = ltrb[1]
        rb = ltrb[2]
        # lb = ltrb[3]
        width = rt - lt + deltaXY[0]
        height = rb - rt + deltaXY[1]
        return width, height

    @logwrap
    # @log_time_consume()
    def snapshot(self, filename=None, msg="", quality=None, max_size=None):
        if not quality:
            quality = ST.SNAPSHOT_QUALITY
        if not max_size and ST.IMAGE_MAXSIZE:
            max_size = ST.IMAGE_MAXSIZE
        if filename:
            if not os.path.isabs(filename):
                logdir = ST.LOG_DIR or "."
                filename = os.path.join(logdir, filename)
        self.snapshot_img = self.airtest_device.snapshot(filename, quality=quality, max_size=max_size)
        # return self.try_log_screen(screen, quality=quality, max_size=max_size)
        return self.snapshot_img

    @logwrap
    def exists(self, v):
        """
        Check whether given target exists on device screen
        :param v: target to be checked
        :return: False if target is not found, otherwise returns the coordinates of the target
        :platforms: Android, Windows, iOS
        """
        try:
            pos = self.loop_find(v, timeout=ST.FIND_TIMEOUT_TMP)
        except TargetNotFoundError:
            return False
        else:
            return pos

    @logwrap
    def touch(self, v, times=1, **kwargs):
        """
        Perform the touch action on the device screen
        :param v: target to touch, either a ``Template`` instance or absolute coordinates (x, y)
        :param times: how many touches to be performed
        :param kwargs: platform specific `kwargs`, please refer to corresponding docs
        :return: finial position to be clicked, e.g. (100, 100)
        :platforms: Android, Windows, iOS
        :Example:
            Click absolute coordinates::
            # >>> touch((100, 100))
            Click the center of the picture(Template object)::
            # >>> touch(Template(r"tpl1606730579419.png", target_pos=5))
            Click 2 times::
            # >>> touch((100, 100), times=2)
            Under Android and Windows platforms, you can set the click duration::
            # >>> touch((100, 100), duration=2)
            Right click(Windows)::
            # >>> touch((100, 100), right_click=True)

        """
        if isinstance(v, (list, tuple)) and len(v) < 2:
            print(f'touch fail as pos iv {v}')
            return None

        if isinstance(v, Template):
            pos = self.loop_find(v, timeout=ST.FIND_TIMEOUT)
        else:
            screen = self.snapshot()
            self.try_log_screen(screen=screen)
            pos = v
        for _ in range(times):
            self.airtest_device.touch(pos, **kwargs)
            time.sleep(0.05)
        delay_after_operation()
        return pos

    @logwrap
    def text(self, content, enter=True, **kwargs):
        """
        Input text on the target device. Text input widget must be active first.
        输入文本
        :param content: 输入的文本内容
        :param enter: 是否按下回车键, 默认为True
        """
        self.airtest_device.text(content, enter=enter, **kwargs)
        delay_after_operation()

    def clear_text(self):
        # 将光标移动到文本末尾
        keyevent("KEYCODE_MOVE_END")

        # 连续删除文本（假设最多8个字符）
        for _ in range(8):
            keyevent("KEYCODE_DEL")

    def key_press(self, key: str, cnt: int = 1, interval: float = 0.1):
        """
        模拟一个按下按键的事件
        文档: https://airtest.readthedocs.io/zh-cn/latest/all_module/airtest.core.win.win.html#airtest.core.win.win.Windows.key_press
         若需要组合按键, 请使用 keyevent() 接口,比如:alt+f4  -> keyevent("%{F4}")   delte -> keyevent("{DEL}")
        :param key: 要模拟的按键, 如: 'F2'
        :param cnt: 按键次数, 默认1次
        :param interval: 按键后等待的时间, 单位:秒
        """
        for i in range(cnt):
            self.airtest_device.key_press(key)
            self.sleep(interval)

    @logwrap
    def loop_find(self, query, timeout=ST.FIND_TIMEOUT, threshold=None, interval=0.5, intervalfunc=None):
        """
        Search for image template in the screen until timeout

        Args:
            query: image template to be found in screenshot
            timeout: time interval how long to look for the image template
            threshold: default is None
            interval: sleep interval before next attempt to find the image template
            intervalfunc: function that is executed after unsuccessful attempt to find the image template

        Raises:
            TargetNotFoundError: when image template is not found in screenshot

        Returns:
            TargetNotFoundError if image template not found, otherwise returns the position where the image template has
            been found in screenshot

        """
        G.LOGGING.info("Try finding: %s", query)
        start_time = time.time()
        while True:
            # 与airtest原有方法仅此处不同
            screen = self.snapshot(filename=None, quality=ST.SNAPSHOT_QUALITY)

            if screen is None:
                G.LOGGING.warning("Screen is None, may be locked")
            else:
                if threshold:
                    query.threshold = threshold
                match_pos = query.match_in(screen)
                if match_pos:
                    self.try_log_screen(screen)
                    return match_pos

            if intervalfunc is not None:
                intervalfunc()

            # 超时则raise，未超时则进行下次循环:
            if (time.time() - start_time) > timeout:
                self.try_log_screen(screen)
                raise TargetNotFoundError('Picture %s not found in screen' % query)
            else:
                time.sleep(interval)

    @logwrap
    def try_log_screen(self, screen=None, quality=None, max_size=None):
        if not ST.LOG_DIR or not ST.SAVE_IMAGE:
            return
        if not quality:
            quality = ST.SNAPSHOT_QUALITY
        if not max_size:
            max_size = ST.IMAGE_MAXSIZE
        if screen is None:
            screen = self.airtest_device.snapshot(quality=quality)
        filename = "%(time)d.jpg" % {'time': time.time() * 1000}
        filepath = os.path.join(ST.LOG_DIR, filename)
        if screen is not None:
            aircv.imwrite(filepath, screen, quality, max_size=max_size)
            return {"screen": filename, "resolution": aircv.get_resolution(screen)}
        return None

    def findTextByCnOCRResult(self, cnocr_result: list, targetText: str, prefixText: str = None,
                              subfixText: str = None,
                              fromX: int = 0, fromY: int = 0, maxDeltaX: int = 0, maxDeltaY: int = 0,
                              autoConvertQuotes: bool = True,
                              appendStrFlag: str = ' ', ignoreCase: bool = True,
                              printCmdInfo: bool = False) -> tuple:
        """
        根据cnocr识别结果,检测是否存在目标文本(targetText),若有则该文本的位置信息 todo 6.4 增加subfixText限制 或者 prefixText&targetText距离限制
        每次截图前会屏幕向上滑动 height 高度, 然后截取 (fromX,fromY) -> (fromX+width,fromY+height) 长条形区域图片进行OCR
        :param cnocr_result: 根据cnocr框架识别得到的结果,若为空,则返回失败
        :param targetText: 必填,要识别的文本正则表达式, 若为空, 则返回的是区域截图的ocr识别结果, pos列表为空
        :param prefixText: 要求在 targetText 之前应存在的字符串正则表达式,若为空,则表示不做判断
        :param subfixText: 要求在 targetText 之后应存在的字符串正则表达式,若为空,则表示不做判断
        :param fromX: 区域截图左上角的x坐标,默认(0,0)
        :param fromY: 区域截图左上角的Y坐标,默认(0,0)
        :param maxDeltaX: 识别到的 prefixText/targetText/subfixText pos坐标的x方向允许的最大阈值, 大于0才有效
        :param maxDeltaY: 识别到的 prefixText/targetText/subfixText pos坐标的y方向允许的最大阈值, 大于0才有效
        :param autoConvertQuotes: 是否将ocr字符串中的双引号统一转为半角字符双引号
        :param appendStrFlag: 根据ocr结果列表拼接生成完整字符串时,连续两个文本之间的连接符号,默认为一个空格
        :param ignoreCase: 正则匹配字符串时,是否忽略大小写
        :param printCmdInfo: 是否打印日志结果
        :return tuple (list,str,dict): 三个元素都可能为空
            第一个元素list: 表示匹配到的targetText区域在屏幕的四个角的坐标(已自行累加了fromX,fromY的偏移量), 若为空,则表示未识别到
            第二个元素str:  表示最终ocr得到的文本
            第三个元素dict: cnocr识别到的该文本对应的其他信息dict,包含 text/score/position
        """
        if CommonUtil.isNoneOrBlank(cnocr_result):
            return None, '', None

        if CommonUtil.isNoneOrBlank(targetText):
            return None, self.composeOcrStr(cnocr_result), None

        targetDict: dict = None  # 目标文本信息, 包含 text/score/position
        prefixDict: dict = None  # prefixText信息, 包含 text/score/position,非none有效
        subfixDict: dict = None  # subfixText信息, 包含 text/score/position,非none有效
        ocr_str_result: str = ''  # 最后一次ocr识别的文本
        hitTargetText: bool = False  # 是否匹配到目标文字
        hitPrefixText: bool = CommonUtil.isNoneOrBlank(prefixText)
        hitSubfixText: bool = CommonUtil.isNoneOrBlank(subfixText)
        targetTextPattern = self._make_re_compile_obj(targetText, ignoreCase)
        prefixTextPattern = self._make_re_compile_obj(prefixText, ignoreCase)
        subfixTextPattern = self._make_re_compile_obj(subfixText, ignoreCase)

        for index in range(len(cnocr_result)):
            dictItem: dict = cnocr_result[index]
            t = dictItem.get('text', '')
            ocr_str_result = '%s%s%s' % (ocr_str_result, appendStrFlag, t)

            # 匹配前置文本
            if not hitPrefixText:
                resultList = prefixTextPattern.findall(t)
                hitPrefixText = not CommonUtil.isNoneOrBlank(resultList)
                if hitPrefixText:
                    prefixDict = dictItem
                continue

            # 匹配目标文本
            if not hitTargetText:
                resultList = targetTextPattern.findall(t)
                hitTargetText = not CommonUtil.isNoneOrBlank(resultList)
                if hitTargetText:
                    targetDict = dictItem
                continue

            # 匹配后置文本
            if not hitSubfixText:
                resultList = None if subfixTextPattern is None else subfixTextPattern.findall(t)
                hitSubfixText = not CommonUtil.isNoneOrBlank(resultList)
                if hitSubfixText:
                    subfixDict = dictItem

        # 对 prefixText 坐标偏移得到屏幕中的绝对坐标
        prefixPosList = None if prefixDict is None else prefixDict.get('position', None)
        if not CommonUtil.isNoneOrBlank(prefixPosList):
            for item in prefixPosList:
                item[0] = item[0] + fromX
                item[1] = item[1] + fromY

        # 对 targetText 坐标偏移得到屏幕中的绝对坐标
        posList = None if targetDict is None else targetDict.get('position', None)
        if not CommonUtil.isNoneOrBlank(posList):
            for item in posList:
                item[0] = item[0] + fromX
                item[1] = item[1] + fromY

        # 对 subfixText 坐标偏移得到屏幕中的绝对坐标
        subfixPosList = None if subfixDict is None else subfixDict.get('position', None)
        if not CommonUtil.isNoneOrBlank(subfixPosList):
            for item in subfixPosList:
                item[0] = item[0] + fromX
                item[1] = item[1] + fromY

        # 对ocr文本结果中的引号进行格式化处理
        if autoConvertQuotes:
            ocr_str_result = ocr_str_result.replace('＂', '"').replace('“', '"').replace('”', '"')

        valid = not CommonUtil.isNoneOrBlank(posList) and hitSubfixText
        if printCmdInfo:
            self.logWarn(
                f'findTextByCnOCRResult {valid},hitSubfixText={hitSubfixText}'
                f',targetText={targetText},prefixText={prefixText},subfix={subfixText}'
                f',ocr_str={ocr_str_result}')
        if not valid:
            return None, ocr_str_result, None

        # 计算总偏移区域是否满足 maxDeltaX 和 maxDeltaY 的要求
        if prefixDict is None:
            prefixDict = targetDict
        if subfixDict is None:
            subfixDict = targetDict
        prefixPosList = None if prefixDict is None else prefixDict.get('position', None)
        subfixPosList = None if subfixDict is None else subfixDict.get('position', None)

        deltaX = abs(prefixPosList[0][0] - subfixPosList[2][0])
        deltaY = abs(prefixPosList[0][1] - subfixPosList[2][1])
        successDelta: bool = True
        if maxDeltaX > 0:
            successDelta = deltaX <= maxDeltaX
        if maxDeltaY > 0:
            successDelta = successDelta and deltaY <= maxDeltaY

        if printCmdInfo:
            self.logWarn(
                f'findTextByCnOCRResult success={successDelta} deltaX,Y={deltaX},{deltaY},maxDeltaX,y={maxDeltaX},{maxDeltaY}')
        try:
            if not successDelta:
                return None, ocr_str_result, None
        except Exception as e:
            self.logWarn(f'findTextByCnOCRResult exception {e}')

        return posList, ocr_str_result, targetDict

    def findTextByOCR(self, targetText: str,
                      img=None,
                      prefixText: str = None,
                      subfixText: str = None,
                      fromX: int = 0, fromY: int = 0,
                      width: int = 0, height: int = 0,
                      maxDeltaX: int = 0, maxDeltaY: int = 0,
                      swipeOverlayHeight: int = 100,
                      maxSwipeRetryCount: int = 10,
                      saveAllImages: bool = False,
                      autoSwitchPointerLocation: bool = True,
                      saveDirPath: str = None,
                      imgPrefixName: str = '',
                      autoConvertQuotes: bool = True,
                      appendStrFlag: str = ' ',
                      ignoreCase: bool = True,
                      printCmdInfo: bool = False) -> tuple:
        """
        通过每次截图指定 height 的图片进行OCR识别,若识别到目标文本(targetText),则返回True
        每次截图前会屏幕向上滑动 height 高度, 然后截取 (fromX,fromY) -> (fromX+width,fromY+height) 长条形区域图片进行OCR
        :param img: 图片对象, 若为空,则表示使用当前屏幕截图进行识别
        :param targetText: 必填,要识别的文本正则表达式, 若为空, 则返回的是区域截图的ocr识别结果, pos列表为空
        :param prefixText: 要求在 targetText 之前应存在的字符串正则表达式,若为空,则表示不做判断
        :param subfixText: 要求在 targetText 之后应存在的字符串正则表达式,若为空,则表示不做判断
        :param fromX: 区域截图左上角的x坐标,默认(0,0)
        :param fromY: 区域截图左上角的Y坐标,默认(0,0)
        :param width: 区域截图宽度,0或负数表示截图到屏幕右侧边缘
        :param height: 区域截图的高度,若为0或负数,则表示截屏到屏幕底部
        :param maxDeltaX: 识别到的 prefixText/targetText/subfixText pos坐标的x方向允许的最大阈值, 大于0才有效
        :param maxDeltaY: 识别到的 prefixText/targetText/subfixText pos坐标的y方向允许的最大阈值, 大于0才有效
        :param swipeOverlayHeight:上滑时,少滑动该距离, 负数表示height的1/10
        :param maxSwipeRetryCount: 最多上滑截图的次数, 一次表示不上滑
        :param saveAllImages:是否保存每张截图,若为False,则仅保存匹配失败的截图
                        文件名格式: {cacheDir}/{deviceId}/{imgPrefixName}_index_fromX_fromY_toX_toY_{appName}.png
        :param autoSwitchPointerLocation: 仅对android有效, 是否自动关闭指针位置(避免ocr时被干扰), 识别结束后自动恢复初始状态
        :param saveDirPath: 截图保存的目录,若为空,则尝试保存到 {self.cacheDir} 中
        :param imgPrefixName: 截图前缀名称
        :param autoConvertQuotes: 是否将ocr字符串中的双引号统一转为半角字符双引号
        :param appendStrFlag: 根据ocr结果列表拼接生成完整字符串时,连续两个文本之间的连接符号,默认为一个空格
        :param ignoreCase: 正则匹配字符串时,是否忽略大小写
        :param printCmdInfo: 是否打印命令内容
        :return tuple (list,str,dict):
            第一个元素list: 表示匹配到的targetText区域在屏幕的四个角的坐标(已自行累加了fromX,fromY的偏移量), 若为空,则表示未识别到
            第二个元素str: 表示最终ocr得到的文本
            第三个元素list: cnocr识别的原始结果list
        """
        ocrStartTs: float = time.time()
        sWidth, sHeight = self.airtest_device.get_current_resolution()  # self.getWH()  # 获取当前设备宽度
        width = sWidth if width <= 0 else width
        height = sHeight if height <= 0 else height

        # 计算区域子截图的右下角坐标
        maxY = sHeight
        toX: int = fromX + width
        toY: int = fromY + height
        toX = toX if toX <= sWidth else sWidth
        toY = toY if toY <= maxY else maxY
        height = toY - fromY

        # 记录当前是否开启了 "指针位置" 功能,以便最后进行恢复
        if self.isAndroid():
            pointerLocationOri: int = self.adbUtil.pointerLocation(value=-1, deviceId=self.uuid)
            if autoSwitchPointerLocation:
                self.adbUtil.pointerLocation(value=0, deviceId=self.deviceId)  # 关闭指针位置

        hit: bool = False  # 是否匹配到目标文字
        posList: list = None  # 识别到的文本位置矩形框4个点的坐标列表
        ocr_str_result: str = ''  # 最后一次ocr识别的文本
        cnocr_result: list = None  # cnocr对区域截图进行识别的原始结果对象

        for i in range(maxSwipeRetryCount):
            try:
                screen = self.snapshot() if img is None else img  # 截屏
            except Exception as e:
                screen = None
                self.logError(f'snapshot fail {e}')
            if screen is None:
                self.logError(f'findTextByOCR fail as screenshot return null')
                return None, '', None

            if fromX == 0 and fromY == 0 and toX == sWidth and toY == sHeight:
                img = screen
            else:
                img = aircv.crop_image(screen, (fromX, fromY, toX, toY))  # 局部截图, 整体耗时0.15s左右

            cnocr_result = self.cnocrImpl.ocr(img)  # cnocr进行解析, 实测耗时大概0.2s
            posList, ocr_str_result, targetDict = self.findTextByCnOCRResult(cnocr_result, targetText=targetText,
                                                                             prefixText=prefixText,
                                                                             subfixText=subfixText,
                                                                             fromX=fromX, fromY=fromY,
                                                                             maxDeltaX=maxDeltaX,
                                                                             maxDeltaY=maxDeltaY,
                                                                             appendStrFlag=appendStrFlag,
                                                                             ignoreCase=ignoreCase,
                                                                             autoConvertQuotes=autoConvertQuotes)
            hit = hit or not CommonUtil.isNoneOrBlank(posList)  # 是否匹配到目标文字

            # 按需保存截图
            ocr_str_result = '' if ocr_str_result is None else ocr_str_result.strip()
            saveDirPath = self.cacheDir if CommonUtil.isNoneOrBlank(saveDirPath) else saveDirPath
            saveImg: bool = not CommonUtil.isNoneOrBlank(saveDirPath) and (saveAllImages or not hit)
            if saveImg:  # 保存图片还是耗时的0.8s左右, 占据方法的大头,因此默认只对失败的部分做截图
                loopStartTs = time.time()
                imgName = '%s_%s_%s_%s_%s_%s' % (imgPrefixName, i, fromX, fromY, toX, toY)
                img_path = self.saveImage(img, imgName=imgName)
                self.logWarn(
                    f'findTextByOCR loopCheck {i} saveImg duration={time.time() - loopStartTs},hit={hit},'
                    f'targetText={targetText},img_path={img_path},prefix={prefixText}', printCmdInfo=printCmdInfo)

            # 匹配到目标文本,则退出重试
            if hit:
                break
            elif maxSwipeRetryCount > 1:
                swipeOverlayHeight = swipeOverlayHeight if swipeOverlayHeight >= 0 else int(height * 0.1)
                swipeHeight = height - swipeOverlayHeight
                swipeHeight = height if swipeHeight <= 0 else swipeHeight

                maxSwipeHeight = sHeight * 0.7  # 预留底部部分空间,不免触发home操作
                if swipeHeight >= maxSwipeHeight:
                    swipeHeight = maxSwipeHeight

                # 滑动耗时稍微长点,避免onMoveUp后,页面因为惯性继续滑动
                if self.isAndroid():
                    self.swipeUp(minDeltaY=swipeHeight, maxDeltaY=swipeHeight,
                                 keepVerticalSwipe=True, durationMs=1500, printCmdInfo=printCmdInfo)

        # 恢复指针位置开关设置
        if self.isAndroid() and autoSwitchPointerLocation:
            self.adbUtil.pointerLocation(value=pointerLocationOri, deviceId=self.deviceId)

        self.logWarn(f'findTextByOCR {not CommonUtil.isNoneOrBlank(posList)},'
                     f'{time.time() - ocrStartTs}秒,target={targetText},prefix={prefixText},'
                     f'ocr_str_result={ocr_str_result}',
                     printCmdInfo=printCmdInfo)
        return posList, ocr_str_result, cnocr_result

    def composeOcrStr(self, cnocr_result: list, appendStrFlag: str = ' ') -> str:
        """根据cnocr识别结果拼接生成text信息"""
        ocr_str_result: str = ''
        if CommonUtil.isNoneOrBlank(cnocr_result):
            return ocr_str_result
        for index in range(len(cnocr_result)):
            dictItem: dict = cnocr_result[index]
            t = dictItem.get('text', '')
            ocr_str_result = '%s%s%s' % (ocr_str_result, appendStrFlag, t)
        return ocr_str_result

    def _make_re_compile_obj(self, targetText: str, ignoreCase: bool = True) -> re.Pattern:
        targetTextPattern = None
        if not CommonUtil.isNoneOrBlank(targetText):
            targetTextPattern = re.compile(targetText, re.IGNORECASE) if ignoreCase else re.compile(targetText)
        return targetTextPattern

    def saveScreenShot(self, imgName: str, fromX: int = 0, fromY: int = 0, toX: int = -1, toY: int = -1) -> str:
        """
        屏幕截图后, 截取区域图像并保存到文件中, 若 toX/toY 小于等于0, 则表示到屏幕右下角位置
        截图保存在 self.cacheDir 目录下, 若未指定目录,则保存失败
        :param imgName: 图片名(不包括后缀), 会自动拼接: .png,
                        文件路径: {cacheDir}/{deviceId}/{imgName}_{appName}.png
        :return str: 截图保存的路径, 若截图失败,则返回 ''
        """
        sWidth, sHeight = self.getWH()  # 获取当前设备宽度
        toX = toX if 0 < toX < sWidth else sWidth
        toY = toY if 0 < toY < sHeight else sHeight
        screen = self.snapshot()  # 截屏
        img = aircv.crop_image(screen, (fromX, fromY, toX, toY))  # 局部截图
        imgNameOpt = '' if CommonUtil.isNoneOrBlank(imgName) else ('%s_' % imgName)
        if CommonUtil.isNoneOrBlank(imgName):
            imgName = '%s_%s_%s_%s_%s' % (imgNameOpt, fromX, fromY, toX, toY)
        return self.saveImage(img, imgName)

    # @log_time_consume(exclude_params=['img', 'dirPath', 'autoAppendDateInfo', 'replaceFlag'])
    def saveImage(self, img, imgName: str = None, dirPath: str = None,
                  append_date_time: bool = True, replaceFlag: str = '_', auto_create_sub_dir: bool = True) -> str:
        """
        保存图片到 {cacheDir} 中
        实测耗时大概0.8s左右

        :param imgName: 文件名, 会自动拼接 {时间_}{self.appName}.png'
        :param dirPath: 图片要保存的目录,未未指定,则使用 self.cacheDir,若仍为空,则保存失败
        :param append_date_time: 最终的图片名称上是否追加时间信息, 默认为True
        :param replaceFlag: 若 imageName 中存在无效字符时,替代为该字符串
        :param auto_create_sub_dir: android时有效,表示是否创建子目录存储图片,路径: {dirPath}/{model}_{deviceId}/{imgName}
        :return str: 最终保存的路径名, 若为空,则表示保存失败
        """
        if img is None:
            return ''

        if CommonUtil.isNoneOrBlank(dirPath):
            dirPath = self.cacheDir

        if CommonUtil.isNoneOrBlank(dirPath):
            return ''
        dirPath = FileUtil.recookPath(dirPath)

        model = self.adbUtil.getDeviceInfo(self.deviceId).get('model', self.deviceId) if self.isAndroid() else ''
        if CommonUtil.isNoneOrBlank(imgName):
            append_date_time = True
            imgName = ''
        else:
            imgName = f'_{imgName}'

        if append_date_time:
            imgName = f"{TimeUtil.getTimeStr(fmt='%m%d_%H%M%S')}{imgName}"
        imgName = imgName.replace('(', replaceFlag).replace(')', replaceFlag) \
            .replace('|', replaceFlag).replace('.*', replaceFlag).replace('[', replaceFlag).replace(']', replaceFlag)

        try:
            pil_img = cv2_2_pil(img)
            FileUtil.createFile('%s/' % dirPath)

            if self.isAndroid():
                if auto_create_sub_dir:
                    img_path = f'{dirPath}/{model}_{self.deviceId}/{imgName}_{self.appName}.png'
                else:
                    img_path = f'{dirPath}/{imgName}_{self.appName}_{model}_{self.deviceId}.png'
            else:
                img_path = '%s/%s.png' % (dirPath, imgName)
            img_path = img_path.replace('_.png', ".png").replace(".png.png", ".png")

            img_path = FileUtil.recookPath(img_path)
            FileUtil.createFile(img_path)  # 按需创建父目录
            pil_img.save(img_path, quality=99, optimize=True)
            # self.logWarn('saveScreenShot imgPath=%s' % img_path)
            return img_path
        except Exception as e:
            traceback.print_exc()
            return ''

    @log_time_consume(exclude_params=['autoSwitchPointerLocation'])
    def getScreenOcrResult(self, autoSwitchPointerLocation: bool = True,
                           fromX: int = 0, fromY: int = 0, toX: int = 0, toY: int = 0, img_name: str = None) -> list:
        """
        获取当前屏幕截图的ocr结果对象
        :param autoSwitchPointerLocation: 仅对android有效, 是否自动关闭指针位置(避免ocr时被干扰), 识别结束后自动恢复初始状态
        :param fromX: 区域截图左上角的x位置,若大于0, 会进行裁剪后再ocr , fromY/toX/toY 同理
        :param img_name: 保存图片的名称, 若不为空, 则会保存图片到 {self.cacheDir} 目录下
        :return list: 识别结果对象, 若失败,则返回None
                        每个元素包含属性: text/score/position, 其中 position 是一个4个元素的列表, 分别是该文本的四个角的(x,y)坐标
        """
        # 记录当前是否开启了 "指针位置" 功能,以便最后进行恢复
        if self.isAndroid():
            pointerLocationOri: int = self.adbUtil.pointerLocation(value=-1, deviceId=self.deviceId)
            if autoSwitchPointerLocation:
                self.adbUtil.pointerLocation(value=0, deviceId=self.deviceId)  # 关闭指针位置

        screen = self.snapshot()  # 截屏

        # 恢复指针位置开关设置
        if self.isAndroid() and autoSwitchPointerLocation:
            self.adbUtil.pointerLocation(value=pointerLocationOri, deviceId=self.deviceId)

        # screen = self.airtest_device.snapshot()  # 截屏
        if screen is None:
            self.logError(f'getScreenOcrResult fail as screenshot return null')
            return list()
        screen = self.crop_img(screen, fromX, fromY, toX, toY, img_name)  # 局部截图
        return self.cnocrImpl.ocr(screen)  # cnocr进行解析, 实测耗时大概0.2s

    def crop_img(self, full_img,
                 fromX: int = 0, fromY: int = 0,
                 toX: int = 0, toY: int = 0,
                 img_name: str = None):
        """
        对指定的图片进行裁剪,并保存裁剪后的图片
        本方法主要用于列表行图片, 由于整图识别时, 不同列信息有发现会有被合并的情况,导致无法区分
        因此可以尝试先提取列明宽度, 然后对每列进行裁剪, 再单独执行ocr识别
        :param full_img: 完整的截图, 一般调用 self.snapshot() 即可
        :param fromX: 区域截图左上角的x位置,若大于0, 会进行裁剪后再ocr, fromY/toX/toY 同理
        :param img_name: 保存图片的名称, 若不为空, 则会保存图片到 {self.cacheDir} 目录下
        :return 区域截图后的图片对象
        """
        if full_img is None:
            self.logError(f'crop_img fail as full_img null')
            return full_img

        target_img = full_img
        if not fromX == fromY == toX == toY == 0:
            sWidth, sHeight = self.getWH()  # 获取当前设备宽度
            toX = toX if 0 < toX < sWidth else sWidth
            toY = toY if 0 < toY < sHeight else sHeight
            target_img = aircv.crop_image(full_img, (fromX, fromY, toX, toY))  # 局部截图

        if not CommonUtil.isNoneOrBlank(img_name):
            self.saveImage(target_img, img_name)
        return target_img

    # @log_time_consume(exclude_params=['full_img']) #大概0.1s左右就能执行完成
    def crop_then_ocr(self, full_img,
                      fromX: int = 0, fromY: int = 0,
                      toX: int = 0, toY: int = 0,
                      img_name: str = None) -> list:
        """
        对指定的图片进行裁剪, 并对裁剪后的子图片执行ocr识别,返回识别结果
        本方法主要用于列表行图片, 由于整图识别时, 不同列信息有发现会有被合并的情况,导致无法区分
        因此可以尝试先提取列明宽度, 然后对每列进行裁剪, 再单独执行ocr识别
        :param full_img: 完整的截图, 一般调用 self.snapshot() 即可
        :param fromX: 区域截图左上角的x位置,若大于0, 会进行裁剪后再ocr, fromY/toX/toY 同理
        :param img_name: 保存图片的名称, 若不为空, 则会保存图片到 {self.cacheDir} 目录下
        """
        target_img = self.crop_img(full_img, fromX, fromY, toX, toY, img_name)
        if target_img is None:
            self.logError(f'crop_img fail as target_img null')
            return list()
        return self.cnocrImpl.ocr(target_img)

    @log_time_consume(exclude_params=['full_img', 'title_key_dict'])
    def ocr_grid_view(self, full_img, title_key_dict: dict, vertical_mode: bool = False, expand: int = 18) -> list:
        """
        对于带标题行的表格区域进行识别
        支持按行识别或者按列识别
        按行识别时,只要对full_img进行ocr一次, 然后按行进行解析即可,速度较快,但可能无法保证每列都解析正确(可能会出现列内容跨列的情况)
        按列识别时,需要对full_img进行多次ocr(每列进行区域截图再ocr), 然后按列进行解析,速度较慢,但能保证每列都解析正确
        :param full_img: 完整的图片, 包含标题行和表格内容的截图, 不包含其他内容
        :param title_key_dict: 列标题映射, 格式: {列标题名: 标题key}, 请保证包含所有列信息, 且顺序与表格列顺序一致
                                其中 '列标题名' 是表格中列标题的文本, '标题key' 是该列的唯一标识, 最终会作为结果字典的key
        :param vertical_mode: 是否是列识别模式
        :param expand: 列识别模式时, 对每列进行区域截图时, 额外增加的宽度, 默认为18
        :return: 除标题行外的表格内容, 每个元素是一个dict, 格式为: [{'标题key1': '列1内容', '标题key2': '列2内容', ...}, ...]
        """

        # 请使用python3.7以上的版本,此时dict是按插入顺序存储的
        keys = list(title_key_dict.keys())  # 获取所有键的列表, 比如: ['证券代码' ,'证券名称']
        values = list(title_key_dict.values())  # 获取所有值的列表, 比如: ['code','name']
        size = len(keys)  # 要求记录的列数量, ocr可能识别更多的列, 但是最终只会记录这些列

        # 按行提取持仓信息
        center_y = -9999  # 当前识别的行y值, 用于确定是否换行了
        delta: int = 20  # 允许的误差
        line_dict = dict()  # 每行内容字典
        horizont_index = 0  # 该属性信息索引
        result = list()  # 最终结果
        self.saveImage(full_img, imgName='ocr_grid_view_full_img', append_date_time=True)  # 调试时保存图片

        if vertical_mode:  # 列模式识别
            # 获取每列的范围, 左/上/右 边界通过列标题获取, 下边界通过截图的高来确定
            title_ocr_result: list = None
            for i in range(len(keys)):
                key = keys[i]
                value = values[i]
                prefixText: str = ''
                subfixText: str = ''

                # 获取目标标题的前后标题名
                if i > 0:
                    for index in range(i - 1, 0, -1):
                        prefixText = keys[index]
                        if not CommonUtil.isNoneOrBlank(prefixText):
                            break
                if i < size - 1:
                    for index in range(i + 1, size - 1):
                        subfixText = keys[index]
                        if not CommonUtil.isNoneOrBlank(subfixText):
                            break

                # self.crop_then_ocr(full_img)
                if title_ocr_result is None:
                    pos, ocrResStr, ocrResList = self.findTextByOCR(key, full_img, prefixText=prefixText,
                                                                    subfixText=subfixText, maxSwipeRetryCount=1)
                    title_ocr_result = ocrResList
                    CommonUtil.printLog(f'持仓数据ocr结果: {ocrResStr}')
                else:
                    pos, ocrResStr, _ = self.findTextByCnOCRResult(title_ocr_result, key, prefixText=prefixText,
                                                                   subfixText=subfixText)
                if pos is None:
                    CommonUtil.printLog(f'列模式定位失败: {key},pre={prefixText},sub={subfixText},ocrStr={ocrResStr}')
                    continue
                CommonUtil.printLog(f'列模式定位成功: {key},pre={prefixText},sub={subfixText},pos={self.calcCenterPos(pos)}')

                # 根据标题列的坐标, 偏移获取到内容区域的返回
                pos_left = pos[0][0] - expand  # 左边界往左偏移一点
                pos_right = pos[1][0] + expand  # 右边界往右偏移一点
                pos_top = pos[3][1]  # 左下角y值,向下偏移一点
                w, h, d = full_img.shape
                pos_bottom = h - 10  # 截图底部向上偏移一点

                # 每列进行区域截图并ocr, 截图文件保存在 cache 目录下,首次运行时,请查看宽度是否符合预期,适当微调,避免ocr错误
                image_name = ''  # f'ocr_grid_view_{key}_{value}_{horizont_index}' # 调试时再保存图片
                ocr_result = self.crop_then_ocr(full_img, fromX=pos_left, fromY=pos_top, toX=pos_right, toY=pos_bottom, img_name=image_name)
                CommonUtil.printLog(f'{image_name} 识别结果:{self.composeOcrStr(ocr_result)}')

                # 每行对应一个dict对象的属性
                center_y = -9999  # 当前正在处理的行y值, 用于判断是否换行了, 有可能一行数据被解析呢多个, 因此不能纯粹按照下表来判断
                line_num = -1
                for item in ocr_result:
                    content: str = item['text'].strip()  # 文本内容
                    pos: list = item['position']  # 文本边框四个角的(x,y)坐标
                    center_pos = self.calcCenterPos(pos)  # 文本中心点的(x,y)坐标

                    y = center_pos[1]  # 当前处理的文本y坐标
                    if y - center_y > delta:  # 新的一行
                        result.append(dict())
                        line_num += 1
                        center_y = y

                    cur_value = result[line_num].get(value, None)
                    if CommonUtil.isNoneOrBlank(cur_value):
                        result[line_num][value] = content
                    else:
                        result[line_num][value] += content

                # for line_num, item in enumerate(ocr_result):
                #     # CommonUtil.printLog(f"行号 {line_num}: 值为 {item}")
                #     content: str = item['text'].strip()  # 文本内容
                #     if len(result) < line_num + 1:  # 新一行,创建行内容dict对象
                #         result.append(dict())
                #     result[line_num][value] = content  # 获取第N行对象dict, 并将其 'value' 属性值指定为 ocr 结果
        else:
            ocr_result = self.crop_then_ocr(full_img)
            for item in ocr_result:
                content: str = item['text'].strip()  # 文本内容
                pos: list = item['position']  # 文本边框四个角的(x,y)坐标
                center_pos = self.calcCenterPos(pos)  # 文本中心点的(x,y)坐标

                y = center_pos[1]  # 当前处理的文本y坐标
                if y - center_y > delta:  # 新的一行
                    line_dict = dict()
                    horizont_index = 0
                    center_y = y
                    result.append(line_dict)

                # 对于无需记录的字段, 直接跳过
                if horizont_index >= size:
                    horizont_index += 1
                    continue

                # 需要可能记录的字段, 获取key值, 非空才记录
                value = values[horizont_index]
                if not CommonUtil.isNoneOrBlank(value):
                    line_dict[value] = content
                horizont_index += 1

        # 只保留非空白数据
        result = [x for x in result if not CommonUtil.isNoneOrBlank(x)]

        # 处理属性确实的数据, 确保每行都包含所有属性
        for item in result:
            for i in range(len(keys)):
                value = values[i]
                item_value = item.get(value, None)
                if item_value is None:
                    CommonUtil.printLog(f'缺少属性 {value}, 原数据:{item} ')
                    item[value] = ""
        # CommonUtil.printLog(f'ocr_grid_view 最终结果: {result}')
        return result

    def getWH(self) -> tuple:
        """
        获取当前设备的宽高 (width, height)
        """
        return self.airtest_device.get_current_resolution()
