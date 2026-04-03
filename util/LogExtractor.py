from typing import Dict, List, Optional
from typing_extensions import Self
from util.CompressUtil import CompressUtil
from util.FileUtil import FileUtil
from util.CommonUtil import CommonUtil


class LogExtractor:
    """
    日志信息提取器工具类 - 支持流式链式调用
    示例:
    # ✨ 流式调用（类似 Kotlin）
    result = (
        LogExtractor('app_log.zip') # 指定日志所在zip压缩包路径, 允许传None表示不从压缩包中读取
        .read_file('logs/error.log') # 日志原始列内容列表
        .filter({  #  根据正则表达式, 匹配出关键数据值
            'error_code': r'ErrorCode:(\d+)',
            'message': r'Message:(.*)'
        }, start_pattern=r'=== TestCase Start ===')
        .distinct() # 对结果去重
        .get_result() # 提取结果, 是个 Dict[str, List[str]]
    )
    """

    def __init__(self, zip_path: Optional[str] = None):
        """
        默认从压缩包中读取指定日志文件内容, 再进行过滤, 也支持绝对路径
        """
        self.zip_path = zip_path
        self.data: List[str] = []  # 日志文件原始内容
        self.result: Dict[str, List[str]] = {}  # 过滤后的日志关键信息

    def read_file(self, target_path: str, in_zip: bool = True, charset: str = 'utf-8') -> Self:
        """
        读取日志文件内容
        @param target_path: 日志文件路径, 若是从zip中读取, 则表示在zip中的相对路径
        @param in_zip: 是否从zip包中读取日志文件
        """
        if in_zip:
            self.data = CompressUtil.read_zip_file_content(self.zip_path, target_path, charset=charset, mode='lines')
        else:
            self.data = FileUtil.readFile(target_path, encoding=charset)
        return self  # 返回自身，支持链式调用

    def filter(self, patterns: Dict[str, str], **kwargs) -> Self:
        """过滤数据"""
        self.result = CommonUtil.filter_list(self.data, patterns, **kwargs)
        return self

    def distinct(self) -> Self:
        """对结果列表中的list元素进行去重保序"""
        for key in self.result:
            self.result[key] = CommonUtil.deduplicate_list(self.result[key])
        return self

    def get_result(self) -> Dict[str, List[str]]:
        """获取最终结果"""
        return self.result
