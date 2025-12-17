# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import threading
import time
from typing import Deque
from collections import deque


class QPSLimiter:
    """QPS限制器，用于控制请求频率"""

    def __init__(self, qps_limit: int = 50):
        """
        初始化QPS限制器

        :param qps_limit: 每秒最大请求数，默认50
        """
        self.qps_limit = qps_limit
        self.request_times: Deque[float] = deque()
        self.lock = threading.Lock()
        self.api_request_count = 0
        self.start_time = time.time()
        self.last_request_time = 0.0

    def wait_if_needed(self):
        """根据需要等待，以确保不超过QPS限制"""
        with self.lock:
            current_time = time.time()

            # 清理超过1秒的请求记录
            while self.request_times and current_time - self.request_times[0] > 1.0:
                self.request_times.popleft()

            # 如果当前请求数已经达到限制
            if len(self.request_times) >= self.qps_limit:
                # 计算需要等待的时间，确保精确到毫秒级
                oldest_request = self.request_times[0]
                wait_time = 1.0 - (current_time - oldest_request)

                if wait_time > 0:
                    # 使用更精确的sleep时间
                    time.sleep(wait_time)
                    current_time = time.time()

                    # 重新清理过期请求
                    while self.request_times and current_time - self.request_times[0] > 1.0:
                        self.request_times.popleft()

            # 记录当前请求时间
            self.request_times.append(current_time)
            self.last_request_time = current_time
            self.api_request_count += 1

    def get_api_request_count(self):
        """获取API请求数量"""
        with self.lock:
            return self.api_request_count

    def get_average_qps(self):
        """获取平均QPS"""
        with self.lock:
            elapsed = time.time() - self.start_time
            return self.api_request_count / elapsed if elapsed > 0 else 0

    def get_elapsed_time(self):
        """获取经过的时间"""
        with self.lock:
            return time.time() - self.start_time
