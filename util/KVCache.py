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
                 expire_seconds: int = 30 * 24 * 3600,
                 check_interval: int = 3600):
        """
        初始化查询缓存

        :param cache_file: 缓存文件路径
        :param save_batch: 新增多少条缓存数据时, 要自动保存到文件中, 非None时有效
        :param recook_key: 对已缓存和新增的key进行处理, 保存处理后的数据
        :param second_cache_files: 第二份缓存文件路径, 若存在, 会将 cache_file 中不存在的key数据添加到 self.cache 的整体缓存dict中
        :param enable: 是否启用缓存, 若为False, 则 get/set/save 等操作均无效
        :param expire_seconds: 缓存有效期(秒),默认30天,超过有效期则删除重建缓存文件
        :param check_interval: 定期检查缓存过期的时间间隔(秒),默认1小时
        """
        self.cache_file = cache_file
        self.enable: bool = enable
        self.recook_key = recook_key
        self.lock = threading.Lock()
        self.save_batch: Optional[int] = save_batch
        self.expire_seconds: int = expire_seconds
        self.check_interval: int = check_interval
        self._new_key_cnt: int = 0  # 新增key的计数
        self._last_check_time: float = time.time()  # 上次检查过期时间
        self._stop_check_thread: bool = False  # 停止定期检查线程的标志
        self._check_thread: Optional[threading.Thread] = None  # 定期检查线程

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
        
        # 启动定期检查缓存过期的后台线程
        if self.enable and self.expire_seconds > 0:
            self._start_expire_check_thread()

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

    def _check_and_handle_expire(self):
        """
        检查并处理缓存过期
        如果缓存过期，删除文件并清空内存缓存
        """
        if not self.enable or self.expire_seconds <= 0:
            return
        
        with self.lock:
            if self._is_cache_expired():
                CommonUtil.printLog(f'⚠️ 缓存已过期，删除重建: {self.cache_file}')
                FileUtil.deleteFile(self.cache_file)
                self.cache.clear()  # 清空内存缓存
                self._new_key_cnt = 0
                CommonUtil.printLog(f'✅ 缓存已重置')

    def _expire_check_loop(self):
        """
        定期检查缓存过期的后台线程循环
        """
        while not self._stop_check_thread:
            try:
                # 等待检查间隔或直到被停止
                for _ in range(int(self.check_interval * 10)):
                    if self._stop_check_thread:
                        break
                    time.sleep(0.1)
                
                if not self._stop_check_thread:
                    self._check_and_handle_expire()
                    self._last_check_time = time.time()
            except Exception as e:
                CommonUtil.printLog(f"定期检查缓存过期异常: {e}")

    def _start_expire_check_thread(self):
        """
        启动定期检查缓存过期的后台线程
        """
        self._stop_check_thread = False
        self._check_thread = threading.Thread(
            target=self._expire_check_loop,
            daemon=True,  # 守护线程，主程序退出时自动结束
            name=f"KVCache-ExpireCheck-{os.path.basename(self.cache_file)}"
        )
        self._check_thread.start()
        CommonUtil.printLog(f'已启动缓存过期定期检查线程，间隔: {self.check_interval}秒')

    def stop_expire_check(self):
        """
        停止定期检查缓存过期的后台线程
        通常在程序退出前调用
        """
        if self._check_thread and self._check_thread.is_alive():
            self._stop_check_thread = True
            self._check_thread.join(timeout=2)
            CommonUtil.printLog(f'已停止缓存过期定期检查线程')

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

    def clear(self) -> Self:
        """
        清空缓存（包括内存和文件）
        :return: self
        """
        if not self.enable:
            return self
        with self.lock:
            self.cache.clear()
            self._new_key_cnt = 0
            FileUtil.deleteFile(self.cache_file)
            CommonUtil.printLog(f'已清空缓存: {self.cache_file}')
        return self

    def __del__(self):
        """析构函数，停止定期检查线程"""
        try:
            self.stop_expire_check()
        except Exception:
            pass
