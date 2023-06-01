# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

# 快手极速版
from wool_tasks.WoolProject import AbsWoolProject
from wool_tasks.ksjsb.main import KsAir


class KsjsbTask(AbsWoolProject):
    PKG_NAME = 'com.kuaishou.nebula'

    def __init__(self, deviceId: str, forceRestart=False, totalSec: int = 180):
        self.air = KsAir(deviceId=deviceId, forceRestart=forceRestart)
        self.air.totalSec = totalSec
        super().__init__(pkgName=KsjsbTask.PKG_NAME,
                         homeActPath='com.yxcorp.gifshow.HomeActivity',
                         deviceId=deviceId, forceRestart=forceRestart, appName='快手极速版', totalSec=totalSec)

    def updateDeviceId(self, deviceId: str):
        super().updateDeviceId(deviceId)
        self.air.updateDeviceId(deviceId)
        return self

    def updateDim(self, dim: float, dimOri: float = -1):
        super().updateDim(dim, dimOri)
        self.air.updateDim(dim, dimOri)
        return self

    def onRun(self, **kwargs):
        # 看视频赚钱
        self.air.updateCacheDir(self.cacheDir).updateLogPath(logName=self.logName) \
            .updateDeviceId(self.deviceId).updateDim(self.dim, self.dimOri).setNotificationRobotDict(
            self.notificationRobotDict).run()


if __name__ == '__main__':
    KsjsbTask(deviceId='0A221FDD40006J').run()  # pixel 5
