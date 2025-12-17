# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import json
import os
import threading
from typing import Optional, TypeVar, Generic

from util.CommonUtil import CommonUtil

T = TypeVar('T')  # 泛型类型


class KVCache(Generic[T]):
    """
    查询缓存，用于存储指定的key-value对,支持断点重跑
    key是字符串, value是泛型T
    使用:
    cache:KVCache[dict] = KVCache("cache.json") # 指定泛型类型是dict
    cache.set("key", {'name':'lynxz','age': 18}) # 追加数据到缓存中
    value:Optional[dict] = cache.get("key") # 从缓存中获取数据
    cache.save() # 保存缓存到文件
    """

    def __init__(self, cache_file: str, save_batch: int = 100):
        """
        初始化查询缓存

        :param cache_file: 缓存文件路径
        :param save_batch: 新增多少条缓存数据时, 要自动保存到文件中
        """
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.lock = threading.Lock()
        self.save_batch: int = save_batch

    def _load_cache(self) -> dict:
        """加载缓存文件"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                CommonUtil.printLog(f"加载缓存文件失败: {e}")
                return {}
        return {}

    def _save_cache(self):
        """保存缓存到文件"""
        if CommonUtil.isNoneOrBlank(self.cache_file):
            return

        try:
            # 确保缓存目录存在
            cache_dir = os.path.dirname(self.cache_file)
            if cache_dir and not os.path.exists(cache_dir):
                os.makedirs(cache_dir)

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            CommonUtil.printLog(f"保存缓存文件失败: {e}")

    def get(self, key: str) -> Optional[T]:
        """从缓存中获取key对应的结果"""
        # 使用线程锁保护共享资源
        with self.lock:
            return self.cache.get(key)

    def set(self, key: str, value: T):
        """将key-value对存入缓存"""
        # 使用线程锁保护共享资源
        with self.lock:
            self.cache[key] = value
            # 每save_batch次请求保存一次缓存，避免频繁写文件
            if len(self.cache) % self.save_batch == 0:
                self._save_cache()

    def save(self):
        """保存缓存到文件"""
        # 使用线程锁保护共享资源
        with self.lock:
            self._save_cache()
