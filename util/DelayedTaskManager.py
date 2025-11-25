# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import asyncio
import threading
import time
from typing import Callable, Union


class DelayedTaskManager:
    def __init__(self):
        # 存储待执行的任务，键为任务ID，值为Timer对象
        self.tasks = {}  # 同步任务
        self.asyncTasks = {}  # 异步任务
        self.task_counter = 0  # 任务ID计数器

    def addTask(self, delay_seconds: int, func: Callable, *args, **kwargs):
        """
        添加一个延迟执行的任务
        基于线程,会在单独的线程中运行, 适用于CPU密集型或者真正并行执行的任务,可以执行普通函数
        :param delay_seconds: 延迟秒数
        :param func: 要执行的函数
        :param args: 函数参数
        :param kwargs: 函数关键字参数
        :return: 任务ID，用于后续取消任务
        """

        # 创建包装函数，执行完后从任务列表中移除
        def wrapper():
            try:
                func(*args, **kwargs)
            finally:
                if task_id in self.tasks:
                    del self.tasks[task_id]

        # 创建并启动Timer
        timer = threading.Timer(delay_seconds, wrapper)
        timer.daemon = True  # 设置为守护线程，主线程结束时自动终止

        # 分配任务ID并存储
        task_id = self.task_counter
        self.task_counter += 1
        self.tasks[task_id] = timer

        # 启动计时器
        timer.start()
        return task_id

    def _cancelTask(self, task_id: Union[int, None]) -> bool:
        """
        取消指定的延迟任务,任务开始前取消有效
        :param task_id: 任务ID, None表示取消全部任务
        :return: 是否成功取消
        """
        if task_id is None:
            task_ids = list(self.tasks.keys())
            for task_id in task_ids:
                self._cancelTask(task_id)
            return True
        elif task_id in self.tasks:
            timer = self.tasks[task_id]
            timer.cancel()
            del self.tasks[task_id]
            print(f"同步任务 {task_id} 已取消")
            return True
        return False

    async def addAsyncTask(self, delay_seconds: int, func: Callable, *args, **kwargs):
        """
        添加一个延迟执行的异步任务
        基于协程,在asyncio事件循环中运行, 适用于IO密集型,可以执行普通函数和协程函数
        :param delay_seconds: 延迟秒数
        :param func: 要执行的函数（可以是普通函数或协程函数）
        :param args: 函数参数
        :param kwargs: 函数关键字参数
        :return: 任务ID，用于后续取消任务
        """

        # 创建包装协程
        async def wrapper():
            try:
                # 等待指定时间
                await asyncio.sleep(delay_seconds)
                # 执行函数（自动处理普通函数和协程函数）
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
            except asyncio.CancelledError:
                print(f"任务 {task_id} 被取消")
                raise
            finally:
                if task_id in self.asyncTasks:
                    del self.asyncTasks[task_id]

        # 创建并启动任务
        task = asyncio.create_task(wrapper())

        # 分配任务ID并存储
        task_id = self.task_counter
        self.task_counter += 1
        self.asyncTasks[task_id] = task

        return task_id

    def _cancelAsyncTask(self, task_id: Union[int, None]) -> bool:
        """
        取消指定的异步延迟任务
        可以在任务执行过程中响应取消
        :param task_id: 任务ID, None表示取消全部异步任务
        :return: 是否成功取消
        """
        if task_id is None:
            task_ids = list(self.asyncTasks.keys())
            for task_id in task_ids:
                self._cancelAsyncTask(task_id)
            return True
        elif task_id in self.asyncTasks:
            task = self.asyncTasks[task_id]
            task.cancel()
            del self.asyncTasks[task_id]
            print(f"异步任务 {task_id} 已取消")
            return True
        return False

    def cancelTask(self, taskId: Union[int, None]) -> bool:
        """
        取消任务(包含同步和异步)
        :param taskId: 任务ID, None表示取消全部任务
        """
        return self._cancelTask(taskId) or self._cancelAsyncTask(taskId)


# 使用示例
async def _example():
    manager = DelayedTaskManager()

    def hello(name):
        print(f"{time.strftime('%H:%M:%S')} 同步Hello, {name}!")

    # 安排两个延迟任务
    task1 = manager.addTask(5, hello, "World")
    task2 = manager.addTask(10, hello, "Python")

    print(f"{time.strftime('%H:%M:%S')} 同步任务已安排，将在5秒和10秒后执行")

    # 等待3秒后取消第二个任务
    time.sleep(3)
    if manager.cancelTask(task2):
        print(f"{time.strftime('%H:%M:%S')} 已取消10秒后的同步任务 {task2}")

    def hello_sync(name):
        print(f"{time.strftime('%H:%M:%S')} [同步] Hello, {name}!")

    async def hello_async(name):
        print(f"{time.strftime('%H:%M:%S')} [异步] Hello, {name}!")

    # 安排两个延迟任务（一个同步函数，一个异步函数）
    task3 = await manager.addAsyncTask(5, hello_sync, "World")
    task4 = await manager.addAsyncTask(10, hello_async, "Python")

    print(f"\n\n{time.strftime('%H:%M:%S')} 异步任务已安排，将在5秒和10秒后执行")

    # 等待3秒后取消第二个任务
    await asyncio.sleep(3)
    if manager.cancelTask(task4):
        print(f"{time.strftime('%H:%M:%S')} 已取消10秒后的异步任务 {task4}")

    # 等待第一个任务执行完成
    await asyncio.sleep(3)
    print(f"{time.strftime('%H:%M:%S')} 异步示例结束")

    # 等待第一个任务执行完成
    time.sleep(3)
    print(f"{time.strftime('%H:%M:%S')} 示例结束")


if __name__ == "__main__":
    asyncio.run(_example())
