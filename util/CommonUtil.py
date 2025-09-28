# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os
import re
import sys
import time
import subprocess
import functools
import importlib.util
import logging
import platform
from typing import Type, Union, Optional

Number = Union[int, float]


class CommonUtil(object):
    # @classmethod
    # def convertStringEncode(cls, srcStr, srcEncode: str = "utf-8", toEncode=sys.stdout.encoding):
    #     """
    #     将字符串转为另一种编码,默认从 utf-8 转为默认控制台的编码,避免中文乱码等问题
    #     :param srcStr:  要进行编码转换的字符串
    #     :param srcEncode:  原始编码
    #     :param toEncode:  目标编码
    #     :return:
    #     """
    #     return srcStr.decode(srcEncode).encode(toEncode)
    _redirect_log_fun = None

    @classmethod
    def redirect_print_log(cls, func):
        """设置外部日志重定向函数, 函数包含一个字符串入参"""
        cls._redirect_log_fun = func

    @staticmethod
    def updateStdOutEncoding(encoding: str = 'utf8'):
        """
        修改标准输出的编码为utf8,可解决部分终端中文乱码问题
        """
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=encoding)

    @staticmethod
    def printLog(msg, condition: bool = True, prefix: str = "", includeTime: bool = True, prefer_redirect_log: bool = True):
        """
        打印日志, 默认使用print() 并会自动拼接当前时间信息, 打印格式为: {prefix}{时间信息}{msg}
        若设置了重定向函数, 并且 prefer_redirect_log=True, 则会使用重定向函数进行日志输出, 日志格式: {prefix}{msg}
        :param msg: 待打印的日志信息
        :param condition: 打印条件, 默认为True, false则不会打印
        :param prefix: 日志前缀, 默认为空
        :param includeTime: 是否包含时间信息, 默认为True, 默认的print有效
        :param prefer_redirect_log: 是否优先使用重定向函数进行日志输出, 默认为True
        """
        from util.TimeUtil import TimeUtil
        if condition:
            # 此处保持使用原始的 print() 语句
            try:
                if prefer_redirect_log and CommonUtil._redirect_log_fun is not None:
                    CommonUtil._redirect_log_fun(f'{prefix}{msg}')
                else:
                    ts = f"{TimeUtil.getTimeStr()} " if includeTime else ""
                    print(f"{prefix}{ts}{msg}", flush=True)
            except Exception as e:
                print(f"printLog exception {e}", flush=True)

    @classmethod
    def exeCmd(cls, cmd: str, printCmdInfo: bool = True, timeout: int = 30) -> str:
        """
        执行shell命令, 可得到返回值
        :param cmd: 待执行的命令
        :param printCmdInfo: 是否打印命令内容
        :param timeout: 超时时间, 单位秒, 默认30秒
        """
        try:
            # 使用subprocess模块执行命令，捕获标准输出和标准错误
            # shell=True表示在shell中执行命令
            # universal_newlines=True表示将输出视为文本而不是字节
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并标准错误到标准输出
                text=True,  # Python 3.7+ 使用text代替universal_newlines
                encoding=sys.getdefaultencoding(),  # 使用系统默认编码
                timeout=timeout  # 添加超时时间，防止命令卡死
            )

            # 获取命令的输出结果
            cmd_result = result.stdout.strip()

            # 打印命令信息和结果
            CommonUtil.printLog(f"exeCmd:{cmd}\n{cmd_result}".strip(), printCmdInfo)
            return cmd_result
        except subprocess.TimeoutExpired:
            CommonUtil.printLog(f"exeCmd 超时: {cmd}", printCmdInfo)
            return ""
        except Exception as e:
            CommonUtil.printLog(f"exeCmd exception:{cmd}\n{e}".strip(), printCmdInfo)
            return ""

    @classmethod
    def exeCmdByOSSystem(cls, cmd: str, printCmdInfo: bool = True):
        """
        通过os.system(xxx) 执行命令, 无返回信息
        """
        CommonUtil.printLog("execute cmd by os.system: %s" % cmd, printCmdInfo)
        os.system(cmd)

    @classmethod
    def isNoneOrBlank(cls, info) -> bool:
        """
        判断所给字符串或其他带有len()方法的对象是否为None或者空(空白字符),若是则返回True
        :param info: 待判断的带有len()方法的对象, 若是字符串,则会进行strip()后再处理
        :return:
        """
        if info is None or len(info) == 0:
            return True
        elif isinstance(info, str):
            return len(info.strip()) == 0
        else:
            return False

    @classmethod
    def changeSep(cls, src: str) -> str:
        """
        将指定路径的分隔符('/'),替换成系统标准的分隔符
        :param src: 原路径
        :return: 处理的路径str
        """
        return src.replace('/', os.sep)

    @classmethod
    def convert2str(cls, src: object, encoding: str = 'utf8') -> str:
        """
        将源数据转换为str
        """
        if isinstance(src, bytes):
            return bytes.decode(src, encoding=encoding)
        elif isinstance(src, str):
            return src
        elif isinstance(src, (int, float, bool)):
            return str(src)
        raise Exception('convert2str fail unsupport type:%s, value=%s' % (type(src), src))

    @staticmethod
    def recookPath(path: str, forceEnableLongPath: bool = False) -> str:
        """未避免循环导包,此处改为方法内import"""
        from util.FileUtil import FileUtil
        return FileUtil.recookPath(path, forceEnableLongPath)

    @staticmethod
    def isFileExist(path: str) -> bool:
        """
        与 FileUtil.isFileExist() 功能一致，为避免互相引用导致 ImportError，此处复制一个冗余方法
        功能：文件是否存在
        :param path: 文件路径
        :return: bool
        """
        path = CommonUtil.recookPath(path)
        if path is None or len(path) == 0:
            return False
        return os.path.exists(path)

    @staticmethod
    def getPlatformName() -> str:
        """
        获取当前系统名，固定返回小写字符串,如： windows linux macos
        """
        name = platform.system().lower()
        if 'darwin' == name:
            name = 'macos'
        return name

    @staticmethod
    def isWindows() -> bool:
        """
        当前是否是windows系统
        """
        return 'windows' == CommonUtil.getPlatformName()

    @staticmethod
    def isLinux() -> bool:
        return 'linux' == CommonUtil.getPlatformName()

    @staticmethod
    def isMacOS() -> bool:
        return 'macos' == CommonUtil.getPlatformName()

    @staticmethod
    def recookExeSuffix(path: str) -> str:
        """
        仅对文件(非目录)路径有效
        若是windows系统，则按需添加文件名后缀 .exe
        否则，删除存在的 .exe 后缀
        """
        if CommonUtil.isNoneOrBlank(path) or path.endswith('//') or path.endswith('\\'):
            return path

        if CommonUtil.isWindows():
            if not path.endswith('.exe'):
                path = '%s.exe' % path
        elif path.endswith('.exe'):  # 非windows系统时，删除 .exe 后缀
            path = path[:-4]
        return path

    @staticmethod
    def checkThirdToolPath(path: str, returnValueIfFileNotExist: str = '', autoAddExeSuffix: bool = False) -> str:
        """
        部分三方工具程序已內置到本项目中，见 `third_tools/` 目录
        本方法检测配置文件所提供的路径是否是内置路径，格式为：格式为：'third_tools/{工具目录名}/*/{可执行程序名}'
        如： third_tools/7z/*/7z 或者 third_tools/7z/*/7z.exe 表示7z可执行程序
        本方法会自动识别当前系统平台，并替换上述 ‘*’ 星号为具体平台名，同时仅windows平台才添加 .exe 后缀
        @param path:原始路径
        @param returnValueIfFileNotExist: 若处理后的程序文件不存在，则返回的值，默认返回空
        @param autoAddExeSuffix: 若是win系统则自动添加后缀 .exe， 否则删除 .exe 后缀
        @param 处理后的路径
        """
        path = CommonUtil.recookPath(path)
        if path.startswith('third_tools/') and '*' in path:
            platformName = CommonUtil.getPlatformName()
            path = path.replace('/*/', '/%s/' % platformName)
            path = CommonUtil.recookExeSuffix(path)

            # 拼接项目根目录路径，生成绝对路径
            root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = '%s/%s' % (root_path, path)

        if not CommonUtil.isFileExist(path):
            path = returnValueIfFileNotExist

        if autoAddExeSuffix:
            path = CommonUtil.recookExeSuffix(path)
        path = CommonUtil.recookPath(path)
        CommonUtil.printLog('checkThirdToolPath result=%s' % path)
        return path

    @staticmethod
    def convertStr2Float(src: str, defaultValue: float) -> float:
        try:
            return float(src)
        except ValueError:
            return defaultValue

    @staticmethod
    def convertStr2Int(src: str, defaultValue: int) -> int:
        try:
            return int(src)
        except ValueError:
            return defaultValue

    @staticmethod
    def killPid(pid: str):
        """
        结束指定pid的进程
        """
        if CommonUtil.isNoneOrBlank(pid):
            return

        try:
            if CommonUtil.isWindows():
                CommonUtil.exeCmdByOSSystem("taskkill /f /pid %s" % pid)
            else:
                import signal
                os.kill(int(pid), signal.SIGKILL)
                CommonUtil.printLog(f'killPid {pid}')
        except Exception as e:
            CommonUtil.printLog(f'killPid {pid} fail: {e}')

    @staticmethod
    def is_library_installed(library_name: Union[str, list]) -> bool:
        """
        检查给定的库是否已安装
        :param library_name: 库名 如 PIL (对应pillow包), 支持传一个str, 也支持传多个 list
        """
        if isinstance(library_name, list):
            for name in library_name:
                if not CommonUtil.is_library_installed(name):
                    return False
            return True
        return importlib.util.find_spec(library_name) is not None

    @staticmethod
    def get_module_path(module_name):
        """
        获取指定库的所在路径
        """
        spec = importlib.util.find_spec(module_name)
        if spec is not None:
            return spec.origin
        else:
            return None

    @staticmethod
    def get_input_info(tip: str, defaultValue: str, quit: str = "q") -> str:
        """
        获取用户输入的值
        :param tip: 提示语
        :param defaultValue:输入为空时,返回的默认值
        :return:
        """
        msg = input(tip).strip()
        _result = defaultValue
        if len(msg) > 0:
            _result = msg
        if quit is not None and quit == _result:
            exit(0)
        return _result

    @staticmethod
    def parse_number(
            s: str,
            target_type: Type[Number] = float,
            default: Optional[Number] = 0
    ) -> Optional[Number]:
        """
        从字符串中提取数值部分并解析为指定类型，失败时返回默认值
        使用示例: parse_number("(123.45)", int, 0)

        参数:
            s: 包含数值的字符串
            target_type: 目标类型，可选int或float（默认float）
            default: 解析失败时的默认值（默认None）

        返回:
            解析后的数值（类型为target_type），或默认值
        """
        if not isinstance(s, str) or not s.strip():
            return default

        s = s.strip()

        # 使用正则表达式提取连续的数值部分
        match = re.search(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', s)

        if not match:
            return default

        num_str = match.group(0)

        try:
            if target_type is int:
                # 对于int类型，先尝试直接转换（处理整数情况）
                return int(num_str)
            elif target_type is float:
                # 对于float类型，先转换为float再检查是否为整数
                num = float(num_str)
                return int(num) if num.is_integer() and target_type is int else num
            else:
                raise ValueError(f"Unsupported target type: {target_type}")
        except ValueError:
            return default

    @staticmethod
    def round_down_to_hundred(num: float) -> int:
        """将浮点数向下取整到最近的100整数倍"""
        return int(num // 100) * 100

    @staticmethod
    def extract_keys(lines: list, target_keys: list, flag: str = '=') -> dict:
        """
        从字符串列表中提取指定 key 的值，返回字典, 行格式默认: key=value
        @param lines: 包含字符串的列表, 每个元素都是str类型, 格式: key=value, 允许有空格
        @param  target_keys: 需要提取的 key 列表
        @param flag: 分隔符
        @return: 包含 key-value 的字典
        """
        result = {}
        if CommonUtil.isNoneOrBlank(lines) or CommonUtil.isNoneOrBlank(target_keys):
            return result

        for line in lines:
            line = line.strip()
            if not line or flag not in line:
                continue

            key_part, value_part = line.split(flag, 1)
            key = key_part.strip()
            value = value_part.strip()

            if key in target_keys:
                result[key] = value
        return result

    @staticmethod
    def set_windows_brightness(brightness: int) -> bool:
        """
        设置Windows系统屏幕亮度（0-100）
        需要安装wmi库: pip install wmi
        :param brightness: 亮度百分比（0-100）
        :return 是否设置成功
        """
        if CommonUtil.isWindows() and not CommonUtil.is_library_installed('wmi'):
            CommonUtil.printLog(f'请安装wmi库: pip install wmi')
            return False

            # 检查亮度值是否在有效范围内
        if not (0 <= brightness <= 100):
            raise ValueError("亮度值必须在0-100之间")

        try:
            # 连接到WMI服务
            import wmi
            c = wmi.WMI(namespace='wmi')
            # 获取显示器亮度类实例
            monitor = c.WmiMonitorBrightnessMethods()[0]
            # 设置亮度
            monitor.WmiSetBrightness(brightness, 1)  # 第二个参数是超时时间（秒）
            return True
        except Exception as e:
            CommonUtil.printLog(f"设置亮度时出错: {e}")

    @staticmethod
    def windows_sleep():
        """让 Windows 系统进入休眠状态"""
        if not CommonUtil.isWindows():
            return
        try:
            # 调用 Windows 系统命令实现休眠
            subprocess.run(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                check=True,
                shell=True
            )
            CommonUtil.printLog("系统已进入休眠状态")
        except subprocess.CalledProcessError as e:
            CommonUtil.printLog(f"休眠命令执行失败: {e}")
        except Exception as e:
            CommonUtil.printLog(f"发生错误: {e}")

    @staticmethod
    def safe_decode(bytes_data):
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
        for encoding in encodings:
            try:
                return bytes_data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return bytes_data.decode('utf-8', errors='replace')


# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
default_logger = logging.getLogger(__name__)


def catch_exceptions(max_retries=0, retry_interval=1, logger=default_logger):
    """
    带重试功能的异常处理装饰器

    参数:
        max_retries: 最大重试次数,默认不充实
        retry_interval: 重试间隔(秒)
        logger: 日志记录器
    """
    if logger is None:
        logger = logging.getLogger()

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries > max_retries:
                        error_msg = f"任务 {func.__name__} 重试 {max_retries} 次后失败: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        # 发送告警
                        # send_alert(error_msg)
                        break

                    wait_msg = f"任务 {func.__name__} 执行异常，{retry_interval} 秒后重试 ({retries}/{max_retries}): {str(e)}"
                    logger.warning(wait_msg, exc_info=True)
                    time.sleep(retry_interval)
            return None

        return wrapper

    return decorator
