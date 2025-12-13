#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import asyncio
import threading
import time
from typing import Callable, Union, List, Set


class DelayedTaskManager:
    def __init__(self):
        # 存储待执行的任务，键为任务ID，值为Timer对象
        self.tasks = {}  # 同步任务
        self.asyncTasks = {}  # 异步任务
        self.task_counter = 0  # 任务ID计数器

        # 依赖关系管理
        self.dependencies = {}  # {task_id: set of dependency task ids} 存储每个任务的依赖项
        self.dependents = {}  # {task_id: set of dependent task ids}    存储每个任务被哪些任务依赖
        self.completed_tasks = set()  # 已完成的任务
        self.pending_tasks = {}  # 等待依赖满足的任务 {task_id: task_info}

    def addTask(self, delay_seconds: int, func: Callable, *args, **kwargs) -> int:
        """
        添加一个延迟执行的任务
        基于线程,会在单独的线程中运行, 适用于CPU密集型或者真正并行执行的任务,可以执行普通函数
        :param delay_seconds: 延迟秒数
        :param func: 要执行的函数
        :param args: 函数参数
        :param kwargs: 函数关键字参数
        :return: 任务ID，用于后续取消任务
        """
        return self.addDependentTask(delay_seconds, [], func, *args, **kwargs)

    def addDependentTask(self, delay_seconds: int, depends_on: List[int],
                         func: Callable, *args, **kwargs) -> int:
        """
        添加一个带依赖关系的延迟执行任务
        :param delay_seconds: 延迟秒数
        :param depends_on: 依赖的任务ID列表
        :param func: 要执行的函数
        :param args: 函数参数
        :param kwargs: 函数关键字参数
        :return: 任务ID
        """
        # 分配任务ID
        task_id = self.task_counter
        self.task_counter += 1

        # 存储依赖关系
        self.dependencies[task_id] = set(depends_on)

        # 更新反向依赖关系
        for dep_id in depends_on:
            if dep_id not in self.dependents:
                self.dependents[dep_id] = set()
            self.dependents[dep_id].add(task_id)

        # 创建包装函数
        def wrapper():
            try:
                func(*args, **kwargs)
            finally:
                self._mark_task_completed(task_id)
                if task_id in self.tasks:
                    del self.tasks[task_id]

        # 检查是否可以立即执行
        if self._can_execute(task_id):
            # 创建并启动Timer
            timer = threading.Timer(delay_seconds, wrapper)
            timer.daemon = True  # 设置为守护线程，主线程结束时自动终止
            self.tasks[task_id] = timer
            timer.start()
        else:
            # 暂时缓存任务信息
            self.pending_tasks[task_id] = {
                'type': 'sync',
                'delay': delay_seconds,
                'wrapper': wrapper
            }

        return task_id

    def _can_execute(self, task_id: int) -> bool:
        """检查任务是否可以执行（所有依赖都已完成）"""
        dependencies = self.dependencies.get(task_id, set())
        return dependencies.issubset(self.completed_tasks)

    def _mark_task_completed(self, task_id: int):
        """标记任务完成，并尝试触发依赖任务"""
        self.completed_tasks.add(task_id)

        # 检查是否有等待此任务完成的依赖任务
        dependents = self.dependents.get(task_id, set())
        for dependent_id in dependents.copy():
            if self._can_execute(dependent_id):
                self._execute_pending_task(dependent_id)

    def _execute_pending_task(self, task_id: int):
        """执行等待中的任务"""
        if task_id in self.pending_tasks:
            task_info = self.pending_tasks.pop(task_id)

            if task_info['type'] == 'sync':
                timer = threading.Timer(task_info['delay'], task_info['wrapper'])
                timer.daemon = True
                self.tasks[task_id] = timer
                timer.start()
            elif task_info['type'] == 'async':
                # 正确处理异步任务
                task = asyncio.create_task(task_info['wrapper']())
                self.asyncTasks[task_id] = task

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

    async def addAsyncTask(self, delay_seconds: int, func: Callable, *args, **kwargs) -> int:
        """
        添加一个延迟执行的异步任务
        基于协程,在asyncio事件循环中运行, 适用于IO密集型,可以执行普通函数和协程函数
        :param delay_seconds: 延迟秒数
        :param func: 要执行的函数（可以是普通函数或协程函数）
        :param args: 函数参数
        :param kwargs: 函数关键字参数
        :return: 任务ID，用于后续取消任务
        """
        return await self.addAsyncDependentTask(delay_seconds, [], func, *args, **kwargs)

    async def addAsyncDependentTask(self, delay_seconds: int, depends_on: List[int],
                                    func: Callable, *args, **kwargs) -> int:
        """
        添加一个带依赖关系的异步延迟任务
        :param delay_seconds: 延迟秒数
        :param depends_on: 依赖的任务ID列表
        :param func: 要执行的函数
        :param args: 函数参数
        :param kwargs: 函数关键字参数
        :return: 任务ID
        """
        # 分配任务ID
        task_id = self.task_counter
        self.task_counter += 1

        # 存储依赖关系
        self.dependencies[task_id] = set(depends_on)

        # 更新反向依赖关系
        for dep_id in depends_on:
            if dep_id not in self.dependents:
                self.dependents[dep_id] = set()
            self.dependents[dep_id].add(task_id)

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
                self._mark_task_completed(task_id)
                if task_id in self.asyncTasks:
                    del self.asyncTasks[task_id]

        # 检查是否可以立即执行
        if self._can_execute(task_id):
            # 创建并启动任务
            task = asyncio.create_task(wrapper())
            self.asyncTasks[task_id] = task
        else:
            # 暂时缓存任务信息
            self.pending_tasks[task_id] = {
                'type': 'async',
                'delay': delay_seconds,
                'wrapper': wrapper,  # ✅ 存储协程函数本身，不执行
                'args': (args, kwargs)  # 可能还需要存储参数
            }

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

    # 测试依赖关系
    print(f"\n\n{time.strftime('%H:%M:%S')} 开始测试依赖关系:")

    def task_b():
        print(f"{time.strftime('%H:%M:%S')} Task B 执行完成")

    def task_c():
        print(f"{time.strftime('%H:%M:%S')} Task C 执行完成")

    def task_a():
        print(f"{time.strftime('%H:%M:%S')} Task A 执行完成 (依赖B和C)")

    # 创建有依赖关系的任务
    task_b_id = manager.addTask(2, task_b)  # 2秒后执行
    task_c_id = await manager.addAsyncTask(3, task_c)  # 3秒后执行
    task_a_id = await manager.addAsyncDependentTask(1, [task_b_id, task_c_id], task_a)  # 依赖B和C完成后执行

    print(f"{time.strftime('%H:%M:%S')} 已安排依赖任务: A依赖于B和C")

    # 等待所有任务完成
    await asyncio.sleep(4)
    time.sleep(4)
    print(f"{time.strftime('%H:%M:%S')} 依赖关系示例结束")

    # 等待第一个任务执行完成
    await asyncio.sleep(3)
    print(f"{time.strftime('%H:%M:%S')} 异步示例结束")

    # 等待第一个任务执行完成
    time.sleep(3)
    print(f"{time.strftime('%H:%M:%S')} 示例结束")


if __name__ == "__main__":
    asyncio.run(_example())
