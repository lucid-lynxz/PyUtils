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
from airtest.core.helper import using

from util.CommonUtil import CommonUtil
from wool_tasks.base_airtest_bd_jsb import BDJsbBaseAir

auto_setup(__file__)


class TbAir(BDJsbBaseAir):

    def __init__(selfd, deviceId: str, forceRestart: bool = False):
        super().__init__(deviceId=deviceId, pkgName='com.taobao.taobao',
                         homeActPath='com.taobao.tao.TBMainActivity',
                         appName='淘宝',
                         forceRestart=forceRestart)

        using(os.path.dirname(__file__))

    def onRun(self, **kwargs):
        super().onRun(**kwargs)

    def taojinbi(self):
        """
        首页 ->'领淘金币'
        """
        pass

    def closeDialog(self, extraImg: str = None, autoClick: bool = True,
                    minX: int = 200, minY: int = 200, maxX: int = 0, maxY: int = 0) -> tuple:
        return super().closeDialog(extraImg='tpl1684931855744.png')

    def qiandao(self):
        """首页左上角 -> '签到' """
        pos, _, ocrResList = self.findTextByOCR(targetText=r'^签到$', maxSwipeRetryCount=1, height=200)
        if not self.tapByTuple(self.calcCenterPos(pos)):
            return

        pos, _, ocrResList = self.findTextByOCR(targetText=r'^立即签到$', prefixText='天天签到领现.',
                                                maxSwipeRetryCount=1, height=200)
        self.tapByTuple(self.calcCenterPos(pos))
        for _ in range(5):
            pos, _, ocrResList = self.findTextByOCR(targetText=r'^立即签到$', prefixText='天天签到领现.',
                                                    maxSwipeRetryCount=1, height=200)
            self.tapByTuple(self.calcCenterPos(pos))

    def yaoxianjin(self):
        """首页->'摇现金'"""
        pos, _, ocrResList = self.findTextByOCR(targetText=r'摇现金', prefixText=r'(订阅|推荐)',
                                                maxSwipeRetryCount=1, height=200)
        # 跳转摇现金页面
        if not self.tapByTuple(self.calcCenterPos(pos)):
            return

        for _ in range(10):
            pos, _, ocrResList = self.findTextByOCR(targetText=r'^摇一摇\s+开福袋$', prefixText=r'(摇福袋|领现金)',
                                                    maxSwipeRetryCount=1)
            if not self.tapByTuple(self.calcCenterPos(pos)):
                continue

            # 等待摇一摇结束
            for _ in range(3):
                pos, _, ocrResList = self.findTextByOCR(
                    targetText=r'(^正在等待好友一起摇|人越多钱越多$|幸运|恭喜.*一起摇成功)',
                    maxSwipeRetryCount=1)
                if not CommonUtil.isNoneOrBlank(pos):
                    self.sleep(3)

            # 开奖结果处理
            # 可能收到祝福/开出福星/金币
            # 1. 若是收到祝福/福星 -> 点击 '开心收下'
            pos, _, ocrResList = self.findTextByOCR(targetText=r'^开心收下$', prefixText=r'有缘.*送你.*$',
                                                    maxSwipeRetryCount=1)
            if not self.tapByTuple(self.calcCenterPos(pos)):  # 收祝福
                # 若是开出福星,则关闭弹框
                pos, _, _ = self.findTextByCnOCRResult(cnocr_result=ocrResList, targetText=r'(开出福星$|^立即抽奖$)')
                if not CommonUtil.isNoneOrBlank(pos):
                    self.closeDialog()

            # 之后底部会弹框方向给淘内/淘外的好友, 点击 '取消'
            pos, _, ocrResList = self.findTextByOCR(targetText=r'^取消$', prefixText=r'(^找身边的朋友.*|发给淘.的好友)',
                                                    maxSwipeRetryCount=1)
            self.tapByTuple(self.calcCenterPos(pos))  # 取消分享
