# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import json
import os
import threading
import time
from typing import Optional, TypeVar, Generic, Callable, Set
from typing_extensions import Self

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

    def __init__(self, cache_file: str, save_batch: Optional[int] = None,
                 recook_key: Optional[Callable] = None,
                 second_cache_files: Optional[Set[str]] = None, enable: bool = True,
                 expire_seconds: int = 30 * 24 * 3600):
        """
        初始化查询缓存

        :param cache_file: 缓存文件路径
        :param save_batch: 新增多少条缓存数据时, 要自动保存到文件中, 非None时有效
        :param recook_key: 对已缓存和新增的key进行处理, 保存处理后的数据
        :param second_cache_files: 第二份缓存文件路径, 若存在, 会将 cache_file 中不存在的key数据添加到 self.cache 的整体缓存dict中
        :param enable: 是否启用缓存, 若为False, 则 get/set/save 等操作均无效
        :param expire_seconds: 缓存有效期(秒),默认30天,超过有效期则删除重建缓存文件
        """
        self.cache_file = cache_file
        self.enable: bool = enable
        self.recook_key = recook_key
        self.lock = threading.Lock()
        self.save_batch: Optional[int] = save_batch
        self.expire_seconds: int = expire_seconds
        self._new_key_cnt: int = 0  # 新增key的计数

        # 检查缓存是否过期
        if self._is_cache_expired():
            CommonUtil.printLog(f'缓存已过期,删除重建: {cache_file}')
            FileUtil.deleteFile(cache_file)

        self.cache = self._load_cache(self.cache_file)
        if not CommonUtil.isNoneOrBlank(second_cache_files):
            for item in second_cache_files:
                if FileUtil.isFileExist(item):
                    second_cache = self._load_cache(item)
                    second_cache.update(self.cache)
                    self.cache = second_cache
        CommonUtil.printLog(f'初始化缓存成功,共有: {len(self.cache.keys())}条数据')

    def _is_cache_expired(self) -> bool:
        """
        检查缓存文件是否过期
        :return: True表示已过期或文件不存在, False表示未过期
        """
        if not os.path.exists(self.cache_file):
            return False  # 文件不存在不算过期

        try:
            # 获取文件创建时间(Windows)或修改时间(Linux/Mac)
            if os.name == 'nt':  # Windows
                create_time = os.path.getctime(self.cache_file)
            else:  # Linux/Mac
                stat = os.stat(self.cache_file)
                create_time = stat.st_ctime

            # 计算是否过期
            elapsed_time = time.time() - create_time
            return elapsed_time > self.expire_seconds
        except Exception as e:
            CommonUtil.printLog(f"检查缓存有效期失败: {e}, 将重建缓存")
            return True

    def _load_cache(self, cache_file: str) -> dict:
        """加载缓存文件"""
        if os.path.exists(cache_file):
            try:
                with self.lock:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                        if self.recook_key:
                            # 创建新字典避免在遍历时修改字典大小
                            new_result = {}
                            for key, value in result.items():
                                new_result[self.recook_key(key)] = value
                            result = new_result
                        CommonUtil.printLog(f'加载缓存成功,共有: {len(result.keys())}条数据, 文件:{cache_file}')
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
            # CommonUtil.printLog(f'尝试保存缓存: {self.cache_file}')
            intent = None if len(self.cache.keys()) >= 50000 else 2
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=intent)
            # CommonUtil.printLog(f'保存缓存成功')
        except Exception as e:
            CommonUtil.printLog(f"保存缓存文件失败: {e}")

    def get(self, key: str) -> Optional[T]:
        """从缓存中获取key对应的结果"""
        if not self.enable:
            return None
        # 使用线程锁保护共享资源
        with self.lock:
            key = self.recook_key(key) if self.recook_key else key
            return self.cache.get(key)

    def set(self, key: str, value: T) -> Self:
        """将key-value对存入缓存"""
        if not self.enable:
            return None
        # 使用线程锁保护共享资源
        with self.lock:
            key = self.recook_key(key) if self.recook_key else key
            if key not in self.cache:
                self._new_key_cnt += 1
            self.cache[key] = value

            # 每save_batch次请求保存一次缓存，避免频繁写文件
            if self.save_batch is not None and self._new_key_cnt > 0 and self._new_key_cnt % self.save_batch == 0:
                self._save_cache()
                self._new_key_cnt = 0
        return self

    def save(self) -> Self:
        """保存缓存到文件"""
        if not self.enable:
            return self
        # 使用线程锁保护共享资源
        with self.lock:
            self._save_cache()
        return self
