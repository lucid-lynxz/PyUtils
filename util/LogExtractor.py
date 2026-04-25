from typing import Dict, List, Optional, Callable

import pandas as pd
from typing_extensions import Self

from util.CommonUtil import CommonUtil
from util.CompressUtil import CompressUtil
from util.FileUtil import FileUtil
from util.NetUtil import NetUtil


class LogExtractor:
    """
    日志信息提取器工具类 - 支持流式链式调用
    示例:
    # ✨ 流式调用（类似 Kotlin）
    result = (
        LogExtractor('app_log.zip') # 指定日志所在zip压缩包路径, 允许传None表示不从压缩包中读取
        .update_zip_path('http://xxx') # 更新日志zip压缩包路径,支持http
        .read_file('logs/error.log') # 日志原始列内容列表
        .filter({  #  根据正则表达式, 匹配出关键数据值
            'error_code': r'ErrorCode:(\d+)',
            'message': r'Message:(.*)'
        }, start_pattern=r'=== TestCase Start ===')
        .distinct() # 对结果去重
        .get_result() # 提取结果, 是个 Dict[str, List[str]]
    )
    """

    def __init__(self, zip_path: Optional[str] = None, cache_dir: str = None, sub_dir_name: str = None,
                 line_mode: bool = True, re_flag: int = 0):
        """
        默认从压缩包中读取指定日志文件内容, 再进行过滤, 也支持绝对路径
        @param zip_path: zip包本地路径或者可下载的url路径, 比如: http://xxx.aliyuncs.com/logs/测试日志_1775183375996.zip?OSSAccessKeyId=xx&Expires=xxx&Signature=xxx
                        若为空, 则表示不需要从zip中提取日志文件
        @param cache_dir: zip下载或解压等需要使用的缓存根目录, 若为空, 则自动在当前目录下创建一个 cache 缓存根目录
        @param sub_dir_name: 在 cache_dir 下允许创建一个子目录用于存放本次下载的文件, 若为空,则不会创建子目录, 直接会在 cache_dir 中存储
        @param line_mode: 是否逐行匹配日志
        @param re_flag: filter() 正则匹配使用的flags
        """
        self.zip_path = ''
        self.log_files = []  # 日志文件列表, 对于传入日志目录时会提取该目录下的子文件路径, filter()时会遍历所有日志文件
        self.log_in_zip: bool = True
        self.log_charset: str = 'utf-8'
        self.result: Dict[str, List[str]] = {}  # 过滤后的日志关键信息
        self.cache_dir = cache_dir or FileUtil.create_cache_dir(None, __file__)
        self.sub_dir_name = '' if CommonUtil.isNoneOrBlank(sub_dir_name) else sub_dir_name
        self.default_filter_params = {
            'line_mode': line_mode,
            'flags': re_flag
        }
        self.update_zip_path(zip_path)

    def update_zip_path(self, zip_path: str, **kwargs) -> Self:
        """
        更新zip包路径, 并按需下载到本地
        @param zip_path: zip包本地路径或者可下载的url路径, 比如: http://xxx.aliyuncs.com/logs/测试日志_1775183375996.zip?OSSAccessKeyId=xx&Expires=xxx&Signature=xxx
        @param kwargs: 其他参数, 主要用于下载, 如: auth=('账号', '密码'), timeout=10 force_download=False
        """
        self.zip_path = zip_path
        if self.zip_path and self.zip_path.startswith('http'):
            save_dir = FileUtil.recookPath(f'{self.cache_dir}/{self.sub_dir_name}/')
            local_zip_path = NetUtil.download(self.zip_path, save_dir, **kwargs)
            if CommonUtil.isNoneOrBlank(local_zip_path):
                print(f'下载文件失败: {self.zip_path}')
                self.zip_path = ''
            else:
                self.zip_path = local_zip_path
        return self

    def read_file(self, target_path: str, in_zip: bool = True, charset: str = 'utf-8') -> Self:
        """
        读取日志文件内容
        @param target_path: 日志文件路径, 若是从zip中读取, 则表示在zip中的相对路径, 也支持目录, 需要以'/' 或者 '\\' 结尾, filter()时会遍历所有日志文件
        @param in_zip: 是否从zip包中读取日志文件, 有传入 zip_path 时有效
        @param charset: 读取文件的编码格式
        """
        target_path = FileUtil.recookPath(target_path)
        is_dir = FileUtil.isDirPath(target_path)
        in_zip = in_zip and FileUtil.isFileExist(self.zip_path)
        self.log_files = [target_path]
        self.log_in_zip = in_zip
        self.log_charset = charset
        if is_dir:
            if in_zip:
                self.log_files = CompressUtil.list_files(self.zip_path, target_path)
            else:
                self.log_files = FileUtil.listAllFilePath(target_path)

        return self  # 返回自身，支持链式调用

    def __read_file(self, target_path: str, in_zip: bool, charset: str = 'utf-8') -> Optional[List[str]]:
        """

        """
        target_path = FileUtil.recookPath(target_path)
        in_zip = in_zip and FileUtil.isFileExist(self.zip_path)

        if in_zip:
            return CompressUtil.read_zip_file_content(self.zip_path, target_path, charset=charset, mode='lines')
        else:
            return FileUtil.readFile(target_path, encoding=charset)

    def filter(self, patterns: Dict[str, str], **kwargs) -> Self:
        """过滤数据, 若多次调用, 则会合并所有结果"""
        # 合并参数，kwargs 会覆盖 default_params 中的同名键
        merged_kwargs = {**self.default_filter_params, **kwargs}

        # 遍历 self.log_files
        for log_file in self.log_files:
            data = self.__read_file(log_file, self.log_in_zip, self.log_charset)
            _cur_result = CommonUtil.filter_list(data, patterns, **merged_kwargs)
            _cur_result = {k: v for k, v in _cur_result.items() if not CommonUtil.isNoneOrBlank(v)}
            # self.result = {**self.result, **_cur_result} # 合并dict,并以后面的数据为准
            self.result = CommonUtil.merge_dict(self.result, _cur_result)  # 拼接合并dict, 会保留所有数据
        return self

    def distinct(self) -> Self:
        """对结果列表中的list元素进行去重保序"""
        for key in self.result:
            self.result[key] = CommonUtil.deduplicate_list(self.result[key])
        return self

    def get_result(self) -> Dict[str, List[str]]:
        """获取最终结果"""
        return self.result

    def print_result(self) -> Self:
        """
        打印结果
        """
        CommonUtil.printLog(CommonUtil.format_dict(self.result, json_mode=False, kv_sep_flag='\n'))
        return self

    def reset(self) -> Self:
        """
        清除数据
        """
        self.log_files = []
        self.result = {}  # 过滤后的日志关键信息
        self.update_zip_path('')
        return self

    def do(self, action: Callable[[Dict[str, List[str]]], None]) -> Self:
        """
        对日志过滤结果执行指定方法, 比如更新数据到表格等
        @param action: 方法
        """
        action(self.result)
        return self

    def batch_filter(
            self,
            excel_path: str,
            filter_patterns: Dict[str, str],
            log_relative_path: Optional[str] = None,
            start_row: int = -1,
            end_row: int = -1,
            log_url_column: str = 'log_url',
            local_log_column: str = 'local_log',
            result_combine_flags: Optional[Dict[str, str]] = None,
            default_combine_flag: str = ',',
            force_download: bool = False,
            force_filter: bool = False
    ) -> pd.DataFrame:
        """
        处理Excel中的日志下载任务, 读取其中的 log_url 列数据进行下载, 下载完完成后更新本地日志路径到 local_Log 列
        并根据 filter_patterns 对日志文件进行多个关键信息提取, 提取的每个关键信息是个list, 再进行拼接生成str并回更到excel文件中

        Args:
            excel_path: Excel文件路径
            filter_patterns: 过滤用的正则表达式, 支持多个, 其中key表示简写的名称,最终会变成excel中的列名, 并将其value值作为数据也更新到excel中
            log_relative_path: 最终要过滤的日志文件在 local_log_column 文件中的相对路径, 主要将日志在zip包中的相对路径传入, 传入空表示不需要解压,直接读取
            start_row: 起始行号(从0开始,-1表示不限制)
            end_row: 结束行号(从0开始,-1表示不限制)
            log_url_column: 记录在线日志下载链接的列名
            local_log_column: 下载完成后, 记录本地日志路径的列名
            result_combine_flags: 日志信息过滤完成后, 对列表进行合并时使用的连接符, 允许不同日志使用不同的连接符, 若未指定, 则兜底使用 default_combine_flag
            default_combine_flag: 日志过滤后, 每种信息都是个列表, 将列表拼接成字符串时, 默认使用的分隔符
            force_download: 本地对应的日志文件存在时, 是否重新下载, 若为 False, 则会跳过下载及之后的操作
            force_filter: 本地有对应的日志文件时, 是否重新过滤, 若为 False, 则会跳过过滤

        Returns:
            更新后的DataFrame
        """
        # 1. 读取Excel
        print(f"读取Excel文件: {excel_path}")
        df = pd.read_excel(excel_path, sheet_name=0)

        print(f"总数据行数: {len(df)}")
        print(f"列名: {list(df.columns)}")

        # 2. 过滤行号范围
        if start_row >= 0 or end_row >= 0:
            original_count = len(df)

            if start_row < 0:
                start_row = 0
            if end_row < 0:
                end_row = len(df) - 1

            # 确保范围有效
            start_row = max(0, start_row)
            end_row = min(len(df) - 1, end_row)

            print(f"按行号过滤({start_row}-{end_row}): 将处理 {end_row - start_row + 1} 行数据")

        # 3. 过滤 log_url 非空且 local_log 不存在或为空的数据
        # 检查 log_url 列是否存在
        if log_url_column not in df.columns:
            raise ValueError(f"Excel中不存在 {log_url_column} 列")

        # 过滤 log_url 非空
        mask_valid_url = df[log_url_column].notna() & (df[log_url_column].astype(str).str.strip() != '')

        # 如果指定了行号范围,则在范围内应用掩码
        if start_row >= 0 and end_row >= 0:
            # 创建一个全False的掩码
            mask_in_range = pd.Series([False] * len(df), index=df.index)
            # 只标记范围内的行为True
            mask_in_range.iloc[start_row:end_row + 1] = True
            # 与有效URL掩码进行与运算
            mask_valid_url = mask_valid_url & mask_in_range

        # 检查 local_log 列是否存在
        has_local_log = local_log_column in df.columns

        if has_local_log and not force_download and not force_filter:
            # local_log 列存在,过滤为空的
            mask_no_local = df[local_log_column].isna() | (df[local_log_column].astype(str).str.strip() == '')
            mask_need_download = mask_valid_url & mask_no_local
        else:
            # local_log 列不存在,所有 log_url 非空的都需要下载
            mask_need_download = mask_valid_url

        df_to_download = df[mask_need_download].copy()

        print(f"总数据行数: {len(df)}")
        print(f"需要下载的数量: {len(df_to_download)}")

        if len(df_to_download) == 0:
            print("没有需要下载的数据")
            return df

        # 4. 下载日志并更新 local_log
        downloaded_count = 0

        # 获取需要下载的行的原始索引
        download_indices = df[mask_need_download].index.tolist()

        for local_idx, original_idx in enumerate(download_indices):
            row = df.loc[original_idx]
            log_url = row[log_url_column]

            # 下载文件
            self.update_zip_path(log_url, force_download=force_download)
            local_path = self.zip_path

            if local_path:
                # 更新原DataFrame中的 local_log
                if has_local_log:
                    df.at[original_idx, local_log_column] = local_path
                else:
                    # 新增 local_log 列
                    df.at[original_idx, local_log_column] = local_path

                downloaded_count += 1
                print(f"[{local_idx + 1}/{len(download_indices)}] 下载成功: {local_path}")

                # 读取日志, 过滤数据, 并更新过滤到的关键信息
                target_log_path = log_relative_path if log_relative_path else local_path
                in_zip = not CommonUtil.isNoneOrBlank(log_relative_path)
                filter_result_dict = self.read_file(target_log_path, in_zip).filter(filter_patterns).distinct().get_result()

                result_combine_flags = result_combine_flags or {}
                for key in filter_result_dict:
                    flag = result_combine_flags.get(key, default_combine_flag)
                    df.at[original_idx, key] = flag.join(filter_result_dict[key]).lstrip(flag).rstrip(flag)
        print(f"\n下载完成! 成功: {downloaded_count}, 失败: {len(df_to_download) - downloaded_count}")

        # 5. 保存更新后的Excel
        df.to_excel(excel_path, index=False)
        print(f"结果已保存到: {excel_path}")
        return df


if __name__ == '__main__':
    # result = (
    #     LogExtractor('app_log.zip')
    #     .update_zip_path('http://xxx')
    #     .read_file('logs/error.log')
    #     .filter({
    #         'error_code': r'ErrorCode:(\d+)',
    #         'message': r'Message:(.*)'
    #     }, start_pattern=r'=== TestCase Start ===')
    #     .distinct()
    #     .print_result()
    #     .get_result()
    # )

    # 支持传入目录
    (LogExtractor().read_file(r'H:\Workspace\Python\PyUtils\log\\')
     .filter({'可用金额': '可用金额:(.*)$'})
     .print_result()
     .filter({'总金额': 'total_cash: (.*), max_finance_amount:'})  # 支持多次调用, 会合并所有结果
     .distinct()  # 对结果中的value列表进行去重
     .print_result())
