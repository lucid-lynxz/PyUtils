# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import time


class TimeUtil(object):
    @classmethod
    def getTimeStr(cls, format="%Y-%m-%d %H:%M:%S"):
        """获取当前时间,并按给定的格式返回字符串结果"""
        return time.strftime(format, time.localtime(time.time()))

    @classmethod
    def currentTimeMillis(cls) -> int:
        """获取当前时间戳,单位:ms"""
        return int(round(time.time() * 1000))

    @classmethod
    def getDurationStr(cls, durationInMills: int) -> str:
        """将毫秒耗时转换更可读的 x时x分x秒的形式"""
        mills = durationInMills % 1000
        restSeconds = durationInMills // 1000
        seconds = restSeconds % 60
        restMinutes = restSeconds // 60
        minutes = restMinutes % 60
        hours = restSeconds // 3600
        return "%s时%s分%s秒" % (hours, minutes, seconds)

    @classmethod
    def sleep(cls, sec: int):
        time.sleep(sec)
