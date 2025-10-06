# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import functools
import inspect
import random
import time
from datetime import datetime, timedelta


def log_time_consume(exclude_params=None, separate: bool = False, only_log_result: bool = True):
    """
    记录函数执行时间和参数的装饰器

    参数:
    :param exclude_params: 需要排除的参数名列表（默认包含 'self' 和 'cls'）
    :param separate: 是否跳行打印参数, 表示会打印第一个语句之前加一个空行, 并在最后一个语句之后加一个空行
    :param only_log_result: 是否只在调用完成后才打印耗时等信息, 默认True, 若为False,则会在调用前打印参数
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
            if not only_log_result:
                if params_to_print:
                    print(f'{TimeUtil.getTimeStr()} {blank_line}执行 {func.__name__} 调用,参数: {params_to_print}')
                else:
                    print(f'{TimeUtil.getTimeStr()} {blank_line}执行 {func.__name__} 调用,无参数')

            # 计时
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()

            # 打印耗时
            time_tip = f'执行耗时: {end_time - start_time:.2f} 秒'
            if only_log_result:
                if params_to_print:
                    print(
                        f'{TimeUtil.getTimeStr()} {blank_line}执行 {func.__name__} 调用,{time_tip},参数: {params_to_print}')
                else:
                    print(f'{TimeUtil.getTimeStr()} {blank_line}执行 {func.__name__} 调用,{time_tip},无参数')
            else:
                print(f'{TimeUtil.getTimeStr()} {func.__name__} {time_tip}{blank_line}')

            return result

        return wrapper

    return decorator


class TimeUtil(object):
    @staticmethod
    def getTimeStr(fmt="%Y-%m-%d %H:%M:%S", n: int = 0) -> str:
        """
        获取N天前的时间,并按给定的格式返回字符串结果
        :param fmt: 日期格式,  %Y 代表四位数的年份，%m 代表两位数的月份，%d 代表两位数的日期
        :param n: 天数, 0表示当天, 正数表示N天前, 负数表示N天后
        """
        current_date = datetime.now()  # 获取当前日期
        n_days_ago = current_date - timedelta(days=n)  # 计算 N 天前的日期
        return n_days_ago.strftime(fmt)  # 将日期转换为指定格式的字符串
        # return time.strftime(format, time.localtime(time.time()))

    @staticmethod
    def getTimeObj(fmt="%Y-%m-%d %H:%M:%S", n: int = 0, target_date: str = None) -> datetime:
        """
        获取N天前的时间,并按给定的格式返回 datetime 对象
        :param fmt: 日期格式,  %Y 代表四位数的年份，%m 代表两位数的月份，%d 代表两位数的日期
        :param n: 天数, 0表示当天, 正数表示N天前, 负数表示N天后
        :param target_date: 目标日期, 默认为None, 表示使用当前日期 n 参数计算得到的日期
        """
        target_date = target_date if target_date else TimeUtil.getTimeStr(fmt, n)
        return datetime.strptime(target_date, fmt)

    @staticmethod
    def convertFormat(dateStr: str, oldFormat: str, newFormat: str = '%Y-%m-%d') -> str:
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

    @staticmethod
    def currentTimeMillis() -> int:
        """获取当前时间戳,单位:ms"""
        return int(round(time.time() * 1000))

    @staticmethod
    def getDurationStr(durationInMills: int) -> str:
        """将毫秒耗时转换更可读的 x时x分x秒的形式"""
        mills = durationInMills % 1000
        restSeconds = durationInMills // 1000
        seconds = restSeconds % 60
        restMinutes = restSeconds // 60
        minutes = restMinutes % 60
        hours = restSeconds // 3600
        return "%s时%s分%s秒" % (hours, minutes, seconds)

    @staticmethod
    def sleep(sec: float, minSec: float = 1, maxSec: float = 10) -> float:
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

    @staticmethod
    def calc_sec_diff(time1: str, time2: str, fmt: str = '%Y-%m-%d', def_value: int = 0) -> float:
        """
        比较两个日期相差的天数
        :param time1: 第一个日期字符串,如: 2022-06-27 也支持时间或者日期+时间格式,具体根据 dateFormat 来决定
        :param time2: 第二个日期字符串,如: 2022-06-28
        :param fmt: 日期格式, 默认为: '%Y-%m-%d' 也可用是: '%Y-%m-%d %H:%M:%S' 等
        :param def_value: 运算出错时返回的值, 默认为0
        :return time1 与 time2 相差的秒数, 负数表示 time1 早于 time2 ,  如: -1
        """
        try:
            # 将字符串解析为datetime对象
            time1 = datetime.strptime(time1, fmt)
            time2 = datetime.strptime(time2, fmt)
            time_diff = time1 - time2  # 计算时间差
            # 获取相差的秒数
            diff = time_diff.total_seconds()
            return diff
        except Exception as e:
            print(f'calc_sec_diff exception {e}')
            return def_value

    @staticmethod
    def dateDiff(date1: str, date2: str, dateFormat: str = '%Y-%m-%d', valueOnError: int = 0) -> int:
        """
        比较两个日期相差的天数
        :param date1: 第一个日期字符串,如: 2022-06-27 也支持时间或者日期+时间格式,具体根据 dateFormat 来决定
        :param date2: 第二个日期字符串,如: 2022-06-28
        :param dateFormat: 日期格式, 默认为: '%Y-%m-%d' 也可用是: '%Y-%m-%d %H:%M:%S' 等
        :param valueOnError: 运算出错时返回的值, 默认为0
        :return date1与date2相差的天数, 负数表示date1早于date2,  如: -1
        """
        diff_sec = TimeUtil.calc_sec_diff(date1, date2, dateFormat, valueOnError)
        return int(diff_sec / 24 / 60 / 60)

    @staticmethod
    def is_time_greater_than(target_str: str, include_equal: bool = False) -> bool:
        """
        比较当前时间是否大于等于目标时间字符串
        :param target_str: 目标时间字符串, 支持格式: "YYYY-MM-DD", "HH:MM:SS", "YYYY-MM-DD HH:MM:SS"
        :param include_equal: 是否包含等于的情况, 默认为False, 即当前时间大于目标时间时才返回True
        """
        target_str = target_str.strip().replace("  ", " ")
        time_format = TimeUtil.get_time_format(target_str)
        try:
            if time_format is None:
                raise ValueError(f"无法解析时间格式: {target_str}")

            cur_time = TimeUtil.getTimeStr(time_format)
            diff_sec = TimeUtil.calc_sec_diff(cur_time, target_str, time_format)
            # print(f'  cur_time={cur_time}, target={target_str},diff_sec={diff_sec},time_format={time_format}')
            return diff_sec >= 0 if include_equal else diff_sec > 0
        except ValueError as e:
            print(f"时间解析错误: {e}")
            return False

    @staticmethod
    def get_time_format(target_str: str) -> str:
        """
        尝试解析为日期时间格式
        支持格式: "YYYY-MM-DD", "YYYYMMDD", "HH:MM:SS", "YYYY-MM-DD HH:MM:SS", "YYYYMMDD HH:MM:SS"
        """
        time_format = None
        if ' ' in target_str:
            if '-' in time_format:
                time_format = "%Y-%m-%d %H:%M:%S"
            else:
                time_format = "%Y%m%d %H:%M:%S"
        # 尝试解析为日期格式
        elif '-' in target_str:
            time_format = "%Y-%m-%d"
        # 尝试解析为时间格式
        elif ':' in target_str:
            time_format = "%H:%M:%S"
        return time_format


if __name__ == '__main__':
    # print(TimeUtil.convertSecsDuration(8))
    # print(TimeUtil.convertSecsDuration(59.5))
    # print(TimeUtil.convertSecsDuration(61))
    # print(TimeUtil.convertSecsDuration(3600 + 358))
    # print(TimeUtil.convertSecsDuration(5260))
    print(TimeUtil.is_time_greater_than("22:15:59"))
    print(TimeUtil.is_time_greater_than(" 2025-06-26     16:00:00  "))
    print(TimeUtil.is_time_greater_than("  2025-06-26   22:15:59  "))
    print(TimeUtil.is_time_greater_than("2025-06-26"))
    # print(TimeUtil.dateDiff('09:30:33', "09:30:00", '%H:%M:%S'))
    # print(TimeUtil.dateDiff('2025-06-14', "2025-06-18", '%Y-%m-%d'))
    # print(TimeUtil.getTimeStr('%Y-%m-%d', 1))  # 昨天
    # print(TimeUtil.getTimeStr('%Y-%m-%d', 0))  # 今天
    # print(TimeUtil.getTimeStr('%Y-%m-%d', -1))  # 明天
