# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import json
import os
import threading
from typing import Optional, TypeVar, Generic, Callable

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

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

    def __init__(self, cache_file: str, backup_dir: Optional[str] = None, save_batch: int = 100, recook_key: Optional[Callable] = None):
        """
        初始化查询缓存

        :param cache_file: 缓存文件路径
        :param backup_dir: 备份目录, 当缓存文件存在时, 会将缓存文件备份到该目录, 非None时会自动备份
        :param save_batch: 新增多少条缓存数据时, 要自动保存到文件中
        :param recook_key: 重新计算key的方法, 传入原始key, 返回新的key
        """
        self.cache_file = cache_file
        if backup_dir:
            FileUtil.backup_file(cache_file, backup_dir)
        self.cache = self._load_cache()
        self.lock = threading.Lock()
        self.save_batch: int = save_batch
        self.recook_key = recook_key

    def _load_cache(self) -> dict:
        """加载缓存文件"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                    if self.recook_key:
                        result = {self.recook_key(k): v for k, v in result.items()}
                    return result
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
            if self.recook_key:
                key = self.recook_key(key)
            return self.cache.get(key)

    def set(self, key: str, value: T):
        """将key-value对存入缓存"""
        # 使用线程锁保护共享资源
        with self.lock:
            if self.recook_key:
                key = self.recook_key(key)
            self.cache[key] = value
            # 每save_batch次请求保存一次缓存，避免频繁写文件
            if len(self.cache) % self.save_batch == 0:
                self._save_cache()

    def save(self):
        """保存缓存到文件"""
        # 使用线程锁保护共享资源
        with self.lock:
            self._save_cache()
