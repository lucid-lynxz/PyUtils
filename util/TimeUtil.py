# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import time
from datetime import datetime


class TimeUtil(object):
    @classmethod
    def getTimeStr(cls, format="%Y-%m-%d %H:%M:%S"):
        """获取当前时间,并按给定的格式返回字符串结果"""
        return time.strftime(format, time.localtime(time.time()))

    @classmethod
    def convertFormat(cls, dateStr: str, oldFormat: str, newFormat: str = '%Y-%m-%d') -> str:
        """
        转换日期格式
        """
        # print('--> convertFormat(%s,%s,%s)' % (dateStr, oldFormat, newFormat))
        try:
            result = datetime.strptime(dateStr, oldFormat).strftime(newFormat)
        except Exception as e:
            result = dateStr
        return result

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

    @classmethod
    def dateDiff(cls, date1: str, date2: str, dateFormat: str = '%Y-%m-%d', valueOnError: int = 0) -> int:
        """
        比较两个日期相差的天数
        :param date1: 第一个日期字符串,如: 2022-06-27
        :param date2: 第二个日期字符串,如: 2022-06-28
        :param dateFormat: 日期格式, 默认为: '%Y-%m-%d'
        :param valueOnError: 运算出错时返回的值, 默认为0
        :return date1与date2相差的天数, 负数表示date1早于date2,  如: -1
        """
        try:
            time1 = time.mktime(time.strptime(date1, dateFormat))
            time2 = time.mktime(time.strptime(date2, dateFormat))
            diff = int(time1) - int(time2)  # 日期转化为int比较
            print(diff)
            return int(diff / 24 / 60 / 60)
        except Exception as e:
            print('dateDiff exception %s' % e)
            print(e)
            return valueOnError
