# coding=utf-8
import logging
import os
import sys
import time

if str(sys.argv[0]).endswith(".exe"):
    project_root_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
else:
    project_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DefaultCustomLog(object):
    """
    auto-tools 工程复制
    默认是自定义日志工具类
    """
    default_log_path: str = None  # 默认的日志路径

    @classmethod
    def get_log(cls, name, log_path=default_log_path, level=logging.DEBUG, use_stream_handler=True,
                use_file_handler=False):
        """
        使用默认配置获取日志实例
        :param name:日志名称
        :param log_path:日志路径
        :param level:日志级别
        :param use_stream_handler:是否输出到控制台,默认是True
        :param use_file_handler:是否保存到文件,默认是False
        :return:
        """
        log = logging.getLogger(name)
        log.setLevel(level)
        # log已经存在handler时不再绑定handler，防止日志重复打印
        if not log.handlers:
            if use_stream_handler:
                log.addHandler(LogHandlerSetting.get_stream_handler())
            if use_file_handler:
                log.addHandler(LogHandlerSetting.get_file_handler(log_path=log_path))
        return log


class LogHandlerSetting(object):
    """
    自定义日志处理器设置
    """
    save_log_dir_path: str = None  # 默认存储日志的路径

    @classmethod
    def get_file_handler(
            cls,
            log_path=None,
            log_level=logging.DEBUG,
            encoding='utf-8',
            formatter_str="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    ):
        """
        获取日志文件处理器，用于把日志写入文件
        :param log_path:日志文件完整路径, 默认用：{项目根目录}/log/{%Y-%m-%d}.log
        :param log_level: 日志级别
        :param encoding: 编码格式,默认:utf-8
        :param formatter_str: 日志格式化
        :return:logging.FileHandler
        """
        if LogHandlerSetting.save_log_dir_path is None or len(LogHandlerSetting.save_log_dir_path) == 0:
            LogHandlerSetting.save_log_dir_path = project_root_dir

        if log_path is None:
            # 不传log路径时，默认用：{项目根目录}/log/2019-7-25.log
            log_path = os.path.join(
                LogHandlerSetting.save_log_dir_path,
                "log",
                "%s.txt" % time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime()),
            )
        log_dir = os.path.dirname(log_path)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        file_handler = logging.FileHandler(log_path, encoding=encoding)
        file_handler.setLevel(log_level)
        formatter = logging.Formatter(formatter_str)
        file_handler.setFormatter(formatter)
        return file_handler

    @classmethod
    def get_stream_handler(cls, log_level=logging.DEBUG,
                           formatter_str="%(asctime)s - %(name)s - %(levelname)s - %(message)s", ):
        """
        获取字符流处理器，用于把日志输出到控制台
        :param log_level:日志级别
        :param formatter_str:日志格式化
        :return:logging.StreamHandler()
        """
        steam_handler = logging.StreamHandler()
        steam_handler.setLevel(log_level)
        formatter = logging.Formatter(formatter_str)
        steam_handler.setFormatter(formatter)
        return steam_handler
