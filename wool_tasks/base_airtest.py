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
from poco.drivers.android.uiautomation import AndroidUiautomationPoco
from util.CommonUtil import CommonUtil
from WoolProject import AbsWoolProject

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
