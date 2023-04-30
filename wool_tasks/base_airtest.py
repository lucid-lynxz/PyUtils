# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.abspath(__file__))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from abc import ABCMeta

__author__ = "Lynxz"

from airtest.core.api import *
from airtest.aircv import *
from poco.drivers.android.uiautomation import AndroidUiautomationPoco
from util.CommonUtil import CommonUtil
from WoolProject import AbsWoolProject
from util.TimeUtil import TimeUtil
from util.FileUtil import FileUtil

"""
airtest基类, 所有子类请自行配置下: auto_setup(__file__)
子类按需重写 check_info_stream_valid(self) 方法  
"""
auto_setup(__file__)


class AbsBaseAir(AbsWoolProject):
    __metaclass__ = ABCMeta

    def __init__(self, deviceId: str, pkgName: str = '',
                 homeActPath: str = '',
                 forceRestart: bool = False):

        super().__init__(pkgName=pkgName,
                         homeActPath=homeActPath,
                         deviceId=deviceId,
                         forceRestart=forceRestart)
        self.poco = None
        if not CommonUtil.isNoneOrBlank(deviceId):
            connect_device("Android:///%s?cap_method=javacap&touch_method=adb" % deviceId)
            wake()  # 唤醒设备

    def updateDeviceId(self, deviceId: str):
        super().updateDeviceId(deviceId)
        if not CommonUtil.isNoneOrBlank(deviceId):
            self.init_poco()
            connect_device("Android:///%s?cap_method=javacap&touch_method=adb" % deviceId)
            wake()  # 唤醒设备
        return self

    def getWH(self) -> tuple:
        """
        获取当前设备的宽高
        """
        if G.DEVICE.display_info['orientation'] in [1, 3]:  # 横屏
            height = G.DEVICE.display_info['width']
            width = G.DEVICE.display_info['height']
        else:
            height = G.DEVICE.display_info['height']
            width = G.DEVICE.display_info['width']
        return width, height

    def findTextByOCR(self, targetText: str,
                      fromX: int = 0, fromY: int = 0,
                      width: int = 0, height: int = 200,
                      maxTryHeight: int = 3800,
                      saveAllImages: bool = False,
                      saveDirPath: str = None) -> tuple:
        """
        通过每次截图指定 height 的图片进行OCR识别,若识别到目标文本(targetText),则返回True
        每次截图前会屏幕向上滑动 height 高度, 然后截取 (fromX,fromY) -> (fromX+width,fromY+height) 长条形区域图片进行OCR
        :param targetText: 要识别的文本,建议不要太精确并且要有唯一性
        :param fromX: 区域截图左上角的x坐标,默认(0,0)
        :param fromY: 区域截图左上角的Y坐标,默认(0,0)
        :param width: 区域截图宽度,0或负数表示截图到屏幕右侧边缘
        :param height: 区域截图的高度,默认200像素
        :param maxTryHeight: 最多上滑截图的高度
        :param saveAllImages:是否保存每张截图,若为False,则仅保存匹配成功的截图,格式:img_index_x_y_x_y_{time}.png
        :param saveDirPath: 截图保存的目录,若为空,则不保存
        :return tuple: (bool,str,str) 依次表示是否匹配到目标文字,最后一次OCR结果字符串,保存的截图路径(可能为空)
        """
        from PIL import Image
        import pytesseract
        print(pytesseract.get_languages(config=''))  # 打印pytesseract支持的语言
        sWidth, sHeight = self.getWH()  # 获取当前设备宽度
        width = sWidth if width <= 0 else width
        count = int(maxTryHeight // height)  # 计算最多上滑重试的次数

        # 结算区域子截图的右下角坐标
        toX: int = fromX + width
        toY: int = fromY + height
        toX = toX if toX <= sWidth else sWidth
        toY = toY if toY <= sHeight else sHeight

        hit: bool = False  # 是否匹配到目标文字
        ocr_str: str = ''  # ocr识别结果
        save_img_path: str = ''  # 截图保存路径
        for i in range(count):
            screen = G.DEVICE.snapshot()  # 截屏
            img = aircv.crop_image(screen, (fromX, fromY, toX, toY))  # 局部截图

            # result = pytesseract.image_to_string(Image.open(imgPath), lang='chi_sim+eng')
            result = pytesseract.image_to_string(Image.open(img), lang='chi_sim+eng')  # ocr识别
            print(result)
            ocr_str = result
            if targetText in result:  # 判断是否包含目标文本
                hit = True

            # 按需保存截图
            saveImg: bool = not CommonUtil.isNoneOrBlank(saveDirPath) and (saveAllImages or hit)
            if saveImg:
                pil_img = cv2_2_pil(img)

                FileUtil.createFile('%s/' % saveDirPath)
                img_path = '%s/img_%s_%s_%s_%s_%s_%s.png' % (saveDirPath,
                                                             i, fromX, fromY, toX, toY,
                                                             TimeUtil.getTimeStr(format='%Y%m%d_%H%M%S'))
                img_path = FileUtil.recookPath(img_path)
                pil_img.save(img_path, quality=99, optimize=True)
                save_img_path = img_path

            # 匹配到目标文本,则退出重试
            if hit:
                break
        return hit, ocr_str, save_img_path

    def init_poco(self):
        """若有需要使用到poco,请调用本方法进行初始化"""
        if self.poco is None:
            self.poco = AndroidUiautomationPoco(use_airtest_input=True, screenshot_each_action=False)
        return self

    def onRun(self, **kwargs):
        print('base airtest onRun')
        super().informationStreamPageAction(totalSec=self.totalSec, func=self.check_info_stream_valid)

    def check_info_stream_valid(self) -> bool:
        """检测当前信息流页面是否有必要挂机(主要是判断是否有奖励)"""
        return True
        # # 青少年模式弹框
        # sleep(1)
        # pos = exists(Template(r"tpl1682341795371.png", record_pos=(0.004, 0.549), resolution=(1080, 2340)))
        # if pos:
        #     touch(Template(r"tpl1682341868524.png", record_pos=(0.007, 0.891), resolution=(1080, 2340)))
