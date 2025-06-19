import schedule
import time
import threading
from queue import Queue
from typing import Callable, Dict, Optional
from util.CommonUtil import CommonUtil


class SchedulerTaskManager:
    """
    任务调度器类，支持动态添加/删除定时任务
    使用方法:
        scheduler = SchedulerTaskManager()
        scheduler.start()  # 启动调度器
        # 添加任务
        TaskScheduler()
            .add_task(
                task_id="task1",
                task_func=my_task_function,
                interval=10,
                unit="seconds",
                run_immediately=True
            )
            .start() # 启动调度器,会在子线程执行
            .wait_exit_event() # 等待用户输入q, 主线程不退出
    """

    def __init__(self):
        self._task_queue = Queue()  # 任务操作队列
        self._task_registry: Dict[str, schedule.Job] = {}  # 任务注册表
        self._stop_event = threading.Event()  # 停止标志
        self._scheduler_thread = None  # 调度器线程
        self._lock = threading.Lock()  # 线程锁

    def start(self):
        """启动调度器（在独立线程中运行）"""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            CommonUtil.printLog("调度器已在运行中")
            return

        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="TaskSchedulerThread"
        )
        self._scheduler_thread.start()
        CommonUtil.printLog("调度器已启动")
        return self

    def wait_exit_event(self):
        """
        等待用户按下q推出调度器
        """
        # 创建事件对象
        exit_event = threading.Event()
        CommonUtil.printLog("调度器已启动，输入'q'退出...")
        # 主线程等待用户输入
        while not exit_event.is_set():
            user_input = input()
            if user_input.lower() == 'q':
                exit_event.set()
        self.stop()
        return self

    def stop(self) -> None:
        """停止调度器"""
        self._stop_event.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=2.0)
        CommonUtil.printLog("调度器已停止")

    def add_task(
            self,
            task_id: str,
            task_func: Callable,
            interval: int = 60,
            unit: str = "seconds",
            at_time: str = None,
            run_immediately: bool = False
    ):
        """
        添加定时任务

        参数:
            task_id: 任务唯一标识
            task_func: 任务执行函数
            interval: 时间间隔
            unit: 时间单位 ('seconds', 'minutes', 'hours', 'days', 'weeks')
            at_time: 定时在指定时间执行, 格式为 'HH:MM:SS', 默认为空, 表示不指定时间
                    - For daily jobs -> `HH:MM:SS` or `HH:MM`
                    - For hourly jobs -> `MM:SS` or `:MM`
                    - For minute jobs -> `:SS`
            run_immediately: 是否立即执行一次
        """
        with self._lock:
            if task_id in self._task_registry:
                CommonUtil.printLog(f"任务 {task_id} 已存在")
                return self

            # 将任务添加到操作队列
            self._task_queue.put(("add", {
                "task_id": task_id,
                "task_func": task_func,
                "interval": interval,
                "unit": unit,
                "at_time": at_time,
                "run_immediately": run_immediately
            }))
            CommonUtil.printLog(f"添加任务 {task_id} 成功")
            return self

    def remove_task(self, task_id: str):
        """
        移除任务
        参数:
            task_id: 任务唯一标识
        """
        with self._lock:
            if task_id not in self._task_registry:
                CommonUtil.printLog(f"任务 {task_id} 不存在")
                return self

            self._task_queue.put(("remove", {"task_id": task_id}))
            return self

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        获取任务状态

        参数:
            task_id: 任务唯一标识

        返回:
            任务信息字典或None
        """
        with self._lock:
            if task_id in self._task_registry:
                return {
                    "task_id": task_id,
                    "status": "running"
                }
            return None

    def _scheduler_loop(self) -> None:
        """调度器主循环（在独立线程中运行）"""
        while not self._stop_event.is_set():
            # 处理任务队列中的操作
            while not self._task_queue.empty():
                operation, data = self._task_queue.get()

                if operation == "add":
                    self._add_task_internal(**data)
                elif operation == "remove":
                    self._remove_task_internal(**data)

            # 执行待处理的定时任务
            schedule.run_pending()
            time.sleep(0.5)  # 减少CPU占用

    def _add_task_internal(
            self,
            task_id: str,
            task_func: Callable,
            interval: int,
            unit: str,
            at_time: str,
            run_immediately: bool
    ) -> None:
        """内部方法：添加任务到schedule"""
        try:
            # 根据时间单位创建任务
            if unit == "seconds":
                job = schedule.every(interval).seconds
            elif unit == "minutes":
                job = schedule.every(interval).minutes
            elif unit == "hours":
                job = schedule.every(interval).hours
            elif unit == "days":
                job = schedule.every(interval).days
            elif unit == "weeks":
                job = schedule.every(interval).weeks
            else:
                raise ValueError(f"不支持的时间单位: {unit}")

            # 如果指定了at_time, 则在指定时间执行任务
            if at_time and unit in ['days', 'minutes', 'hours']:
                job.at(at_time)
            job.do(task_func)

            # 立即执行一次
            if run_immediately:
                threading.Thread(target=task_func, daemon=True).start()

            # 注册任务
            self._task_registry[task_id] = job
            CommonUtil.printLog(f"任务 {task_id} 已注册到schedule: 每 {interval} {unit} 执行一次")

        except Exception as e:
            CommonUtil.printLog(f"添加任务 {task_id} 失败: {e}")

    def _remove_task_internal(self, task_id: str) -> None:
        """内部方法：从schedule移除任务"""
        try:
            if task_id in self._task_registry:
                schedule.cancel_job(self._task_registry[task_id])
                del self._task_registry[task_id]
                CommonUtil.printLog(f"任务 {task_id} 已移除")
        except Exception as e:
            CommonUtil.printLog(f"移除任务失败: {e}")


# 使用示例
if __name__ == "__main__":
    # 创建调度器实例
    scheduler = SchedulerTaskManager()


    # 定义任务函数
    def task1():
        CommonUtil.printLog(f"执行任务1")


    def task2():
        CommonUtil.printLog(f"执行任务2")


    # 启动调度器
    scheduler.start()

    # 添加任务
    scheduler.add_task("task1", task1, 10, "seconds")  # 每10秒执行一次
    scheduler.add_task("task2", task2, 5, "seconds")  # 每5秒执行一次

    # # 5秒后移除任务1
    # time.sleep(5)
    # scheduler.remove_task("task1")

    # 程序运行20秒后退出
    time.sleep(30)
    scheduler.stop()
