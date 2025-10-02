import sys
import time
from datetime import datetime


class TimedStdout:
    """拦截 stdout 和 logging 输出, 添加时间戳"""

    @staticmethod
    def activate(stdout: bool = True, logger: bool = False):
        """
        给三方库的日志输出统一添加时间戳信息
        :param stdout: 是否拦截 stdout 输出, 默认为 True
        :param logger: 是否拦截三方库的logging日志输出, 默认为 False
        """
        if stdout:
            # 在使用第三方库前替换 stdout
            sys.stdout = TimedStdout(sys.stdout)

        if logger:
            TimedStdout.setup_third_party_logger()

    def __init__(self, original_stdout):
        self.original_stdout = original_stdout

    def write(self, message):
        if message.strip() != "":  # 忽略空行
            # 格式化时间（年-月-日 时:分:秒）
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 拼接时间戳和原始消息
            self.original_stdout.write(f"{timestamp} {message}")
        else:
            self.original_stdout.write(message)

    def flush(self):
        self.original_stdout.flush()  # 确保输出及时刷新

    @staticmethod
    def setup_third_party_logger(logger_name="pybroker", time_format="%Y-%m-%d %H:%M:%S"):
        """
        若三方库使用功能了logging进行日志输出, 则可以通过本方法使输出的日志带有时间戳

        :param logger_name: 第三方库的日志器名称，默认为 "pybroker"
        :param time_format: 时间格式，默认为 "%Y-%m-%d %H:%M:%S"
        """
        import logging
        # 获取第三方库的日志器
        logger = logging.getLogger(logger_name)

        # 避免重复添加处理器
        if logger.handlers:
            return

        # 设置日志级别（根据需要调整，如 DEBUG/INFO/WARNING）
        logger.setLevel(logging.INFO)

        # 创建控制台处理器
        console_handler = logging.StreamHandler()

        # 定义日志格式（包含时间、级别、消息）
        formatter = logging.Formatter(
            fmt=f"%(asctime)s - %(levelname)s - %(message)s",
            datefmt=time_format
        )

        # 关联格式器和处理器
        console_handler.setFormatter(formatter)

        # 为日志器添加处理器
        logger.addHandler(console_handler)
