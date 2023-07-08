# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from airtest.core.api import *
from wool_tasks.base_airtest_bd_jsb import BDJsbBaseAir

auto_setup(__file__)


class DragonRead(BDJsbBaseAir):
    PKG_NAME = 'com.dragon.read'

    def __init__(self, deviceId: str, forceRestart: bool = True, totalSec: int = 180, minInfoStreamSec: int = 180):
        super().__init__(deviceId=deviceId, pkgName=DragonRead.PKG_NAME,
                         splashActPath='com.dragon.read.pages.splash.SplashActivity',
                         homeActPath='com.dragon.read.pages.main.MainFragmentActivity',
                         appName='番茄免费小说',
                         minInfoStreamSec=minInfoStreamSec,
                         totalSec=totalSec,
                         forceRestart=forceRestart)
        using(os.path.dirname(__file__))

    def startApp(self, homeActPath: str = None,
                 forceRestart: bool = False, msg: str = None):
        super().startApp(forceRestart=forceRestart)

    def get_earn_monkey_tab_name(self) -> tuple:
        return '福利', r'(金币收益|开宝箱得金币|日常任务)'

    def get_info_stream_tab_name(self) -> tuple:
        return '书城', r'(排行榜|书荒广场|热门书签|^推荐|猜你喜欢)'

    def check_info_stream_valid(self, forceRecheck: bool = False) -> tuple:
        if self.canDoOthersWhenInStream():
            self.watch_ad_video(minDurationSec=5 * 60)
            forceRecheck = True
        return super().check_info_stream_valid(forceRecheck=forceRecheck)

    def run(self, **kwargs):
        super().run(**kwargs)

    def onRun(self, **kwargs):
        # super().onRun(**kwargs)
        if self.goto_home_information_tab():
            self.runAction(self.read_novel_detail, eachNovelSec=self.totalSec, jumpPrefixText=r'(^猜你喜欢|^推荐好书)')

    def kan_xiaoshuo(self, jump2NovelHomeBtnText: str = r'(^看小说$|^看更多$)',
                     prefixText: str = r'[看|读]小说.*?赚金.',
                     jump2NovelDetailBtnText: str = r'(?:每读\(0/\d+\)|\d\.\d分)',
                     keywordInNovelDetail: str = r'(书籍介绍|第.{1,7}章|弟.{1,7}草|第.{1,7}草|弟.{1,7}章|继续阅读下一页|下一章|左滑开始阅读)',
                     eachNovelSec: float = 16 * 60, novelCount: int = 1):
        super().kan_xiaoshuo()
