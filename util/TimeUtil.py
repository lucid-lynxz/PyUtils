# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import functools
import inspect
import random
import time
from datetime import datetime, timedelta


def log_time_consume(exclude_params=None, separate: bool = True):
    """
    记录函数执行时间和参数的装饰器

    参数:
        exclude_params: 需要排除的参数名列表（默认包含 'self' 和 'cls'）
        separate: 是否跳行打印参数, 默认true, 表示会打印第一个语句之前加一个空行, 并在最后一个语句之后加一个空行
    示例:
    @log_time_consume(exclude_params=['password'])
    def login(username, password):
        pass
    """
    # 设置默认排除参数
    default_exclude = ['self', 'cls']
    if exclude_params is None:
        exclude_params = default_exclude
    else:
        # 确保默认参数在列表中
        exclude_params = list(set(exclude_params + default_exclude))

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 获取函数签名以获取参数名
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # 准备打印的参数
            params_to_print = {}
            for name, value in bound_args.arguments.items():
                if name not in exclude_params:
                    params_to_print[name] = value

            # 打印参数
            blank_line = '\n' if separate else ''
            if params_to_print:
                print(f'{blank_line}执行 {func.__name__} 调用,参数: {params_to_print}')
            else:
                print(f'{blank_line}执行 {func.__name__} 调用,无参数')

            # 计时
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()

            # 打印耗时
            print(f'{func.__name__} 执行耗时: {end_time - start_time:.2f} 秒{blank_line}')
            return result

        return wrapper

    return decorator


class TimeUtil(object):
    @classmethod
    def getTimeStr(cls, f="%Y-%m-%d %H:%M:%S", n: int = 0):
        """
        获取N天前的时间,并按给定的格式返回字符串结果
        :param f: 日期格式,  %Y 代表四位数的年份，%m 代表两位数的月份，%d 代表两位数的日期
        :param n: 天数, 0表示当天, 正数表示N天前, 负数表示N天后
        """
        current_date = datetime.now()  # 获取当前日期
        n_days_ago = current_date - timedelta(days=n)  # 计算 N 天前的日期
        return n_days_ago.strftime(f)  # 将日期转换为指定格式的字符串
        # return time.strftime(format, time.localtime(time.time()))

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

    @staticmethod
    def convertSecsDuration(totalSecs: float) -> str:
        """
        将所给的秒数转换为易读的字符串, 格式: x小时y分z秒
        """
        totalSecs = int(totalSecs)
        hour = int(totalSecs // 3600)
        rest = totalSecs % 3600
        minutes = int(rest // 60)
        secs = int(rest % 60)
        result = '%s小时%s分%s秒' % (hour, minutes, secs)
        return result.replace('分0秒', '分').replace('时0分', '时').replace('0小时', '')

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
    def sleep(cls, sec: float, minSec: float = 1, maxSec: float = 10) -> float:
        """
        等待一会
        :param sec: 等待指定的秒数，大于0有效，若小于0，则会在 [minSec,maxSec) 中随机算一个
        :return 最终使用的时长,单位:s
        """
        if sec < 0:
            sec = round(minSec + random.random() * (maxSec - minSec), 1)  # 保留一位小数

        if sec < 0:
            sec = 1

        if sec > 0:
            time.sleep(sec)
        return sec

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


if __name__ == '__main__':
    print(TimeUtil.convertSecsDuration(8))
    print(TimeUtil.convertSecsDuration(59.5))
    print(TimeUtil.convertSecsDuration(61))
    print(TimeUtil.convertSecsDuration(3600 + 358))
    print(TimeUtil.convertSecsDuration(5260))
