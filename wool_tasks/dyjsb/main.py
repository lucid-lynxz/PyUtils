# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from typing import Union
from airtest.core.api import *
from wool_tasks.base_airtest_bd_jsb import BDJsbBaseAir

auto_setup(__file__)


class DyAir(BDJsbBaseAir):
    PKG_NAME = 'com.ss.android.ugc.aweme.lite'

    def __init__(self, deviceId: str, forceRestart: bool = True, totalSec: int = 180, minInfoStreamSec: int = 180):
        super().__init__(deviceId=deviceId, pkgName=DyAir.PKG_NAME,
                         splashActPath='com.ss.android.ugc.aweme.splash.SplashActivity',
                         homeActPath='com.ss.android.ugc.aweme.splash.SplashActivity',
                         appName='抖音极速版',
                         minInfoStreamSec=minInfoStreamSec,
                         totalSec=totalSec,
                         forceRestart=forceRestart)
        using(os.path.dirname(__file__))

    def get_info_stream_tab_name(self) -> tuple:
        """
        获取 首页 页面的跳转按钮名称和目标页面的关键字(用于确认有跳转成功)
        """
        return '首页', r'(^频道$|^关注$|同城|^热榜TOP|^搜索：|^热搜：|^直播卖货|^抢首评|^社会榜TOP.*|作品原声|来一发弹幕)'

    def perform_earn_tab_actions(self, tag: Union[str, list] = None,
                                 maxSwipeCount: int = 8,
                                 back2HomeStramTab: bool = False, filterFuncNames: set = None):
        return super().perform_earn_tab_actions(['earn_page_action_dy', 'earn_page_action'], maxSwipeCount,
                                                back2HomeStramTab, filterFuncNames)


if __name__ == '__main__':
    air = DyAir(deviceId='7b65fc7a')
    air.run()
