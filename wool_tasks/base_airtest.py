# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys
import traceback

from util.NetUtil import NetUtil

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from abc import ABCMeta
import logging
import re

__author__ = "Lynxz"

from typing import Union
from cnocr import CnOcr
from airtest.core.api import *
from airtest.aircv import *
from base.TaskManager import TaskManager, TaskLifeCycle
from util.CommonUtil import CommonUtil
from WoolProject import AbsWoolProject
from util.TimeUtil import TimeUtil
from util.FileUtil import FileUtil
from util.decorator import log_wrap

"""
airtest基类, 所有子类请自行配置下: auto_setup(__file__)
子类按需重写 check_info_stream_valid(self) 方法  
"""
auto_setup(__file__)

logger = logging.getLogger("airtest")
logger.setLevel(logging.WARN)


class AbsBaseAir(AbsWoolProject):
    __metaclass__ = ABCMeta
    key_minStreamSecs = 'key_minStreamSecs'  # 信息流页面需要刷多久后才允许执行其他操作,默认5min
    key_lastStreamTs = 'key_lastStreamTs'  # 上次刷信息流时跳转的时间戳,单位:s

    def __init__(self, deviceId: str, pkgName: str = '',
                 splashActPath: str = '',
                 homeActPath: str = '',
                 appName: str = '',
                 totalSec: int = 180,
                 forceRestart: bool = False):

        self.poco = None
        self.airtest_device = None  # airtest设备列表中的当前设备

        # 测试使用 cnocr 进行解析
        # 文档: https://cnocr.readthedocs.io/zh/latest/usage/
        # 首次安装运行时会自动下载模型, 若报错下载失败找不到模型文件,可参考下面文案手动下载模型放到报错的路径目录下
        # https://huggingface.co/breezedeus/cnstd-cnocr-models/tree/main/models/cnocr/2.2
        self.cnocrImpl: CnOcr = CnOcr()  # cnocr识别对象

        super().__init__(pkgName=pkgName,
                         splashActPath=splashActPath,
                         homeActPath=homeActPath,
                         appName=appName,
                         deviceId=deviceId,
                         totalSec=totalSec,
                         forceRestart=forceRestart)

    def kan_zhibo_in_page(self, count: int = 1,  # 总共需要看几次直播
                          max_sec: int = 60,  # 每个直播最多需要观看的时长
                          zhiboHomePageTitle: str = r'^看直播领金.',  # 直播列表首页的标题名,用于判断是否跳转到直播详情成功
                          autoBack2Home: bool = True):
        pass

    @log_wrap(print_out_obj=False, print_caller=True)
    def continue_watch_ad_videos(self, max_secs: int = 90,  # 最多要观看的时长, 之后会通过检测 '已领取' / '已成功领取奖励' 来决定是否继续观看
                                 min_secs: int = 10,
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

    # 可能会弹出获得金币弹框, 点击关闭按钮, 耗时比较久, 建议是想检测特定文本后按需触发
    @log_wrap(print_caller=True)
    def closeDialog(self, extraImg: str = None, autoClick: bool = True,
                    minX: int = 200, minY: int = 200, maxX: int = 0, maxY: int = 0) -> tuple:
        """
        搜索并点击关闭弹框
        :param extraImg: 其他自定义的关闭按钮图片相对路径,会优先匹配该图片
        :param autoClick: 匹配到关闭按钮后是否直接点击
        :param minX:匹配到的按钮必须满足的指定的区间才认为合法
        :param maxX:匹配到的按钮必须满足的指定的区间才认为合法
        :param minY:匹配到的按钮必须满足的指定的区间才认为合法
        :param maxY:匹配到的按钮必须满足的指定的区间才认为合法
        :return tuple:(float,float) 表示匹配到的按钮坐标值, 若为空,则表示未匹配到
        """
        pass

    @log_wrap(exclude_arg={'self', 'cnocr_result'})
    def get_rest_chance_count(self, title: str,
                              subTitle: str,
                              cnocr_result: list = None,
                              appendStrFlag: str = '') -> tuple:
        """
        要求当前已在赚钱任务页面
        比如搜索/看直播等活动,每天有限额,通过本方法根据 subTitle 信息获取剩余可用次数
        1. 优先进行ocr单行匹配
        2. 对完整的ocr结果进行匹配

        :param title: 标题行
        :param subTitle: 正则表达式要求至少包含一个 '(\\d+/\\d+)' 表示已完成次数和总次数
        :param cnocr_result: 若已有ocr识别结果,则直接服用,否则重新ocr
        :param appendStrFlag: 根据ocr结果列表拼接生成完整字符串时,连续两个文本之间的连接符号,默认为一个空格
        :return tuple: (int,int)  completeCount, totalCount 依次表示已使用的次数, 总次数
        """
        completeCount: int = 0
        totalCount: int = 0
        if cnocr_result is None:
            pos, ocrStr, ocrResultList = self.findTextByOCR(subTitle, prefixText=title,
                                                            swipeOverlayHeight=300,
                                                            height=1400, appendStrFlag=appendStrFlag)
        else:
            pos, ocrStr, ocrResultDict = self.findTextByCnOCRResult(cnocr_result, targetText=subTitle,
                                                                    prefixText=title, appendStrFlag=appendStrFlag)
            if not CommonUtil.isNoneOrBlank(ocrResultDict):
                subTitleText = ocrResultDict.get('text', '')
                ocrStr = ocrStr if CommonUtil.isNoneOrBlank(subTitleText) else subTitleText

        if CommonUtil.isNoneOrBlank(ocrStr):
            return completeCount, totalCount

        pattern = re.compile(subTitle)  # 如果已搜索过,还有剩余搜索机会的话,此时可能没有 '去搜索' 按钮, 而是倒计时按钮
        resultList = pattern.findall(ocrStr)
        if CommonUtil.isNoneOrBlank(resultList):
            return completeCount, totalCount
        else:
            chancesInfo = resultList[0]
            if '/' in chancesInfo:
                arr = chancesInfo.split('/')
                if len(arr) >= 2:
                    completeCount = CommonUtil.convertStr2Int(arr[0], 0)
                    totalCount = CommonUtil.convertStr2Int(arr[1], 0)
        self.logWarn(f'已完成:{chancesInfo},complete={completeCount},total={totalCount},ocrStr={ocrStr}')
        return completeCount, totalCount

    def search_by_input(self, keyword: str, hintListKeyword: str = r'搜索有奖',
                        viewSec: int = 20, ignoreCase: bool = True) -> bool:
        """
        要求当前已在搜索页面,且光标已定位到搜索输入框
        则会自动输入部分keyword,并尝试匹配:
         1. '搜索有奖'
         2. 入参的 'keyword' 完整内容
         3. 比输入的部分keyword更长的提示项
         返回是否输入搜索成功
         :param keyword: 完整的搜索关键字
         :param hintListKeyword: 输入keyword后可能会弹出提示列表,点选带有 hintListKeyword 的item
         :param viewSec: 若搜索成功,则浏览搜索结果的时长,单位:s, 大于0有效,浏览完成后仍在当前页面
         :param ignoreCase: 是否忽略大小写
         :return bool:是否搜索成功
        """
        # 由于使用 yosemite 等输入直接键入文本时,获得金币约等于无,此处尝试只输入一半内容,然后通过下拉提示列表进行点击触发关键字输入
        length = len(keyword)
        inputKWIndex: int = length if length <= 8 else int(length / 2)
        inputKW: str = keyword[0:inputKWIndex]  # 实际输入的关键字内容
        self.logWarn(f'尝试输入搜索关键字: {inputKW}  完整的关键字为:{keyword}')
        self.text(inputKW, search=False)  # 输入关键字,进行搜索
        self.sleep(2)

        pos, ocrStr, ocrResList = self.findTextByOCR(targetText=inputKW, subfixText=r'搜索',
                                                     height=800, maxSwipeRetryCount=1)
        if CommonUtil.isNoneOrBlank(pos):
            img_path = self.saveScreenShot(f'search_by_input_fail_input_fail', autoAppendDateInfo=True)
            self.logWarn(f'search_by_input fail 未输入成功,kw={inputKW},img_path={img_path}')
            return False

        # 检测下拉提示列表
        success: bool = False
        for checkIndex in range(3):
            pos, ocrStr, ocrResList = self.findTextByOCR(hintListKeyword, prefixText=inputKW,
                                                         height=800, maxSwipeRetryCount=1)
            success = self.tapByTuple(self.calcCenterPos(pos))
            self.logWarn(f'search_by_input 尝试匹配搜索有奖提示语 success={success},ocrStr={ocrStr}')
            if not success:  # 未找到 '搜索有奖' 时,表明对关键字无要求,直接点击比输入值更长的文本即可
                pos, ocrStr, _ = self.findTextByCnOCRResult(ocrResList, keyword, prefixText='搜索')
                success = self.tapByTuple(self.calcCenterPos(pos))
                if not success:
                    pos, ocrStr, _ = self.findTextByCnOCRResult(ocrResList, r'%s.+' % inputKW, prefixText=inputKW)
                    pos = self.calcCenterPos(pos)
                    self.logWarn(f'search_by_input 查找比输入更长的提示语 pos={pos}')
                    success = self.tapByTuple(pos)
                    if not success:
                        pos, ocrStr, _ = self.findTextByCnOCRResult(ocrResList, r'搜索')
                        pos = self.calcCenterPos(pos)
                        self.logWarn(f'search_by_input fail 直接点击 "搜索" 按钮: pos={pos}')
                        success = self.tapByTuple(pos)

                if self.findTextByCnOCRResult(cnocr_result=ocrResList, targetText=r'浏览\d+秒可得搜索金币'):
                    success = True

            if not success:
                self.logWarn(f'search input kw fail wait 3s:{inputKW}')
                self.sleep(3)
            else:
                self.logWarn(f'search input kw success:{inputKW}, ocrStr={ocrStr}')
                break

        # 浏览指定的时长
        if success and viewSec > 0:
            totalSec: float = 0
            while True:
                self.sleep(4)
                self.swipeUp(durationMs=1000)
                totalSec = totalSec + 5
                if totalSec > viewSec:
                    break
        return success

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

    @log_wrap(print_out_obj=False, print_caller=True)
    def updateDeviceId(self, deviceId: str):
        if not CommonUtil.isNoneOrBlank(
                self.deviceId) and self.deviceId == deviceId and self.airtest_device is not None:
            return self

        super().updateDeviceId(deviceId)
        connect_device("Android:///%s?cap_method=javacap&touch_method=adb" % self.deviceId)
        wake()  # 唤醒设备
        set_current(self.deviceId)
        self.airtest_device = G.DEVICE
        # for dev in G.DEVICE_LIST:
        #     if self.deviceId == dev.serialno:
        #         self.airtest_device = dev
        #         break
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

    def getScreenOcrResult(self, autoSwitchPointerLocation: bool = True,
                           fromX: int = 0, fromY: int = 0, toX: int = 0, toY: int = 0) -> list:
        """获取当前屏幕截图的ocr结果对象"""
        # 记录当前是否开启了 "指针位置" 功能,以便最后进行恢复
        pointerLocationOri: int = self.adbUtil.pointerLocation(value=-1, deviceId=self.deviceId)
        if autoSwitchPointerLocation:
            self.adbUtil.pointerLocation(value=0, deviceId=self.deviceId)  # 关闭指针位置

        screen = self.snapshot()  # 截屏

        # 恢复指针位置开关设置
        if autoSwitchPointerLocation:
            self.adbUtil.pointerLocation(value=pointerLocationOri, deviceId=self.deviceId)

        # screen = self.airtest_device.snapshot()  # 截屏
        if screen is None:
            self.logError(f'getScreenOcrResult fail as screenshot return null')
            return None

        if not fromX == fromY == toX == toY == 0:
            sWidth, sHeight = self.getWH()  # 获取当前设备宽度
            toX = toX if 0 < toX < sWidth else sWidth
            toY = toY if 0 < toY < sHeight else sHeight
            screen = self.snapshot()  # 截屏
            screen = aircv.crop_image(screen, (fromX, fromY, toX, toY))  # 局部截图

        return self.cnocrImpl.ocr(screen)  # cnocr进行解析, 实测耗时大概0.2s

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

    def findTextByOCR(self, targetText: str,
                      prefixText: str = None,
                      subfixText: str = None,
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
                      ignoreCase: bool = True,
                      printCmdInfo: bool = False) -> tuple:
        """
        通过每次截图指定 height 的图片进行OCR识别,若识别到目标文本(targetText),则返回True
        每次截图前会屏幕向上滑动 height 高度, 然后截取 (fromX,fromY) -> (fromX+width,fromY+height) 长条形区域图片进行OCR
        :param targetText: 必填,要识别的文本正则表达式, 若为空, 则返回的是区域截图的ocr识别结果, pos列表为空
        :param prefixText: 要求在 targetText 之前应存在的字符串正则表达式,若为空,则表示不做判断
        :param subfixText: 要求在 targetText 之后应存在的字符串正则表达式,若为空,则表示不做判断
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
        :param ignoreCase: 正则匹配字符串时,是否忽略大小写
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
            screen = self.snapshot()  # 截屏
            if screen is None:
                self.logError(f'findTextByOCR fail as screenshot return null')
                return None, '', None
            img = aircv.crop_image(screen, (fromX, fromY, toX, toY))  # 局部截图, 整体耗时0.15s左右

            cnocr_result = self.cnocrImpl.ocr(img)  # cnocr进行解析, 实测耗时大概0.2s
            posList, ocr_str_result, targetDict = self.findTextByCnOCRResult(cnocr_result, targetText=targetText,
                                                                             prefixText=prefixText,
                                                                             subfixText=subfixText,
                                                                             fromX=fromX, fromY=fromY,
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

        # 恢复指针位置开关设置
        if autoSwitchPointerLocation:
            self.adbUtil.pointerLocation(value=pointerLocationOri, deviceId=self.deviceId)

        self.logWarn(f'findTextByOCR {not CommonUtil.isNoneOrBlank(posList)},'
                     f'{time.time() - ocrStartTs}秒,target={targetText},prefix={prefixText},'
                     f'ocr_str_result={ocr_str_result}',
                     printCmdInfo=printCmdInfo)
        return posList, ocr_str_result, cnocr_result

    def _make_re_compile_obj(self, targetText: str, ignoreCase: bool = True) -> re.Pattern:
        targetTextPattern = None
        if not CommonUtil.isNoneOrBlank(targetText):
            targetTextPattern = re.compile(targetText, re.IGNORECASE) if ignoreCase else re.compile(targetText)
        return targetTextPattern

    def findTextByCnOCRResult(self, cnocr_result: list, targetText: str, prefixText: str = None,
                              subfixText: str = None,
                              fromX: int = 0, fromY: int = 0, autoConvertQuotes: bool = True,
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

        # 偏移得到屏幕中的绝对坐标
        posList = None if targetDict is None else targetDict.get('position', None)
        if not CommonUtil.isNoneOrBlank(posList):
            for item in posList:
                item[0] = item[0] + fromX
                item[1] = item[1] + fromY

        # 对ocr文本结果中的引号进行格式化处理
        if autoConvertQuotes:
            ocr_str_result = ocr_str_result.replace('＂', '"').replace('“', '"').replace('”', '"')

        valid = not CommonUtil.isNoneOrBlank(posList) and hitSubfixText
        if printCmdInfo or valid:
            self.logWarn(
                f'findTextByCnOCRResult {valid},hitSubfixText={hitSubfixText}'
                f',targetText={targetText},prefixText={prefixText},subfix={subfixText}'
                f',ocr_str={ocr_str_result}')
        if not valid:
            return None, ocr_str_result, None
        return posList, ocr_str_result, targetDict

    @log_wrap(print_caller=True, exclude_arg=['self', 'ocrResList'])
    def check_if_in_page(self, targetText: str, prefixText: str = None, ocrResList=None, height: int = 0,
                         maxRetryCount: int = 1, autoCheckDialog: bool = True, minOcrLen: int = 20) -> bool:
        """
        检测当前是否在指定的页面
        :param targetText:页面上必须存在的信息,正则表达式,若为空,则直接返回True
        :param prefixText: 特定信息前面必须存在的字符串,支持正则
        :param ocrResList: cnocr识别结果,若为空,则会进行一次ocr识别
        :param height: 若需要进行截图ocr,则ocr的高度是多少
        :param maxRetryCount: 识别重试次数, 若当前识别失败,则下一轮必然重新ocr
        :param autoCheckDialog: 是否自动检测弹框,默认True
        :param minOcrLen: 要求ocr得到的文本总长度不能小于该值,否则认为识别失败
        :return bool: 是否在目标页面
        """
        if CommonUtil.isNoneOrBlank(targetText):
            return True
        for index in range(maxRetryCount):
            if ocrResList is None:  # 重新ocr
                pos, ocrResStr, ocrResList = self.findTextByOCR(targetText, height=height, prefixText=prefixText,
                                                                maxSwipeRetryCount=1)
            else:  # 复用原先的ocr结果
                pos, ocrResStr, _ = self.findTextByCnOCRResult(ocrResList, targetText=targetText, prefixText=prefixText)

            if not CommonUtil.isNoneOrBlank(pos):  # 找到目标文本
                return True

            if maxRetryCount <= 1:  # 只允许匹配一次,则直接返回
                return False

            # 检测文本长度
            if CommonUtil.isNoneOrBlank(ocrResStr) or len(ocrResStr) <= minOcrLen:
                self.logWarn(f'check_if_in_page fail ocrResStr is too short,wait:ocrResStr={ocrResStr}')
                ocrResList = None
                self.sleep(2)
                continue

            img_path = self.saveScreenShot(f'未找到_{targetText}_{prefixText}_{index}', autoAppendDateInfo=True)
            self.logWarn(
                f'check_if_in_page 未找到:{targetText}, index={index},prefixText={prefixText},'
                f'img_path={img_path}\nocrResStr={ocrResStr}')
            if autoCheckDialog:
                ocrResList = self.check_dialog(breakIfHitText=targetText)  # 可能是有弹框覆盖, 此处不做弹框检测,避免死循环
            else:
                self.sleep(2)  # 可能是未加载完成,等待2s再试
                ocrResList = None  # 置空,下一轮强制重新ocr
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

    def tapByTuple(self, posTuple: tuple, deviceId: str = None, times: int = 1, sleepSec: float = 3,
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

    def canDoOthersWhenInStream(self, autoUpdate: bool = True) -> bool:
        """
        当前正在刷信息流页面时,是否允许跳转到其他页面执行刷金币操作
        在信息流页面每刷一页就会重新计算一次
        :param autoUpdate:检测到允许跳转时, 是否刷新时间戳,默认:True
        """
        minStreamSec: int = self.getStateValue(AbsBaseAir.key_minStreamSecs, 0)  # 最短间隔时长,单位:s
        lastStreamTs: float = self.getStateValue(AbsBaseAir.key_lastStreamTs, 0)  # 上次跳转的时间戳
        curTs: float = time.time()
        if curTs - lastStreamTs >= minStreamSec:
            self.logWarn(
                f'canDoOthersWhenInStream true minStreamSec={minStreamSec},lastStreamTs={lastStreamTs},curTs={curTs}')
            if autoUpdate:
                self.updateStateKV(AbsBaseAir.key_lastStreamTs, curTs)
            return True
        else:
            return False

    def check_info_stream_valid(self, forceRecheck: bool = False) -> bool:
        """检测当前信息流页面是否有必要挂机(主要是判断是否有奖励)"""
        if self.canDoOthersWhenInStream():
            self.perform_earn_tab_actions()
            self.back_until_info_stream_page()  # 返回首页
            forceRecheck = True  # 可能跳转新页面了,需要重新检测
        return self.check_if_in_info_stream_page(forceRecheck=forceRecheck)

    @log_wrap(print_out_obj=False)
    def perform_earn_tab_actions(self, tag: Union[str, list] = 'earn_page_action', maxSwipeCount: int = 8,
                                 back2HomeStramTab: bool = False, filterFuncNames: set = None):
        """
        跳转到去赚钱页面,然后执行各任务
        :param tag: 需要自行的任务task tag, 可只传入一个,或者list
        :param maxSwipeCount: 在赚钱任务页面最多下滑次数
        :param back2HomeStramTab: 执行完毕后是否回退到首页信息流页面
        :param filterFuncNames: 若非空,则只执行包含的方法
        """
        if not self.check_if_in_earn_page() and not self.goto_home_earn_tab():
            self.logWarn(f'perform_earn_tab_actions fail as not in earn page')
            return self
        earnName, earnKeyword = self.get_earn_monkey_tab_name()
        earnFuncList = list()
        if isinstance(tag, str):
            earnFuncList = TaskManager.getTaskList(tag, taskLifeCycle=TaskLifeCycle.custom)
        elif isinstance(tag, list):
            for tTag in tag:
                tEarnFuncList = TaskManager.getTaskList(tTag, taskLifeCycle=TaskLifeCycle.custom)
                if not CommonUtil.isNoneOrBlank(tEarnFuncList):
                    earnFuncList = earnFuncList + tEarnFuncList

        ocrResList = self.getScreenOcrResult()
        for _ in range(maxSwipeCount):
            for item in earnFuncList:
                funcName: str = item.__name__
                if not CommonUtil.isNoneOrBlank(filterFuncNames) and funcName not in filterFuncNames:
                    continue

                # self.logWarn(f'perform_earn_tab_actions action: {funcName}')
                consumed = item(baseAir=self, ocrResList=ocrResList, breakIfHitText=earnKeyword)
                if consumed:
                    self.logWarn(f'perform_earn_tab_actions consumed: {funcName}')
                    if not self.check_if_in_earn_page(autoCheckDialog=True):
                        if self.check_if_in_info_stream_page():
                            self.goto_home_earn_tab()
                        else:
                            self.back_until_info_stream_page()
                            self.goto_home_earn_tab()

                        if not self.check_if_in_earn_page(autoCheckDialog=True):
                            self.logWarn(f'当前已不在赚钱页面,退出继续执行赚钱任务')
                            break
                        self.sleep(2)  # 页面信息可能变化, 等待一会再ocr
                        ocrResList = self.getScreenOcrResult()
            self.back_until_earn_page(ocrResList=ocrResList)  # 返回到赚钱页面
            self.swipeUp(minDeltaY=1000, maxDeltaY=1000, keepVerticalSwipe=True, durationMs=1500)  # 下滑一页
            ocrResList = self.check_dialog(breakIfHitText=earnKeyword)  # 检测可能的弹框

        self.back_until_earn_page()  # 执行完成,返回到赚钱页面
        if back2HomeStramTab:
            self.back_until_info_stream_page()  # 返回信息流页面
        return self

    def common_log_info(self) -> str:
        if self.airtest_device is None:
            return ''
        serialNo = self.airtest_device.serialno
        if self.deviceId != serialNo:
            NetUtil.push_to_robot(f'当前设备号与air dev序列号不符,serialNo={serialNo},deviceId={self.deviceId}',
                                  self.notificationRobotDict)
        return ''


if __name__ == '__main__':
    air = AbsBaseAir(deviceId='0A221FDD40006J')
    pos1, ocr_str, _ = air.findTextByOCR('看小说', swipeOverlayHeight=300,
                                         height=1200, saveDirPath='H:/wool_cache/', )
    print('pos=%s' % pos1)
    cx, cy = air.calcCenterPos(pos1)
    print('cx,cy=%s,%s' % (cx, cy))
    air.adbUtil.tap(cx, cy)
