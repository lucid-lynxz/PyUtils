# -*- coding: utf-8 -*-

import concurrent
import functools
import inspect
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from util.log_handler import DefaultCustomLog

logger = DefaultCustomLog.get_log(os.path.basename(__file__))


def log_wrap(loggerObj=logger, exclude_arg=('self',), print_caller: bool = False,
             out_attr: str = None, print_out_obj: bool = True):
    """
    装饰器函数，用来记录方法的输入和输出
    :param loggerObj: 日志输出所使用的 logger
    :param exclude_arg: 排除参数，默认为 None
    :param print_caller: 是否打印当前函数的调用方信息(函数名+行号),默认False
    :param out_attr: 输出结果对象的属性，如果为 None 则直接输出对象，如 'json'
    :param print_out_obj: out_attr为None时,增加判断是否打印整个结果对象,默认为True
    """

    if not exclude_arg:
        exclude_arg = set()
    elif not isinstance(exclude_arg, set):
        exclude_arg = set(exclude_arg)

    def decorator(func):
        """
        实际的装饰器函数，用来装饰指定的方法。
        :param func: 被装饰的方法。
        """

        def log_msg(msg):
            if loggerObj is None:
                print(msg)
            else:
                loggerObj.warn(msg)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """
            包装函数，用来实现日志输出和原始函数的调用
            :param args: 函数的位置参数
            :param kwargs: 函数的关键字参数
            """
            get_func_args = (
                inspect.signature(func).bind(*args, **kwargs).arguments.items()
            )
            params = {
                name: value for name, value in get_func_args if name not in exclude_arg
            }
            start_ts = time.time()

            caller_info = ''
            if print_caller:
                try:
                    frame = sys._getframe()
                    file_name = frame.f_code.co_filename  # 调用方法所在文件路径
                    func_name = frame.f_back.f_code.co_name  # 调用方方法名
                    line_no = frame.f_back.f_lineno  # 行号
                    caller_info = f'call by:{func_name}:{line_no} '
                finally:
                    pass

            msg = f"{func.__module__}#{func.__qualname__} args: {params} {caller_info}"
            log_msg(msg)

            result = func(*args, **kwargs)
            duration_sec = round(time.time() - start_ts, 2)
            msg = f"{func.__module__}#{func.__qualname__} 耗时:{duration_sec}秒,result={result if print_out_obj else ''}"
            if out_attr and hasattr(result, out_attr):
                attr = getattr(result, out_attr)
                attr = attr() if callable(attr) else attr
                log_msg(f"{msg} 调用 result.{out_attr} 结果:{attr}")
            else:
                log_msg(msg)
            return result

        return wrapper

    return decorator


def timeout(seconds):
    """
    超时控制装饰器：支持多线程并发执行

    :param seconds: 超时时间（秒）
    :return: 装饰器对象
    """

    def wrapper(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            pool_executor = ThreadPoolExecutor()
            func_with_timeout = pool_executor.submit(func, *args, **kwargs)
            try:
                return func_with_timeout.result(timeout=seconds)
            except concurrent.futures._base.TimeoutError:
                raise Exception(f"{func.__name__} run too long, timeout {seconds}s.")

        return inner

    return wrapper
