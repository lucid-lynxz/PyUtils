# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys
import traceback

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.abspath(__file__))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from abc import ABCMeta
import logging
import re

__author__ = "Lynxz"

from cnocr import CnOcr
from airtest.core.api import *
from airtest.aircv import *
from util.CommonUtil import CommonUtil
from WoolProject import AbsWoolProject
from util.TimeUtil import TimeUtil
from util.FileUtil import FileUtil

"""
airtest基类, 所有子类请自行配置下: auto_setup(__file__)
子类按需重写 check_info_stream_valid(self) 方法  
"""
auto_setup(__file__)

logger = logging.getLogger("airtest")
logger.setLevel(logging.WARN)


class AbsBaseAir(AbsWoolProject):
    __metaclass__ = ABCMeta

    def __init__(self, deviceId: str, pkgName: str = '',
                 splashActPath: str = '',
                 homeActPath: str = '',
                 appName: str = '',
                 totalSec: int = 180,
                 forceRestart: bool = False):

        super().__init__(pkgName=pkgName,
                         splashActPath=splashActPath,
                         homeActPath=homeActPath,
                         appName=appName,
                         deviceId=deviceId,
                         totalSec=totalSec,
                         forceRestart=forceRestart)
        self.poco = None
        self.updateDeviceId(deviceId)
        self.stateDict: dict = {}  # 用于子类按需存储一些状态信息
        self.initStateDict()
        self.airtest_device = G.DEVICE  # airtest设备列表中的当前设备

        # 测试使用 cnocr 进行解析
        # 文档: https://cnocr.readthedocs.io/zh/latest/usage/
        # 首次安装运行时会自动下载模型, 若报错下载失败找不到模型文件,可参考下面文案手动下载模型放到报错的路径目录下
        # https://huggingface.co/breezedeus/cnstd-cnocr-models/tree/main/models/cnocr/2.2
        self.cnocrImpl: CnOcr = CnOcr()  # cnocr识别对象

    def initStateDict(self):
        pass

    def updateStateKV(self, key: str, value: object):
        self.stateDict[key] = value
        return self

    def getStateValue(self, key: str, default_value: object = None):
        return self.stateDict.get(key, default_value)

    def check_coin_dialog(self, ocrResList=None, fromX: int = 0, fromY: int = 0, retryCount: int = 2,
                          breakIfHitText: str = None):
        """
        检测当前界面的弹框,并统一处理:
        1. 对于领取红包的, 直接领取
        2. 对于看广告视频的, 点击进行跳转观看, 观看结束后返回当前页面
        :param ocrResList: cnorcr识别结果,避免重复截图识别,若为None则会重新截图及ocr
        :param fromX: ocrResList 非 None 时有效, 用于表示 ocrResList 的在屏幕上的偏移量
        :param fromY: 同上
        :param retryCount: 检测次数
        :param breakIfHitText: 观看广告视频返回到指定页面时,要停止继续返回,默认是None表示返回到 '任务中心'
        :return list: 最后一次cnocr识别结果
        """
        pass

    def continue_watch_ad_videos(self, max_secs: int = 90,  # 最多要观看的时长, 之后会通过检测 '已领取' / '已成功领取奖励' 来决定是否继续观看
                                 min_secs: int = 30,
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
        pass

    # 可能会弹出获得金币弹框, 点击关闭按钮
    def closeDialog(self, extraTpl: Template = None, autoClick: bool = True,
                    minX: int = 200, minY: int = 200, maxX: int = 0, maxY: int = 0) -> tuple:
        """
        搜索并点击关闭弹框
        :param extraTpl: 其他自定义的关闭按钮图片
        :param autoClick: 匹配到关闭按钮后是否直接点击
        :param minX:匹配到的按钮必须满足的指定的区间才认为合法
        :param maxX:匹配到的按钮必须满足的指定的区间才认为合法
        :param minY:匹配到的按钮必须满足的指定的区间才认为合法
        :param maxY:匹配到的按钮必须满足的指定的区间才认为合法
        :return tuple:(float,float) 表示匹配到的按钮坐标值, 若为空,则表示未匹配到
        """
        pass

    @logwrap
    def snapshot(self, filename=None, msg="", quality=None, max_size=None):
        if not quality:
            quality = ST.SNAPSHOT_QUALITY
        if not max_size and ST.IMAGE_MAXSIZE:
            max_size = ST.IMAGE_MAXSIZE
        if filename:
            if not os.path.isabs(filename):
                logdir = ST.LOG_DIR or "."
                filename = os.path.join(logdir, filename)
        return self.airtest_device.snapshot(filename, quality=quality, max_size=max_size)
        # return self.try_log_screen(screen, quality=quality, max_size=max_size)

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
    def text(self, text, enter=True, **kwargs):
        """
        Input text on the target device. Text input widget must be active first.
        """
        self.airtest_device.text(text, enter=enter, **kwargs)
        delay_after_operation()

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

    def updateDeviceId(self, deviceId: str):
        super().updateDeviceId(deviceId)
        connect_device("Android:///%s?cap_method=javacap&touch_method=adb" % self.deviceId)
        wake()  # 唤醒设备

        self.airtest_device = G.DEVICE
        for dev in G.DEVICE_LIST:
            if self.deviceId == dev.serialno:
                self.airtest_device = dev
                break
        self.init_poco()
        return self

    def getWH(self) -> tuple:
        """
        获取当前设备的宽高
        """
        # 经测试, pixel2xl 耗时1.6s左右,因此做下缓存, 一般挂机时不做横竖屏切换
        height = self.getStateValue('height', 0)
        width = self.getStateValue('width', 0)
        if height > 0 and width > 0:
            return width, height

        if self.airtest_device.display_info['orientation'] in [1, 3]:  # 横屏
            height = self.airtest_device.display_info['width']
            width = self.airtest_device.display_info['height']
        else:
            height = self.airtest_device.display_info['height']
            width = self.airtest_device.display_info['width']
        self.updateStateKV('height', height)
        self.updateStateKV('width', width)
        return width, height

    def saveScreenShot(self, imgName: str, fromX: int = 0, fromY: int = 0, toX: int = -1, toY: int = -1,
                       autoAppendDateInfo: bool = False) -> str:
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
        if CommonUtil.isNoneOrBlank(imgName) or autoAppendDateInfo:
            timeStr = TimeUtil.getTimeStr(format='%m%d_%H%M%S')
            imgName = '%s%s_%s_%s_%s_%s' % (imgNameOpt, timeStr, fromX, fromY, toX, toY)
        return self.saveImage(img, imgName)

    def saveImage(self, img, imgName: str = None, dirPath: str = None,
                  autoAppendDateInfo: bool = False, replaceFlag: str = '_') -> str:
        """
        保存图片到 {cacheDir} 中
        实测耗时大概0.8s左右

        :param imgName: 文件名, 会自动拼接 self.appName 和 '.png' 后缀
        :param dirPath: 图片要保存的目录,未未指定,则使用 self.cacheDir,若仍未空,则保存失败
        :param replaceFlag: 若 imageName 中存在无效字符时,替代为该字符串
        :return str: 最终保存的路径名, 若为空,则表示保存失败
        """
        if img is None:
            return ''

        if CommonUtil.isNoneOrBlank(dirPath):
            dirPath = self.cacheDir

        if CommonUtil.isNoneOrBlank(dirPath):
            return ''

        if CommonUtil.isNoneOrBlank(imgName):
            autoAppendDateInfo = True
            imgName = ''

        if autoAppendDateInfo:
            imgName = '%s_%s' % (imgName, TimeUtil.getTimeStr(format='%m%d_%H%M%S'))
        imgName = imgName.replace('(', replaceFlag).replace(')', replaceFlag) \
            .replace('|', replaceFlag).replace('.*', replaceFlag).replace('[', replaceFlag).replace(']', replaceFlag)

        try:
            pil_img = cv2_2_pil(img)
            FileUtil.createFile('%s/' % dirPath)
            model = self.adbUtil.getDeviceInfo(self.deviceId).get('model', self.deviceId)
            img_path = '%s/%s_%s/%s_%s.png' % (dirPath, model, self.deviceId, imgName, self.appName)
            img_path = FileUtil.recookPath(img_path)
            FileUtil.createFile(img_path)  # 按需创建父目录
            pil_img.save(img_path, quality=99, optimize=True)
            # self.logWarn('saveScreenShot imgPath=%s' % img_path)
            return img_path
        except Exception as e:
            traceback.print_exc()
            return ''

    def getScreenOcrResult(self, ) -> list:
        """获取当前屏幕截图的ocr结果对象"""
        screen = self.snapshot()  # 截屏
        # screen = self.airtest_device.snapshot()  # 截屏
        if screen is None:
            self.logError(f'getScreenOcrResult fail as screenshot return null')
            return None
        return self.cnocrImpl.ocr(screen)  # cnocr进行解析, 实测耗时大概0.2s

    def findTextByOCR(self, targetText: str,
                      prefixText: str = None,
                      fromX: int = 0, fromY: int = 0,
                      width: int = 0, height: int = 0,
                      swipeOverlayHeight: int = 100,
                      maxSwipeRetryCount: int = 10,
                      saveAllImages: bool = False,
                      autoSwitchPointerLocation: bool = True,
                      saveDirPath: str = None,
                      imgPrefixName: str = '',
                      autoConvertQuotes: bool = True,
                      appendStrFlag: str = ' ',
                      printCmdInfo: bool = False) -> tuple:
        """
        通过每次截图指定 height 的图片进行OCR识别,若识别到目标文本(targetText),则返回True
        每次截图前会屏幕向上滑动 height 高度, 然后截取 (fromX,fromY) -> (fromX+width,fromY+height) 长条形区域图片进行OCR
        :param targetText: 必填,要识别的文本正则表达式, 若为空, 则返回的是区域截图的ocr识别结果, pos列表为空
        :param prefixText: 要求在 targetText 之前应存在的字符串正则表达式,若为空,则表示不做判断
        :param fromX: 区域截图左上角的x坐标,默认(0,0)
        :param fromY: 区域截图左上角的Y坐标,默认(0,0)
        :param width: 区域截图宽度,0或负数表示截图到屏幕右侧边缘
        :param height: 区域截图的高度,若为0或负数,则表示截屏到屏幕底部
        :param swipeOverlayHeight:上滑时,少滑动该距离, 负数表示height的1/10
        :param maxSwipeRetryCount: 最多上滑截图的次数, 一次表示不上滑
        :param saveAllImages:是否保存每张截图,若为False,则仅保存匹配失败的截图
                        文件名格式: {cacheDir}/{deviceId}/{imgPrefixName}_{time}_index_fromX_fromY_toX_toY_{appName}.png
        :param autoSwitchPointerLocation: 是否自动关闭指针位置(避免ocr时被干扰), 识别结束后自动恢复初始状态
        :param saveDirPath: 截图保存的目录,若为空,则尝试保存到 {self.cacheDir} 中
        :param imgPrefixName: 截图前缀名称
        :param autoConvertQuotes: 是否将ocr字符串中的双引号统一转为半角字符双引号
        :param appendStrFlag: 根据ocr结果列表拼接生成完整字符串时,连续两个文本之间的连接符号,默认为一个空格
        :param printCmdInfo: 是否打印命令内容
        :return tuple (list,str,dict):
            第一个元素list: 表示匹配到的targetText区域在屏幕的四个角的坐标(已自行累加了fromX,fromY的偏移量), 若为空,则表示未识别到
            第二个元素str: 表示最终ocr得到的文本
            第三个元素list: cnocr识别的原始结果list
        """
        ocrStartTs: float = time.time()
        sWidth, sHeight = self.getWH()  # 获取当前设备宽度
        width = sWidth if width <= 0 else width
        height = sHeight if height <= 0 else height

        # 结算区域子截图的右下角坐标
        maxY = sHeight
        toX: int = fromX + width
        toY: int = fromY + height
        toX = toX if toX <= sWidth else sWidth
        toY = toY if toY <= maxY else maxY
        height = toY - fromY

        # 记录当前是否开启了 "指针位置" 功能,以便最后进行恢复
        pointerLocationOri: int = self.adbUtil.pointerLocation(value=-1, deviceId=self.deviceId)
        if autoSwitchPointerLocation:
            self.adbUtil.pointerLocation(value=0, deviceId=self.deviceId)  # 关闭指针位置

        hit: bool = False  # 是否匹配到目标文字
        posList: list = None  # 识别到的文本位置矩形框4个点的坐标列表
        ocr_str_result: str = ''  # 最后一次ocr识别的文本
        cnocr_result: list = None  # cnocr对区域截图进行识别的原始结果对象

        for i in range(maxSwipeRetryCount):
            loopStartTsBack: float = time.time()

            screen = self.snapshot()  # 截屏
            if screen is None:
                self.logError(f'findTextByOCR fail as screenshot return null')
                return None, None, None
            img = aircv.crop_image(screen, (fromX, fromY, toX, toY))  # 局部截图, 整体耗时0.15s左右

            cnocr_result = self.cnocrImpl.ocr(img)  # cnocr进行解析, 实测耗时大概0.2s
            posList, ocr_str_result, targetDict = self.findTextByCnOCRResult(cnocr_result, targetText=targetText,
                                                                             prefixText=prefixText,
                                                                             fromX=fromX, fromY=fromY,
                                                                             appendStrFlag=appendStrFlag,
                                                                             autoConvertQuotes=autoConvertQuotes)
            hit = hit or not CommonUtil.isNoneOrBlank(posList)  # 是否匹配到目标文字

            # 按需保存截图
            ocr_str_result = '' if ocr_str_result is None else ocr_str_result.strip()
            saveDirPath = self.cacheDir if CommonUtil.isNoneOrBlank(saveDirPath) else saveDirPath
            saveImg: bool = not CommonUtil.isNoneOrBlank(saveDirPath) and (saveAllImages or not hit)
            if saveImg:  # 保存图片还是耗时的0.8s左右, 占据方法的大头,因此默认只对失败的部分做截图
                loopStartTs = time.time()
                imgName = '%s_%s_%s_%s_%s_%s_%s.png' % (
                    imgPrefixName, i, fromX, fromY, toX, toY, TimeUtil.getTimeStr(format='%m%d_%H%M%S'))
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
                self.swipeUp(minDeltaY=swipeHeight, maxDeltaY=swipeHeight,
                             keepVerticalSwipe=True, durationMs=1500, printCmdInfo=printCmdInfo)
            # self.logWarn(
            #     f'findTextByOCR loopCheck {i} end duration={time.time() - loopStartTsBack}', printCmdInfo=printCmdInfo)

        # 恢复指针位置开关设置
        if autoSwitchPointerLocation:
            self.adbUtil.pointerLocation(value=pointerLocationOri, deviceId=self.deviceId)

        self.logWarn(f'findTextByOCR {not CommonUtil.isNoneOrBlank(posList)},'
                     f'{time.time() - ocrStartTs}秒,target={targetText},prefix={prefixText},'
                     f'ocr_str_result={ocr_str_result}',
                     printCmdInfo=printCmdInfo)
        return posList, ocr_str_result, cnocr_result

    def findTextByCnOCRResult(self, cnocr_result: list, targetText: str, prefixText: str = None,
                              fromX: int = 0, fromY: int = 0, autoConvertQuotes: bool = True,
                              appendStrFlag: str = ' ',
                              printCmdInfo: bool = False) -> tuple:
        """
        根据cnocr识别结果,检测是否存在目标文本(targetText),若有则该文本的位置信息
        每次截图前会屏幕向上滑动 height 高度, 然后截取 (fromX,fromY) -> (fromX+width,fromY+height) 长条形区域图片进行OCR
        :param cnocr_result: 根据cnocr框架识别得到的结果,若为空,则返回失败
        :param targetText: 必填,要识别的文本正则表达式, 若为空, 则返回的是区域截图的ocr识别结果, pos列表为空
        :param prefixText: 要求在 targetText 之前应存在的字符串正则表达式,若为空,则表示不做判断
        :param fromX: 区域截图左上角的x坐标,默认(0,0)
        :param fromY: 区域截图左上角的Y坐标,默认(0,0)
        :param autoConvertQuotes: 是否将ocr字符串中的双引号统一转为半角字符双引号
        :param appendStrFlag: 根据ocr结果列表拼接生成完整字符串时,连续两个文本之间的连接符号,默认为一个空格
        :return tuple (list,str,dict): 三个元素都可能为空
            第一个元素list: 表示匹配到的targetText区域在屏幕的四个角的坐标(已自行累加了fromX,fromY的偏移量), 若为空,则表示未识别到
            第二个元素str:  表示最终ocr得到的文本
            第三个元素dict: cnocr识别到的该文本对应的其他信息dict,包含 text/score/position
        """
        if CommonUtil.isNoneOrBlank(cnocr_result):
            return None, None, None
        hit: bool = False  # 是否匹配到目标文字
        targetDict: dict = None  # 目标文本信息, 包含 text/score/position
        ocr_str_result: str = ''  # 最后一次ocr识别的文本
        hitPrefixText: bool = CommonUtil.isNoneOrBlank(prefixText)
        targetTextPattern = None if CommonUtil.isNoneOrBlank(targetText) else re.compile(targetText)
        prefixTextPattern = None
        if not hitPrefixText:
            prefixTextPattern = re.compile(prefixText)

        for index in range(len(cnocr_result)):
            dictItem: dict = cnocr_result[index]
            t = dictItem.get('text', '')
            ocr_str_result = '%s%s%s' % (ocr_str_result, appendStrFlag, t)

            if not hitPrefixText:
                resultList = prefixTextPattern.findall(t)
                if not CommonUtil.isNoneOrBlank(resultList):  # 匹配到前置文本
                    hitPrefixText = True
                    continue

            if not hitPrefixText or hit:
                continue

            # 匹配到目标文本后
            resultList = None if targetTextPattern is None else targetTextPattern.findall(t)
            hit = not CommonUtil.isNoneOrBlank(resultList)
            if hit:
                targetDict = dictItem

        # 偏移得到屏幕中的绝对坐标
        posList = None if targetDict is None else targetDict.get('position', None)
        if not CommonUtil.isNoneOrBlank(posList):
            for item in posList:
                item[0] = item[0] + fromX
                item[1] = item[1] + fromY

        # 对ocr文本结果中的引号进行格式化处理
        if autoConvertQuotes:
            ocr_str_result = ocr_str_result.replace('＂', '"').replace('“', '"').replace('”', '"')
        self.logWarn(
            f'findTextByCnOCRResult {not CommonUtil.isNoneOrBlank(posList)} '
            f'targetText={targetText},prefixText={prefixText},ocr_str={ocr_str_result}')
        return posList, ocr_str_result, targetDict

    def check_if_in_page(self, targetText: str, prefixText: str = None, ocrResList=None, height: int = 0,
                         maxRetryCount: int = 3) -> bool:
        """
        检测当前是否在指定的页面
        :param targetText:页面上必须存在的信息,正则表达式,若为空,则直接返回True
        :param prefixText: 特定信息前面必须存在的字符串,支持正则
        :param ocrResList: cnocr识别结果,若为空,则会进行一次ocr识别
        :param height: 若需要进行截图ocr,则ocr的高度是多少
        :param maxRetryCount: 识别重试次数, 若当前识别失败,则下一轮必然重新ocr
        :return bool: 是否在目标页面
        """
        if CommonUtil.isNoneOrBlank(targetText):
            return True
        for index in range(maxRetryCount):
            if ocrResList is None:  # 重新ocr
                pos, ocrResStr, _ = self.findTextByOCR(targetText, height=height, prefixText=prefixText,
                                                       maxSwipeRetryCount=1)
            else:  # 复用原先的ocr结果
                pos, ocrResStr, _ = self.findTextByCnOCRResult(ocrResList, targetText=targetText, prefixText=prefixText)

            if CommonUtil.isNoneOrBlank(ocrResStr) or len(ocrResStr) <= 30:
                self.logWarn(f'check_if_in_page fail ocrResStr is too short,wait')
                self.sleep(3)
                continue

            if CommonUtil.isNoneOrBlank(pos):  # 未找到目标文本
                img_path = self.saveScreenShot(f'未找到_{targetText}_{prefixText}_{index}', autoAppendDateInfo=True)
                self.logWarn(
                    f'check_if_in_page 未找到:{targetText}, index={index},prefixText={prefixText},'
                    f'img_path={img_path}\nocrResStr={ocrResStr}')
                self.check_coin_dialog()  # 可能是有弹框覆盖
                self.sleep(2)  # 可能是未加载完成,等待2s再试
                ocrResList = None  # 置空,下一轮强制重新ocr
            else:
                return True
        return False

    def calcCenterPos(self, ltrb: list) -> tuple:
        """
        给定矩形框4个顶点的坐标,计算其中心点坐标(x,y)
        :param ltrb: 4个顶点坐标,依次为左上,右上,右下,左下, 每个元素包含是个list, list中包含两个float子元素,依次表示x,y的位置
        :return tuple: 中心点的坐标(x,y) x,y的类型是float, 若输入为空,则返回空白元组 ()
        """
        if CommonUtil.isNoneOrBlank(ltrb) or len(ltrb) < 3:
            return ()
        lt = ltrb[0]
        rt = ltrb[1]
        rb = ltrb[2]
        # lb = ltrb[3]
        centerX = lt[0] + (rt[0] - lt[0]) / 2
        centerY = rt[1] + (rb[1] - rt[1]) / 2
        return centerX, centerY

    def tapByTuple(self, posTuple: tuple, deviceId: str = None, times: int = 1, sleepSec: float = 1.5,
                   printCmdInfo: bool = False) -> bool:
        return self.adbUtil.tapByTuple(posTuple, deviceId=deviceId, times=times, sleepSec=sleepSec,
                                       printCmdInfo=printCmdInfo)

    def init_poco(self):
        """若有需要使用到poco,请启用本方法进行初始化"""
        # if self.poco is None:
        #     self.poco = AndroidUiautomationPoco(device=self.airtest_device,
        #                                         use_airtest_input=True,
        #                                         screenshot_each_action=False)
        return self

    def onRun(self, **kwargs):
        self.runAction(self.informationStreamPageAction, totalSec=self.totalSec, func=self.check_info_stream_valid)

    def check_info_stream_valid(self, forceRecheck: bool = False) -> bool:
        """检测当前信息流页面是否有必要挂机(主要是判断是否有奖励)"""
        return self.check_current_at_info_stream_page(forceRecheck=forceRecheck)

    def check_current_at_info_stream_page(self, keywordInPage: str = None, auto_enter_stream_page: bool = True,
                                          forceRecheck: bool = False) -> bool:
        """检测当前位于信息流页面, 若当前未位于信息流页面,则自动通过 goto_home_information_tab() 跳转"""
        name, keyword = self.get_home_tab_name()
        return self.check_if_in_page(targetText=keyword)

    def goto_home_information_tab(self, enableByRestartApp: bool = True) -> bool:
        """
        跳转到信息流页面
        :param enableByRestartApp: 是否允许重启app后再做点击
        :return bool: 是否跳转成功
        """
        name, targetPageKeyword = self.get_home_tab_name()
        return self.goto_home_sub_tab(name=name,
                                      targetPageKeyword=targetPageKeyword,
                                      enableByRestartApp=enableByRestartApp)

    def goto_home_earn_tab(self, sleepSecsInPage: int = 2, enableByRestartApp: bool = True) -> bool:
        """
        跳转到赚钱任务页面
        """
        earnName, earnPageKeyword = self.get_earn_monkey_tab_name()
        return self.goto_home_sub_tab(name=earnName, prefixText=None,
                                      targetPageKeyword=earnPageKeyword,
                                      sleepSecsInPage=sleepSecsInPage,
                                      enableByRestartApp=enableByRestartApp)


if __name__ == '__main__':
    air = AbsBaseAir(deviceId='0A221FDD40006J')
    pos, ocr_str, _ = air.findTextByOCR('看小说', swipeOverlayHeight=300,
                                        height=1200, saveDirPath='H:/wool_cache/', )
    print('pos=%s' % pos)
    cx, cy = air.calcCenterPos(pos)
    print('cx,cy=%s,%s' % (cx, cy))
    air.adbUtil.tap(cx, cy)
