# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import re
import sys
import ctypes
from ctypes import wintypes
from airtest.core.api import *

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

__author__ = "Lynxz"

from util.CommonUtil import CommonUtil
from base_airtest import BaseAir
from util.TimeUtil import log_time_consume

auto_setup(__file__)


class BaseAir4Windows(BaseAir):

    def run(self, **kwargs):
        pass

    def __init__(self, handle_id: str = None, window_title: str = None, cacheDir: str = ''):
        """
        :param handle_id: 要定位的窗口句柄, 若为空,则会根据 window_title 进行查找
        :param window_title: 要查找的窗口标题, 用于确定句柄, 请确保唯一
        """
        self.appName = window_title
        if CommonUtil.isNoneOrBlank(handle_id):
            hid, title = BaseAir4Windows.get_handle_id_by_title(window_title)
            self.appName = title
            handle_id = str(hid)
        super().__init__('windows', uuid=handle_id, app_name=self.appName, cacheDir=cacheDir)

    @staticmethod
    @log_time_consume()
    def get_handle_id_by_title(window_title: str) -> tuple:
        """
        根据windows窗口标题（支持正则表达式）查找窗口句柄

        :param window_title: 窗口标题的正则表达式模式
        :return tuple {窗口句柄,窗口名称}   若未找到,则返回 {0,""}
        """
        # 编译正则表达式模式（忽略大小写）
        title_pattern = re.compile(window_title, re.IGNORECASE)

        # 定义Windows API函数
        user32 = ctypes.WinDLL('user32')
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        # 存储找到的窗口句柄
        found_windows = []

        # 窗口枚举回调函数
        def enum_windows_callback(hwnd, lParam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if buff.value:
                        # 将句柄转换为整数存储
                        handle_value = ctypes.cast(hwnd, ctypes.c_void_p).value
                        found_windows.append((handle_value, buff.value))
            return True

        # 枚举所有可见窗口
        user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)

        # # 打印所有找到的窗口（调试用）
        # print("\n所有可见窗口:")
        # for handle, title in found_windows:
        #     print(f"窗口标题:{title}, 句柄:{handle}")

        # 使用正则表达式查找匹配的窗口
        matching_windows = []
        for handle, title in found_windows:
            if title_pattern.search(title):
                matching_windows.append((handle, title))

        # 打印匹配结果
        if matching_windows:
            CommonUtil.printLog("匹配到的窗口:")
            for handle, title in matching_windows:
                print(f"正则匹配: '{window_title}' -> 窗口标题: {title}, 句柄: {handle}")

            # 返回第一个匹配窗口的句柄
            return matching_windows[0]
        else:
            CommonUtil.printLog(f"未找到匹配正则表达式 '{window_title}' 的窗口")
            return 0, ""

    def key_press(self, key: str, cnt: int = 1, interval: float = 0.1):
        """
        模拟一个按下按键的事件
        文档: https://airtest.readthedocs.io/zh-cn/latest/all_module/airtest.core.win.win.html#airtest.core.win.win.Windows.key_press
         若需要组合按键, 请使用 keyevent() 接口,比如:alt+f4  -> keyevent("%{F4}")   delte -> keyevent("{DEL}")
        :param key: 要模拟的按键, 如: 'F2'
        :param cnt: 按键次数, 默认1次
        :param interval: 按键后等待的时间, 单位:秒
        """
        for i in range(cnt):
            self.airtest_device.key_press(key)
            self.sleep(interval)


if __name__ == '__main__':
    air = BaseAir4Windows(window_title='网上股票交易系统', cacheDir='D:/log/')
    air.saveImage(air.snapshot())
    pos, ocrResStr, ocrResList = air.findTextByOCR('资金股票', prefixText='查询', subfixText='当日成交')
    print(f'资金股票矩形框坐标: {pos}')
    print(f'资金股票中心点坐标: {air.calcCenterPos(pos)}')
    print(f'\n\nocrResStr: {ocrResStr}')
    # print(f'\n\nocrResList: {ocrResList}')
    air.touch(air.calcCenterPos(pos))  # 点击资金股票文本框
