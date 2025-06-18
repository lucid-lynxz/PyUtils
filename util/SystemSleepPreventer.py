import atexit
import ctypes
import platform
import signal
import subprocess
import threading
import time

import pyautogui


class SystemSleepPreventer:
    """
    跨平台防止系统休眠和锁屏的工具类

    使用示例:
    with SystemSleepPreventer():
        # 执行需要防止休眠的代码
        time.sleep(3600)  # 运行1小时
    """

    def __init__(self, interval: int = 60, keep_alive: bool = False):
        """
        初始化防休眠工具

        参数:
            interval: 鼠标移动间隔（秒），仅用于鼠标模拟模式
            keep_alive: 是否在后台持续运行（仅用于鼠标模拟模式）
        """
        self.os = platform.system()
        self.interval = interval
        self.keep_alive = keep_alive
        self.active = False
        self.thread = None
        self.original_mouse_pos = None
        self.caffeinate_process = None

        # 注册程序退出时的清理函数
        atexit.register(self._cleanup)

    def start(self) -> None:
        """开始防止系统休眠"""
        if self.active:
            return

        if self.os == "Windows":
            self._start_windows()
        elif self.os == "Darwin":  # macOS
            self._start_macos()
        elif self.os == "Linux":
            self._start_linux()
        else:
            # 默认使用鼠标模拟方式
            self._start_mouse_simulator()

        self.active = True
        print(f"已启用系统防休眠: {self.os}")

    def stop(self) -> None:
        """停止防止系统休眠，恢复默认设置"""
        if not self.active:
            return

        if self.os == "Windows":
            self._stop_windows()
        elif self.os == "Darwin":  # macOS
            self._stop_macos()
        elif self.os == "Linux":
            self._stop_linux()
        else:
            self._stop_mouse_simulator()

        self.active = False
        print(f"已禁用系统防休眠: {self.os}")

    def _start_windows(self) -> None:
        """Windows 系统防止休眠实现"""
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ES_DISPLAY_REQUIRED = 0x00000002

        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )

    def _stop_windows(self) -> None:
        """Windows 系统恢复休眠设置"""
        ES_CONTINUOUS = 0x80000000
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)

    def _start_macos(self) -> None:
        """macOS 系统防止休眠实现"""
        self.caffeinate_process = subprocess.Popen(
            ["caffeinate", "-dim"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    def _stop_macos(self) -> None:
        """macOS 系统恢复休眠设置"""
        if self.caffeinate_process:
            self.caffeinate_process.send_signal(signal.SIGINT)
            self.caffeinate_process.wait()
            self.caffeinate_process = None

    def _start_linux(self) -> None:
        """Linux 系统防止休眠实现"""
        subprocess.call(["xset", "s", "off"])
        subprocess.call(["xset", "s", "noblank"])
        subprocess.call(["xset", "-dpms"])

    def _stop_linux(self) -> None:
        """Linux 系统恢复休眠设置"""
        subprocess.call(["xset", "s", "on"])
        subprocess.call(["xset", "s", "blank"])
        subprocess.call(["xset", "+dpms"])

    def _start_mouse_simulator(self) -> None:
        """通过鼠标模拟防止系统休眠"""
        self.original_mouse_pos = pyautogui.position()
        self.thread = threading.Thread(
            target=self._mouse_simulator_loop,
            daemon=True
        )
        self.thread.start()

    def _stop_mouse_simulator(self) -> None:
        """停止鼠标模拟"""
        if self.original_mouse_pos:
            pyautogui.moveTo(*self.original_mouse_pos, duration=0.1)
            self.original_mouse_pos = None

    def _mouse_simulator_loop(self) -> None:
        """鼠标模拟循环"""
        try:
            while True:
                # 轻微移动鼠标
                pyautogui.moveRel(1, 0, duration=0.1)
                pyautogui.moveRel(-1, 0, duration=0.1)
                time.sleep(self.interval)
        except Exception as e:
            print(f"鼠标模拟线程异常: {e}")

    def _cleanup(self) -> None:
        """程序退出时的清理工作"""
        self.stop()

    def __enter__(self):
        """支持 with 语句"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 语句"""
        self.stop()
        return False  # 不抑制异常
