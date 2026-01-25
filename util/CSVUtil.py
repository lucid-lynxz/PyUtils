# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import csv
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Type, TypeVar, Union, Dict, Callable

import numpy as np
import pandas as pd

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

T = TypeVar('T')  # 泛型类型

"""
CSV/padans工具类
支持: 
* read_csv(): 读取csv文件, 并将NaN值替换为空字符串

* read_csv_to_objects(): 读取csv文件, 对行数据进行字符替换, 并将每行数据转化为特定的对象
* extract_csv(): 从csv文件中提取指定列的数据, 支持关键字和行号过滤, 并进行数据清洗和处理

* merge_csv(): 合并多个csv文件, 支持按列名合并, 并进行数据去重
* merge_dataframe(): 合并多个DataFrame, 支持按列名合并, 并进行数据去重

* calc_csv_accuracy(): 计算csv文件中指定列的准确率(基于指定的真值基准列, 去统计指定列的准确率)
* calc_dataframe_accuracy(): 计算DataFrame中指定列的准确率

* to_markdown(): 将DataFrame转换为Markdown格式的字符串, 并存储到指定的文件中

* filter_and_replace_dataframe(): 过滤指定列的数据, 对结果进行行号二次过滤和指定数据替换

其他常用api:
重命名列名: df = df.rename(columns={'a': 'b'})
拼接不同的df:  df = pd.concat([df1, df2, df3], ignore_index=True)
"""


class CSVUtil(object):

    @staticmethod
    def read_csv(src_path: str, usecols: Optional[Union[pd.Index, List[str]]] = None, skip_rows: int = 0, encoding: str = 'utf-8-sig') -> pd.DataFrame:
        """
        以str格式读取CSV文件, 并将NaN值替换为空字符串
        :param src_path: csv源文件路径
        :param encoding: 编码
        :param usecols: 要读取的列, None或[] 表示读取全部列,否则只会保留有定义的列(若列不存在, 会自动添加)
        :param skip_rows: 要跳过读取的行数
        """
        try:
            df = pd.read_csv(src_path, encoding=encoding, dtype=str, skiprows=skip_rows, on_bad_lines='skip')
        except UnicodeDecodeError:
            encoding = FileUtil.detect_encoding(src_path, 'utf-8-sig')
            df = pd.read_csv(src_path, encoding=encoding, dtype=str, skiprows=skip_rows)

        df = CSVUtil.reorder_cols(df, usecols)
        return df.fillna('')

    @staticmethod
    def reorder_cols(df: pd.DataFrame, usecols: Optional[Union[pd.Index, List[str]]] = None) -> pd.DataFrame:
        """
        重排并只保留指定的列数据
        若要修改列名请自行调用接口: df=df.rename({'a':'b'}, inplace=False)
        注意返回的新的df 不影响入参的源df, 请按需重新赋值
        """
        df = CSVUtil.add_cols(df, usecols)
        if df is not None and not CommonUtil.isNoneOrBlank(usecols):
            df = df[usecols]  # 重排顺序
        return df

    @staticmethod
    def add_cols(df: pd.DataFrame, usecols: Optional[Union[pd.Index, List[str]]] = None) -> Optional[pd.DataFrame]:
        """
        按需添加列
        若要修改列名请自行调用接口: df=df.rename({'a':'b'}, inplace=False)
        """
        if df is None:
            return None

        if not CommonUtil.isNoneOrBlank(usecols):
            for col in usecols:
                if col not in df.columns:
                    df[col] = ''  # 初始化为空字符
                    CommonUtil.printLog(f'{col}列不存在, 添加')
        return df

    @staticmethod
    def contains_cols(df: pd.DataFrame, cols: List[str], all_match: bool = True) -> bool:
        """
        检查DataFrame中是否包含指定的列
        :param df: DataFrame
        :param cols: 列名列表
        :param all_match: 是否全部匹配, True-全部匹配, False-只要有一个匹配即可
        :return: 是否包含
        """
        if df is None or CommonUtil.isNoneOrBlank(cols):
            return False
        columns = df.columns.tolist()
        match_result = [col in columns for col in cols]
        return all(match_result) if all_match else any(match_result)

    @staticmethod
    def to_csv(df: pd.DataFrame, output_path: str, encoding: str = 'utf-8-sig', index=False, lineterminator='\n', mode: str = 'w') -> bool:
        """
        将DataFrame保存为CSV文件
        :param df: DataFrame
        :param output_path: 输出路径
        :param encoding: 编码
        :param index: 是否保存索引
        :param lineterminator: 行分隔符
        :param mode: 保存模式, w-覆盖  a-追加
        """
        if CommonUtil.isNoneOrBlank(output_path):
            return False

        try:
            FileUtil.createFile(output_path, False)
            df.to_csv(output_path, index=index, encoding=encoding, lineterminator=lineterminator, mode=mode)
            CommonUtil.printLog(f'to_csv success: total rows={len(df)}, 保存数据到: {output_path}')
            return True
        except Exception as e:
            CommonUtil.printLog(f'to_csv fail: {e}\n保存数据到: {output_path}')
            return False

    @staticmethod
    def read_csv_to_objects(
            file_path: str,
            object_class: Type[T],
            skip_rows: int = 0,
            delimiter: str = ',',
            encoding: str = 'utf-8',
            skip_empty_line: bool = True,
            replace_dict: Optional[Dict[str, str]] = None
    ) -> List[T]:
        """
        读取CSV文件并转换为对象列表
        会跳过以 # 或 ; 开头的行
        skip_empty_line=True时, 还会跳过空白行
        泛型对象T中必须包含有一个函数:

        @classmethod
        def by_csv_row(cls, row: List[str]):
            pass

        参数:
        - file_path: CSV文件路径
        - object_class: 目标对象类（需实现 by_csv_row 方法）
        - skip_rows: 跳过的行数（默认为1，跳过标题行）
        - delimiter: 分隔符（默认为逗号）
        - encoding: 文件编码（默认为utf-8）
        - skip_empty_line: 是否跳过空行
        - replace_dict: 将指定的字符串替换为其他字符串的字典, 如: {'#': '#', ' ': ''}

        返回:
        - 对象列表
        """
        objects = []
        file_path = FileUtil.recookPath(file_path)
        if not FileUtil.isFileExist(file_path):
            return objects

        with open(file_path, 'r', encoding=encoding) as file:
            reader = csv.reader(file, delimiter=delimiter)

            # 跳过指定行数
            for _ in range(skip_rows):
                next(reader, None)

            # 逐行解析并转换为对象
            for row_num, row in enumerate(reader, start=skip_rows):
                if skip_empty_line and (not row or all(not cell.strip() for cell in row)):  # 跳过空行
                    continue

                if row[0].startswith('#') or row[0].startswith(';'):  # 跳过以 # 或 ; 开头的行
                    continue

                # 按需去除等号和空格, 将等号转为逗号,避免原内容中包含冒号时, 冒号会被识别为 key-value 的分隔符
                row_str = delimiter.join(row)
                ori_row_str = row_str
                if replace_dict:
                    for k, v in replace_dict.items():
                        row_str = row_str.replace(k, v)
                row = row_str.split(delimiter)

                try:
                    obj = object_class.by_csv_row(row)

                    obj.config_path = file_path
                    obj.row_number = row_num
                    obj.row_str = ori_row_str

                    objects.append(obj)
                except Exception as e:
                    print(f"警告: 第{row_num}行解析失败 - {e}. 行内容: {row},oriRowStr={row_str}")
                    # 可选择记录错误或跳过该行，此处选择跳过

        return objects

    @staticmethod
    def extract_csv(src_path: str, column_name: str, row_ranges: List[Union[int, tuple]] = None,
                    output_path: str = None, encoding: str = 'utf-8-sig',
                    remove_empty_row: bool = True,
                    process_func: Optional[callable] = None,
                    filter_columns_dict: Optional[Dict[str, str]] = None,
                    keep_all_columns: bool = False,
                    max_rows: Optional[int] = None) -> pd.DataFrame:
        """
        从指定CSV文件中提取指定列的部分数据，并可选择保存为新的CSV文件
        参考 extract_lines() 方法实现
        兼容单个数据跨多行存储的情况(带有\n换行符), 能正确识别为str数据

        @param src_path: 源CSV文件路径
        @param column_name: 要提取的列名，例如 'query'
        @param row_ranges: 行范围列表，每个元素是一个元组 (start_row(含), end_row(含)) 或单个行号，行号从0开始(不包括column行)
                          默认为None，表示处理全部数据范围
        @param output_path: 输出CSV文件路径，如果提供则保存为新的CSV文件，默认为None不保存
        @param encoding: 源文件编码，默认为 'utf-8-sig'
        @param remove_empty_row: 是否删除空白行，默认为True
        @param process_func: 可选的处理函数，用于对每个row数据进行处理，函数签名应为 func(data: str) -> str
        @param filter_columns_dict: 过滤条件字典，格式为 { 列名: 正则表达式 }，支持多列过滤
        @param keep_all_columns: 是否保留所有列数据，默认为False，只保留指定列
        @param max_rows: 最大输出行数，None表示全部输出，默认为None
        @return pd.DataFrame: 提取后的DataFrame
        """
        if not FileUtil.isFileExist(src_path):
            CommonUtil.printLog(f'extract_csv fail: 源文件不存在:{FileUtil.recookPath(src_path)}')
            return pd.DataFrame()

        try:
            # 读取CSV文件，使用 dtype=str 确保所有数据都作为字符串处理
            # keep_default_na=False 和 na_values=[''] 确保空值也被当作字符串处理
            # df = pd.read_csv(src_path, encoding=encoding, dtype=str, keep_default_na=False, na_values=[''])
            df = pd.read_csv(src_path, encoding=encoding, dtype=str)

            # 确保所有NaN值都被替换为空字符串
            df = df.fillna('')

            # 检查列是否存在
            if column_name not in df.columns:
                CommonUtil.printLog(f'extract_csv fail: 列 "{column_name}" 不存在于文件中')
                return pd.DataFrame()

            extracted_df = df.copy()

            # 如果没有提供过滤字典，则不过滤数据
            if filter_columns_dict is not None and len(filter_columns_dict) > 0:
                # 检查过滤列是否存在
                missing_columns = [col for col in filter_columns_dict.keys() if col not in extracted_df.columns]
                if missing_columns:
                    CommonUtil.printLog(f"警告: 列 {missing_columns} 不存在于DataFrame中")
                    return extracted_df

                # 根据是否使用正则表达式进行过滤
                filtered_df = extracted_df
                for filter_column, filter_keyword in filter_columns_dict.items():
                    filtered_df = filtered_df[filtered_df[filter_column].astype(str).str.contains(filter_keyword, regex=True, na=False)]
                extracted_df = filtered_df

            # 根据keep_all_columns参数决定是否保留所有列
            if not keep_all_columns:
                extracted_df = df[[column_name]].copy()

            # 处理行范围筛选
            if row_ranges is None:
                # 如果row_ranges为None，则处理全部数据范围
                final_df = extracted_df.reset_index(drop=True)
            else:
                # 根据行范围筛选数据
                selected_indices = []
                for row_range in row_ranges:
                    if isinstance(row_range, int):
                        # 单行提取
                        if 0 <= row_range < len(extracted_df):
                            selected_indices.append(row_range)
                    elif isinstance(row_range, tuple) and len(row_range) == 2:
                        # 范围提取
                        start_row, end_row = row_range
                        # 确保索引在有效范围内
                        start_row = max(0, start_row)
                        end_row = min(len(extracted_df) - 1, end_row)

                        # 提取范围内的行
                        if start_row <= end_row:
                            selected_indices.extend(range(start_row, end_row + 1))
                    else:
                        CommonUtil.printLog(f"extract_csv fail: 无效的行范围格式 {row_range}")
                        continue

                # 索引去重并排序索引
                selected_indices = sorted(list(set(selected_indices)))

                # 根据选定的索引提取数据
                final_df = extracted_df.iloc[selected_indices].reset_index(drop=True)

            # 如果提供了处理函数，则对数据进行处理
            if process_func is not None and callable(process_func):
                final_df[column_name] = final_df[column_name].apply(process_func)

            # 删除空白行
            if remove_empty_row:
                final_df = final_df[final_df[column_name].str.strip() != '']

            # 限制输出数据量
            if max_rows is not None and max_rows > 0:
                final_df = final_df.head(max_rows)

            # 如果提供了输出路径，则保存为新的CSV文件
            CSVUtil.to_csv(final_df, output_path, encoding=encoding)
            return final_df
        except Exception as e:
            CommonUtil.printLog(f'extract_csv_columns fail: {e}')
            return pd.DataFrame()

    @staticmethod
    def merge(df_left: pd.DataFrame, df_right: pd.DataFrame, on_column: str, priority_left: bool = True, keep_both: bool = True,
              deduplicate: bool = False):
        """
        合并两个DataFrame，去重并解决冲突
        对于 'on_column' 列值相同的记录, 只会保留一行, 若其他column值存在冲突, 则以 'priority' 指定的数据为准
        若只是简单的拼接不同的df,无需去重等操作,可直接使用原始接口: df = pd.concat([df1, df2, df3], ignore_index=True)

        :param df_left: 左侧DataFrame
        :param df_right: 右侧DataFrame
        :param on_column: 用于去重和合并的公共列名
        :param priority_left: 左侧 DataFrame的值在冲突时优先, 若为False, 则右侧 DataFrame的值优先
        :param keep_both: 是否保留两个DataFrame中的所有行(True: 保留所有行; False: 只保留优先级高的DataFrame中的行)
        :param deduplicate: 是否在合并前对两个DataFrame按on_column去重，默认False
        :return: 合并并去重后的最终 DataFrame
        """
        # 如果需要去重，则先对两个DataFrame按on_column去重，保留第一条记录
        if deduplicate:
            df_left = CSVUtil.deduplicate(df_left, on_column)
            df_right = CSVUtil.deduplicate(df_right, on_column)
        else:
            # 如果不去重但仍希望避免笛卡尔积效应，需要预处理重复记录
            # 当keep_both=False时，我们只保留一侧的数据，避免重复记录导致的笛卡尔积
            if not keep_both:
                if priority_left:
                    # 保留左侧DataFrame中的所有记录，去除右侧DataFrame中与左侧重复的记录（但保留右侧独有的记录）
                    # 先找出在左侧DataFrame中存在的query
                    left_queries = set(df_left[on_column])
                    # 从右侧DataFrame中移除与左侧重复的记录，但保留每组重复记录的第一条
                    df_right_no_duplicates = df_right[~df_right[on_column].isin(left_queries)]
                    # 合并右侧独有的记录和右侧重复记录的第一条
                    df_right_unique = df_right[df_right[on_column].isin(left_queries)].drop_duplicates(subset=[on_column], keep='first')
                    df_right = pd.concat([df_right_no_duplicates, df_right_unique]).reset_index(drop=True)
                else:
                    # 保留右侧DataFrame中的所有记录，去除左侧DataFrame中与右侧重复的记录（但保留左侧独有的记录）
                    # 先找出在右侧DataFrame中存在的query
                    right_queries = set(df_right[on_column])
                    # 从左侧DataFrame中移除与右侧重复的记录，但保留每组重复记录的第一条
                    df_left_no_duplicates = df_left[~df_left[on_column].isin(right_queries)]
                    # 合并左侧独有的记录和左侧重复记录的第一条
                    df_left_unique = df_left[df_left[on_column].isin(right_queries)].drop_duplicates(subset=[on_column], keep='first')
                    df_left = pd.concat([df_left_no_duplicates, df_left_unique]).reset_index(drop=True)

        if keep_both:
            # 保留两个DataFrame的所有行（原有逻辑）
            if not priority_left:
                df_left, df_right = df_right, df_left  # 交换位置，统一按左优先处理

            # 1. 合并
            merged_df = pd.merge(df_left, df_right, on=on_column, how='outer', suffixes=('_left', '_right'))

            # 2. 解决冲突
            right_columns = [col for col in merged_df.columns if col.endswith('_right')]
            for right_col in right_columns:
                left_col = right_col.replace('_right', '_left')
                # 当左侧值为空时，使用右侧值；否则使用左侧值
                merged_df[right_col] = np.where(
                    (merged_df[left_col].isna()) | (merged_df[left_col] == ''),
                    merged_df[right_col],
                    merged_df[left_col]
                )
                merged_df.drop(columns=[left_col], inplace=True)
                merged_df.rename(columns={right_col: right_col.replace('_right', '')}, inplace=True)

            # 对于左侧DataFrame中完全为空的列，使用右侧DataFrame中的值进行填充
            for col in merged_df.columns:
                if col != on_column and not col.endswith('_left') and not col.endswith('_right'):
                    # 检查该列是否在右侧DataFrame中存在
                    right_col_name = col + '_right'
                    if right_col_name in merged_df.columns:
                        # 如果当前列为空，则使用右侧列的值
                        merged_df[col] = np.where(
                            (merged_df[col].isna()) | (merged_df[col] == ''),
                            merged_df[right_col_name],
                            merged_df[col]
                        )
                        # 删除右侧列
                        merged_df.drop(columns=[right_col_name], inplace=True)

            return merged_df
        else:
            # 只保留优先级高的DataFrame中的行
            if priority_left:
                # 保留左侧DataFrame中的行，如果有冲突则使用左侧的值
                merged_df = pd.merge(df_left, df_right, on=on_column, how='left', suffixes=('_left', '_right'))

                # 解决冲突，优先使用左侧的值
                right_columns = [col for col in merged_df.columns if col.endswith('_right')]
                for right_col in right_columns:
                    left_col = right_col.replace('_right', '_left')
                    # 优先使用左侧的值，如果左侧为空则使用右侧的值
                    merged_df[left_col] = np.where(
                        (merged_df[left_col].isna()) | (merged_df[left_col] == ''),
                        merged_df[right_col],
                        merged_df[left_col]
                    )
                    merged_df.drop(columns=[right_col], inplace=True)
                    merged_df.rename(columns={left_col: left_col.replace('_left', '')}, inplace=True)

                # 对于左侧DataFrame中完全为空的列，使用右侧DataFrame中的值进行填充
                for col in merged_df.columns:
                    if col != on_column and not col.endswith('_left') and not col.endswith('_right'):
                        # 检查该列是否在右侧DataFrame中存在
                        right_col_name = col + '_right'
                        if right_col_name in merged_df.columns:
                            # 如果当前列为空，则使用右侧列的值
                            merged_df[col] = np.where(
                                (merged_df[col].isna()) | (merged_df[col] == ''),
                                merged_df[right_col_name],
                                merged_df[col]
                            )
                            # 删除右侧列
                            merged_df.drop(columns=[right_col_name], inplace=True)

                return merged_df
            else:
                # 保留右侧DataFrame中的行，如果有冲突则使用右侧的值
                merged_df = pd.merge(df_left, df_right, on=on_column, how='right', suffixes=('_left', '_right'))

                # 解决冲突，优先使用右侧的值
                right_columns = [col for col in merged_df.columns if col.endswith('_right')]
                for right_col in right_columns:
                    left_col = right_col.replace('_right', '_left')
                    # 优先使用右侧的值，如果右侧为空则使用左侧的值
                    merged_df[right_col] = np.where(
                        (merged_df[right_col].isna()) | (merged_df[right_col] == ''),
                        merged_df[left_col],
                        merged_df[right_col]
                    )
                    merged_df.drop(columns=[left_col], inplace=True)
                    merged_df.rename(columns={right_col: right_col.replace('_right', '')}, inplace=True)

                # 对于右侧DataFrame中完全为空的列，使用左侧DataFrame中的值进行填充
                for col in merged_df.columns:
                    if col != on_column and not col.endswith('_left') and not col.endswith('_right'):
                        # 检查该列是否在左侧DataFrame中存在
                        left_col_name = col + '_left'
                        if left_col_name in merged_df.columns:
                            # 如果当前列为空，则使用左侧列的值
                            merged_df[col] = np.where(
                                (merged_df[col].isna()) | (merged_df[col] == ''),
                                merged_df[left_col_name],
                                merged_df[col]
                            )
                            # 删除左侧列
                            merged_df.drop(columns=[left_col_name], inplace=True)

                return merged_df

    @staticmethod
    def merge_csv(csv1: str, csv2: str, on_column: str,
                  priority_left: bool = True,
                  encoding: str = 'utf-8-sig',
                  output_csv: Optional[str] = None,
                  keep_both: bool = True,
                  deduplicate: bool = False
                  ) -> pd.DataFrame:
        """
        合并两个CSV文件，并可以指定以哪个文件为准

        :param csv1: 第一个CSV文件路径 (作为 'left')
        :param csv2: 第二个CSV文件路径 (作为 'right')
        :param on_column: 用于合并的公共列名
        :param priority_left: 左侧 DataFrame的值在冲突时优先, 若为False, 则右侧 DataFrame的值优先
        :param output_csv: 将合并后的结果写入的输出CSV文件路径 (可选), None表示不输出
        :param encoding: CSV文件的编码
        :param keep_both: 是否保留两个DataFrame中的所有行(True: 保留所有行; False: 只保留优先级高的DataFrame中的行)
        :param deduplicate: 是否在合并前对两个DataFrame按on_column去重，默认False
        :return: 合并后的 DataFrame
        """
        df1 = CSVUtil.read_csv(csv1, encoding=encoding)
        df2 = CSVUtil.read_csv(csv2, encoding=encoding)

        merged_df = CSVUtil.merge(df1, df2, on_column, priority_left, keep_both, deduplicate)
        CSVUtil.to_csv(merged_df, output_csv, encoding=encoding, index=False)
        return merged_df

    @staticmethod
    def calc_accuracy(df: pd.DataFrame, column_base: str, column_compare: str, keyword: Optional[str] = None,
                      keyword_col: Optional[str] = None, enable_any_empty: bool = False, enable_all_empty: bool = False) -> dict:
        """
        计算指定列的准确率统计信息:
        1. 过滤 column_base 和 column_compare 均有值的数据
            会生成一个dataFrame, 记为: valid_df
            对应的数据量, 记为: valid_cnt  即: len(valid_df)
        2. 计算 valid_df 中 column_base 和 column_compare 相同值的数量
            会生成一个dataFrame, 记为: same_df
            对应的数据量, 记为: same_cnt  即: len(same_df)
        3. 计算准确率, 记为: accuracy = same_cnt / valid_cnt

        Args:
            df (pandas.DataFrame): 数据框
            column_base (str): 基准数据列名, 此为真值列
            column_compare (str): 待统计准确率的列名, 此为预测值列
            keyword (str, optional): 关键字过滤条件，如果提供且keyword_col不为空，则 keyword_col 列的值必须包含该关键字才被视为有效数据
            keyword_col (str, optional): 关键字所在的列名，用于判断是否满足条件。如果为None，则默认是: column_compare
            enable_any_empty (bool, optional): 是否允许任意一列是空。若为True，则允许列值为空字符串''或NaN 若为False,则两列都要求非空
            enable_all_empty (bool, optional): 是否允许所有列是空。若为True，则允许所有列都为空, 不做过滤, 优先级高于enable_any_empty

        Returns:
            dict: 包含统计信息的字典，各key含义如下：
                - total_cnt (int): 总数据数，即数据框的总行数
                - valid_cnt (int): 有效数据数，即两个列均有值的行数, 若 enable_empty=True, 则允许值为空
                - same_cnt (int): 匹配数据数，即两个列值相等的行数
                - accuracy (float): 准确率，计算公式为 same_cnt/valid_cnt
                - valid_df (pandas.DataFrame): 有效数据的DataFrame，即两个列均有值的数据子集
                - same_df (pandas.DataFrame): 匹配数据的DataFrame，即两个列值相等的数据子集
        """
        # 1. 总数据数
        total_cnt = len(df)

        # 2. 根据 enable_empty 参数过滤有效数据
        if enable_all_empty:  # 允许两列都为空,则无需做过滤
            valid_df = df
        elif enable_any_empty:  # 允许任意一列为空
            # 注意：NaN表示数据缺失，空字符串''表示数据存在但为空
            valid_df = df[(df[column_base].notna()) | (df[column_compare].notna())]
        else:
            # 不允许空值：两列都有值且不为空字符串
            valid_df = df[
                (df[column_base].notna()) &
                (df[column_compare].notna()) &
                (df[column_base].astype(str).str.strip() != '') &
                (df[column_compare].astype(str).str.strip() != '')
                ]
            # valid_df = df[df[column_base].notna() & df[column_compare].notna()]

        # 3. 如果提供了keyword和keyword_col参数，则进一步过滤keyword_col包含关键字的数据
        keyword_col = column_compare if keyword_col is None else keyword_col
        if keyword is not None and keyword_col is not None and keyword_col in df.columns:
            valid_df = valid_df[valid_df[keyword_col].astype(str).str.contains(keyword, na=False)]

        valid_cnt = len(valid_df)

        # 4. column_base 和 column_compare 值相等的数据量及对应DataFrame
        same_df = valid_df[valid_df[column_base].astype(str) == valid_df[column_compare].astype(str)]
        same_cnt = len(same_df)

        # 5. 准确率计算
        accuracy = same_cnt / valid_cnt if valid_cnt > 0 else 0

        return {
            'total_cnt': total_cnt,  # 总数据数
            'valid_cnt': valid_cnt,  # 有效数据数（两列均有值，且满足keyword条件）
            'same_cnt': same_cnt,  # 匹配数据数（两列值相等）
            'accuracy': accuracy,  # 准确率（匹配数/有效数）
            'valid_df': valid_df,  # 有效数据DataFrame
            'same_df': same_df  # 匹配数据DataFrame
        }

    @staticmethod
    def calc_csv_accuracy(csv_path: str, column_base: str, column_compare: str,
                          keyword: Optional[str] = None, keyword_col: Optional[str] = None, encoding: str = 'utf-8-sig',
                          enable_any_empty: bool = False, enable_all_empty: bool = False):
        """
        计算CSV文件指定列的准确率

        Args:
            csv_path (str): CSV文件路径
            column_base (str): 基准数据列名, 此为真值列
            column_compare (str): 待统计准确率的列名, 此为预测值列
            keyword (str, optional): 关键字过滤条件，如果提供且keyword_col不为空，则 keyword_col 列的值必须包含该关键字才被视为有效数据
            keyword_col (str, optional): 关键字所在的列名，用于判断是否满足条件。如果为None，则默认是: column_compare
            encoding (str): CSV文件的编码，默认为 'utf-8-sig'
            enable_any_empty (bool, optional): 是否允许任意一列是空。若为True，则允许列值为空
            enable_all_empty (bool, optional): 是否允许所有列是空。若为True，则允许所有列都为空,优先级高于enable_any_empty

        Returns:
            dict: 统计信息字典，包含准确率、有效数据数、匹配数据数、总数据数等信息
        """
        df = pd.read_csv(csv_path, encoding=encoding, dtype=str)
        return CSVUtil.calc_accuracy(df, column_base, column_compare, keyword, keyword_col, enable_any_empty, enable_all_empty)

    @staticmethod
    def to_markdown(df: pd.DataFrame, include_index: bool = True, output_file: Optional[str] = None, encoding: str = 'utf-8-sig',
                    title: Optional[str] = None, append: bool = False, align_flag: str = ':---:') -> str:
        """
        将 DataFrame 转换为 Markdown 表格字符串,并按需存储到文件中
        :param df: 输入的 DataFrame
        :param include_index: 是否包含索引列（默认为 True）
        :param output_file: 输出的 Markdown 文件路径（可选）
        :param encoding: 文件编码（默认为 'utf-8-sig'）
        :param title: 表格标题（可选），如果提供则在表格第一行添加标题行
        :param append: 是否追加到文件末尾（默认为 False）
        :param align_flag: 对齐方式 居中: ':---:'   左对齐: ':---' 右对齐: '---:'
        """
        if include_index:
            n_df = df.reset_index()  # 将index变成数据列,并返回一个行的df
        else:
            n_df = df

        markdown_str = "| " + " | ".join(n_df.columns) + " |\n"  # 表头-列名

        # 添加分隔行（必须在表头之后、数据行之前）
        markdown_str += "| " + " | ".join([align_flag] * len(n_df.columns)) + " |\n"

        # # 添加表格标题行（如果提供）
        # if title:
        #     # 创建标题行，将标题放在第一列，其余列为空
        #     title_row = f"| {title} "
        #     for i in range(len(n_df.columns) - 1):
        #         title_row += "| "
        #     title_row += "|\n"
        #     title_row += "| " + " | ".join([":---:"] * len(n_df.columns)) + " |\n"
        #     markdown_str = title_row + markdown_str

        for _, row in n_df.iterrows():
            markdown_str += "| " + " | ".join(str(v) for v in row) + " |\n"

        if not CommonUtil.isNoneOrBlank(title):
            markdown_str = f'**{title}**\n\n' + markdown_str

        if output_file:
            if append:
                FileUtil.append2File(output_file, markdown_str, encoding=encoding)
            else:
                FileUtil.write2File(output_file, markdown_str, encoding=encoding)

        return markdown_str

    @staticmethod
    def filter_and_replace(
            df: pd.DataFrame,
            filter_columns_dict: Optional[Dict[str, str]] = None,
            row_ranges: Optional[List[Union[int, tuple]]] = None,
            replace_columns_dict: Optional[Dict[str, str]] = None,
    ) -> pd.DataFrame:
        """
        对传入的DataFrame进行拷贝然后过滤，并在指定范围内替换指定列的数据

        @param df: 输入的DataFrame
        @param filter_columns_dict: 过滤条件字典，格式为 { 列名: 正则表达式 }，支持多列过滤
        @param row_ranges: 替换的行范围列表，每个元素是一个元组 (start_row, end_row) 或单个行号，
                          行号相对于过滤后的DataFrame，从0开始。
                          默认为None，表示替换所有行
        @param replace_columns_dict: 需要替换数据的列名字典，格式为 {列名: 替换值}
        @return: 处理后的DataFrame
                如果只过滤不替换, 则返回过滤后的DataFrame(仅包含符合条件的行)
                若有替换, 则返回替换后的完整DataFrame(包含所有行，但相关数据已被替换)
        """
        # 如果没有提供过滤字典，则不过滤数据
        if filter_columns_dict is not None and len(filter_columns_dict) > 0:
            # 检查过滤列是否存在
            missing_columns = [col for col in filter_columns_dict.keys() if col not in df.columns]
            if missing_columns:
                CommonUtil.printLog(f"警告: 列 {missing_columns} 不存在于DataFrame中")
                return df

            # 根据是否使用正则表达式进行过滤
            filtered_df = df
            for filter_column, filter_keyword in filter_columns_dict.items():
                filtered_df = filtered_df[filtered_df[filter_column].astype(str).str.contains(filter_keyword, regex=True, na=False)]
        else:
            # 不过滤，使用全部数据
            filtered_df = df

        # 如果没有指定要替换的列，则直接返回过滤后的DataFrame
        if not replace_columns_dict:
            return filtered_df

        # 确保要替换的列存在
        filtered_df = CSVUtil.add_cols(filtered_df, list(replace_columns_dict.keys()))

        # 确定要替换的行索引
        if row_ranges is None:
            # 默认替换所有过滤出的行
            replace_indices = filtered_df.index.tolist()
        else:
            # 根据指定范围确定要替换的行
            replace_indices = []
            for row_range in row_ranges:
                if isinstance(row_range, int):
                    # 单行替换
                    if 0 <= row_range < len(filtered_df):
                        replace_indices.append(filtered_df.index[row_range])
                elif isinstance(row_range, tuple) and len(row_range) == 2:
                    # 范围替换
                    start_row, end_row = row_range
                    # 确保索引在有效范围内
                    start_row = max(0, start_row)
                    end_row = min(len(filtered_df) - 1, end_row)

                    # 添加范围内的行索引
                    if start_row <= end_row:
                        replace_indices.extend(filtered_df.index[start_row:end_row + 1])
                else:
                    CommonUtil.printLog(f"警告: 无效的行范围格式 {row_range}")

        # 执行替换操作(在完整DataFrame上进行替换)
        for col, value in replace_columns_dict.items():
            df.loc[replace_indices, col] = value

        # 如果有替换操作，返回完整的DataFrame
        return df

    @staticmethod
    def sample_by_column_values(df: pd.DataFrame, column_name: str, value_counts_dict: Dict[str, int], balance_counts: bool = False) -> pd.DataFrame:
        """
        按指定列的不同值随机抽样

        Args:
            df: 源DataFrame
            column_name: 要筛选的列名
            value_counts_dict: 字典，key为要筛选的值，value为每个值要抽取的行数
            balance_counts: 是否平衡每个值的抽取数量，默认为False, 若为True,则会以实际各类可取数量的最小值作为最终获取数

        Returns:
            抽样后的DataFrame
        """

        if balance_counts:
            # 平衡模式：各类别数据量保持一致
            min_cnt = len(df)
            for value, cnt in value_counts_dict.items():
                filtered = df[df[column_name] == value]
                final_cnt = min(len(filtered), cnt)
                min_cnt = min(min_cnt, final_cnt)

            for key in value_counts_dict:
                value_counts_dict[key] = min_cnt

        sampled_dfs = []

        for value, count in value_counts_dict.items():
            # 筛选出该值的所有行
            filtered_df = df[df[column_name] == value]

            # 如果该值的行数少于要求的数量，则取全部
            # 否则随机抽取指定数量
            if len(filtered_df) <= count:
                sampled_dfs.append(filtered_df)
            else:
                sampled_dfs.append(filtered_df.sample(n=count, random_state=42))

        # 合并所有抽样的结果
        if sampled_dfs:
            result_df = pd.concat(sampled_dfs, ignore_index=True)
            # 打乱最终结果的顺序
            result_df = result_df.sample(frac=1, random_state=42).reset_index(drop=True)
            return result_df
        else:
            return pd.DataFrame()

    @staticmethod
    def deduplicate(df: pd.DataFrame, subset: Union[str, List[str]], keep: str = 'first') -> pd.DataFrame:
        """
        基于指定列对DataFrame进行去重操作, 返回去重后的DataFrame (不修改原DataFrame)
        P.S. 如果需要修改原DataFrame, 请使用: df.drop_duplicates(subset=subset, keep=keep, inplace=True)

        :param df: 待去重的DataFrame
        :param subset: 用于判断重复的列名或列名列表，如: 'column_name' 或 ['col1', 'col2']
        :param keep: 保留策略，'first'(默认)保留第一次出现的记录，'last' 保留最后一次出现的记录，False 删除所有重复项
        :return: 去重后的DataFrame
        """
        return df.drop_duplicates(subset=subset, keep=keep).reset_index(drop=True)

    @staticmethod
    def find_duplicate_rows(df: pd.DataFrame, subset: Union[str, List[str]]) -> pd.DataFrame:
        """
        查找并返回基于指定列的重复行，将重复的行排列在一起(保持原始索引)，便于快速查看重复内容
        P.S. 返回的dataframe会保留原索引,若需要重置索引, 请使用: result_df.reset_index(drop=True)

        :param df: 输入的DataFrame
        :param subset: 用于判断重复的列名或列名列表，如: 'column_name' 或 ['col1', 'col2']
        :return: 包含所有重复行的DataFrame，按重复组排列
        """
        # 找到所有重复的行（包括首次出现的行）
        duplicate_mask = df.duplicated(subset=subset, keep=False)
        duplicates_df = df[duplicate_mask]

        # 如果只有一列用于判断重复，直接按该列排序
        if isinstance(subset, str):
            sorted_df = duplicates_df.sort_values(by=[subset])
        else:
            # 如果是多列，按这些列排序，使重复的行聚集在一起
            sorted_df = duplicates_df.sort_values(by=subset)

        # return sorted_df.reset_index(drop=True) # 重置索引
        return sorted_df

    @staticmethod
    def filter_matching_columns(df: pd.DataFrame, column_pairs: Dict[str, str], all_match: bool = True, same_value: bool = True):
        """
        找出DataFrame中指定列对值相同或不同的数据行

        参数:
        df: pandas DataFrame
        column_pairs: dict, 键值对表示需要比较的列, 如 {'A': 'B', 'C': 'D'}
        all_match: bool, True表示所有条件都满足(AND)，False表示任意条件满足(OR)
        same_value: bool, True表示查找值相同的行，False表示查找值不同的行

        返回:
        过滤后的DataFrame，只包含满足条件的行
        """
        if not column_pairs:
            return df

        # 定义逻辑操作函数替代lambda表达式
        def and_operation(x, y):
            return x & y

        def or_operation(x, y):
            return x | y

        def same_compare(col1_param, col2_param):
            return df[col1_param] == df[col2_param]

        def diff_compare(col1_param, col2_param):
            return df[col1_param] != df[col2_param]

        # 根据all_match选择逻辑操作
        if all_match:
            mask = True
            op = and_operation
        else:
            mask = False
            op = or_operation

        # 根据same_value选择比较操作符
        if same_value:
            compare_op = same_compare
        else:
            compare_op = diff_compare

        # 遍历所有列对，检查每一对列的值是否符合条件
        for col1, col2 in column_pairs.items():
            condition = compare_op(col1, col2)
            mask = op(mask, condition)

        # 返回符合条件的行
        return df[mask]

    @staticmethod
    def filter_containing_columns(df: pd.DataFrame, column_pairs: Dict[str, str], all_match: bool = True):
        """
        找出DataFrame中指定列对值存在包含关系的数据行

        参数:
        df: pandas DataFrame
        column_pairs: dict, 键值对表示需要比较包含关系的列, 如 {'A': 'B', 'C': 'D'} 表示A包含B, C包含D
        all_match: bool, True表示所有条件都满足(AND)，False表示任意条件满足(OR)

        返回:
        过滤后的DataFrame，只包含满足包含关系条件的行
        """
        if not column_pairs:
            return df

        # 定义逻辑操作函数
        def and_operation(x, y):
            return x & y

        def or_operation(x, y):
            return x | y

        def contains_compare(col1_param, col2_param):
            """检查col1是否包含col2的值"""
            return df[col1_param].astype(str).str.contains(df[col2_param].astype(str), regex=False, na=False)

        # 根据all_match选择逻辑操作
        if all_match:
            mask = True
            op = and_operation
        else:
            mask = False
            op = or_operation

        # 遍历所有列对，检查每一对列的值是否符合包含关系
        for col1, col2 in column_pairs.items():
            condition = contains_compare(col1, col2)
            mask = op(mask, condition)

        # 返回符合条件的行
        return df[mask]

    @staticmethod
    def diff(df1: pd.DataFrame, df2: pd.DataFrame, on_columns: Union[str, List[str]], max_rows: Optional[int] = None) -> pd.DataFrame:
        """
        基于指定列的值进行唯一性判断，从df1中删除df2的数据，保留只唯一存在于df1的数据

        :param df1: 源DataFrame
        :param df2: 要从中删除数据的DataFrame
        :param on_columns: 用于比较的列名或列名列表
        :param max_rows: 最大返回行数, None表示不限制
        :return: 只在df1中存在而不在df2中的数据DataFrame
        """
        # 确保on_columns是列表格式
        if isinstance(on_columns, str):
            on_columns = [on_columns]

        # 检查指定的列是否都存在于两个DataFrame中
        missing_in_df1 = [col for col in on_columns if col not in df1.columns]
        missing_in_df2 = [col for col in on_columns if col not in df2.columns]

        if missing_in_df1:
            CommonUtil.printLog(f"警告: 列 {missing_in_df1} 不存在于df1中")
        if missing_in_df2:
            CommonUtil.printLog(f"警告: 列 {missing_in_df2} 不存在于df2中")

        result_df = df1.copy()
        if missing_in_df1 or missing_in_df2:
            pass
        else:
            # 使用merge和indicator参数来识别只在df1中存在的行
            result_df = result_df.merge(df2[on_columns].copy(), on=on_columns, how='left', indicator=True)
            # 保留只在df1中存在的行
            result_df = result_df[result_df['_merge'] == 'left_only'].drop('_merge', axis=1)

        result_df = result_df.reset_index(drop=True)
        if max_rows is not None:
            result_df = result_df.head(max_rows)
        return result_df

    @staticmethod
    def convert_dir_excels(src_dir: str, delete_src_excel: bool):
        """
        转换指定目录下的excel文件
        :param src_dir: excel所在目录
        :param delete_src_excel: 是否删除已转换的excel源文件
        """
        file_list: list = FileUtil.listAllFilePath(src_dir, depth=1)

        for file in file_list:
            full_name, name, ext = FileUtil.getFileName(file)

            if ext not in ['xls', 'xlsx']:
                continue

            converted_csv = f'{src_dir}/{name}.csv'
            CSVUtil.convert_excel(file, converted_csv)

            if delete_src_excel:
                FileUtil.deleteFile(file)

    @staticmethod
    def convert_excel(input_file: str, temp_csv: Optional[str] = None, ignore_exist: bool = True) -> str:
        """
        如果输入是 Excel，则转为可分块读取的 CSV 文件, 否则直接返回原文件路径
        :param input_file: 输入文件路径, 支持: .xlsx  .xls  .csv
        :param temp_csv: excel后存储的csv文件路径, 若为None,则使用input_file同目录下, 将后缀改为csv
        :param ignore_exist: 忽略已存在的csv文件, 直接转换并覆盖
        :return: 转换后的文件路径
        """
        input_lower = input_file.lower()
        if input_lower.endswith(('.xlsx', '.xls')):
            if CommonUtil.isNoneOrBlank(temp_csv):
                temp_csv = input_file.replace('.xlsx', '.csv').replace('.xls', '.csv')

            temp_csv = FileUtil.recookPath(temp_csv)
            full_name, name, ext = FileUtil.getFileName(input_file)

            if not FileUtil.isFileExist(temp_csv) or ignore_exist:
                CommonUtil.printLog(f"🔄 正在将 Excel 转换为 CSV 文件: {full_name}")
                try:
                    df = pd.read_excel(input_file, dtype=str)
                    CSVUtil.to_csv(df, temp_csv)
                    CommonUtil.printLog(f"✅ Excel 已成功转换为: {temp_csv}")
                except Exception as e:
                    CommonUtil.printLog(f"❌ Excel 转换失败: {e}")
                    raise
            else:
                CommonUtil.printLog(f"✅ 使用已有的 CSV: {temp_csv}")
            return temp_csv
        else:
            return input_file  # 已经是 CSV

    @staticmethod
    def batch_concurrency_process(csv_file: str, output_file: str,
                                  process_row_data: Callable[[pd.Series], None],
                                  col_keyword: str = 'query',
                                  filter_columns_dict: Optional[Dict[str, str]] = None,
                                  chunk_size: int = 1000,
                                  max_concurrent: int = 30,
                                  on_chunk_finished: Callable[[str, pd.DataFrame], None] = None) -> pd.DataFrame:
        """
        从csv文件中分批次提取数据, 批次内部对各行数据进行并发处理, 返回新结果, 并将结果覆盖回原行数据中

        :param csv_file: 输入CSV文件路径, 通常是: src.csv
        :param output_file: 输出CSV文件路径, 通常是: 自动_t.csv
                            若文件已存在, 会读取其 col_keyword 列信息,去重, 并跳过相关行数据的处理
        :param process_row_data: 行数据处理函数, 输入是原始行对象pd.Series, 直接在其上修改即可
        :param col_keyword: 在input/output文件中都要存在的列名, 用于去重, 处理新行数据时, 若检测到该列数据已有处理过的缓存,则实际使用缓存值
                            filter_columns_dict为空时,默认是检测 output_file 该存在该列数据时, 就认为这条数据 已处理过, 会跳过
        :param filter_columns_dict: 已处理数据的过滤条件，格式为 { 列名: 正则表达式 }，支持多列过滤, 被过滤条件命中的数据才表示已处理过
        :param chunk_size: 每次读取的行数
        :param max_concurrent: 批次内部数据处理的并发数
        :param on_chunk_finished: 每批次的数据处理完成后的回调函数, 输入为: 结果信息, 处理后的DataFrame
        """
        result_df = pd.DataFrame()
        # 1. 检查输入文件
        if not FileUtil.isFileExist(csv_file):
            CommonUtil.printLog(f"❌ 输入文件不存在: {csv_file}")
            return result_df

        # 2. 加载已处理的数据（用于去重）
        processed_queries = set()
        if FileUtil.isFileExist(output_file):
            try:
                if CommonUtil.isNoneOrBlank(filter_columns_dict):
                    filter_columns_dict = {}

                if col_keyword not in filter_columns_dict.keys():
                    filter_columns_dict[col_keyword] = r'\S+'  # 非空
                keys = filter_columns_dict.keys()
                usecols = list(keys)
                df_done = CSVUtil.read_csv(output_file, usecols=usecols)
                df_done = CSVUtil.filter_and_replace(df_done, filter_columns_dict)
                processed_queries = set(df_done[col_keyword].dropna())
                CommonUtil.printLog(f"✅ 检测到已有结果文件，跳过 {len(processed_queries)} 条已处理数据")
            except Exception as e:
                CommonUtil.printLog(f"⚠️ 读取已有结果失败，将重新处理全部数据: {e}")

        total_processed = 0
        start_time = time.time()

        # 3. 分块读取
        try:
            chunk_iter = pd.read_csv(csv_file, chunksize=chunk_size, dtype=str)
        except Exception as e:
            CommonUtil.printLog(f"❌ 无法分块读取文件 {csv_file}: {e}")
            return result_df

        # 5. 循环处理每个 chunk
        for chunk_idx, chunk in enumerate(chunk_iter, start=1):
            if col_keyword not in chunk.columns:
                CommonUtil.printLog(f"❌ 输入文件中缺少 '{col_keyword}' 列")
                return result_df

            # 清洗并过滤掉空值和已处理项
            queries_to_process = []
            for q in chunk[col_keyword]:
                if pd.isna(q):
                    continue
                q_str = str(q).strip()
                if q_str and q_str not in processed_queries:
                    queries_to_process.append(q_str)

            if not queries_to_process:
                CommonUtil.printLog(f"⏭️ 批次 {chunk_idx}: 无新数据，跳过")
                continue

            CommonUtil.printLog(f"▶ 处理批次 {chunk_idx} | 新增待处理: {len(queries_to_process)} 条")

            # 并发处理当前批次
            # with ThreadPoolExecutor 会等待所有任务都执行完成后再继续执行
            # result_df = pd.DataFrame()
            result_df = chunk
            with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                futures = [executor.submit(process_row_data, chunk.iloc[i]) for i in range(len(chunk))]
                # for future in futures:
                #     try:
                #         res = future.result()
                #         if isinstance(res, pd.Series):
                #             result_df = pd.concat([result_df, res.to_frame().T], ignore_index=True)
                #     except Exception as exc:
                #         CommonUtil.printLog(f"线程执行出错: {exc}")

            # 增量写入结果
            if len(result_df) > 0:
                # 写入文件（批次之间是串行的，不需要加锁）
                write_header = not FileUtil.isFileExist(output_file)
                result_df.to_csv(output_file, mode='a', header=write_header, index=False, encoding='utf-8-sig')

                # 更新已处理集合
                processed_queries.update(result_df[col_keyword].astype(str))
                total_processed += len(result_df)
                msg = f"✅ 批次 {chunk_idx} 完成 | 写入: {len(result_df)} 条 | 累计成功: {total_processed} "
                CommonUtil.printLog(msg)
                if on_chunk_finished:
                    on_chunk_finished(msg, result_df)

            # 可选：降低请求密度
            time.sleep(0.5)

        # 6. 总结统计
        elapsed = time.time() - start_time
        hours = elapsed / 3600
        CommonUtil.printLog(f"🎉 全部处理完成！")
        CommonUtil.printLog(f"📊 总耗时: {elapsed:.1f} 秒 ({hours:.2f} 小时)")
        CommonUtil.printLog(f"📈 总成功条数: {total_processed}")

        CommonUtil.printLog(f"📁 最终结果保存至: {output_file}")

    @staticmethod
    def merge_csv_in_dir(src_dir: str, output_csv_name: str = 'merge_result',
                         on_column: str = 'query', rename_cols: Optional[Dict] = None,
                         usecols: List[str] = None, skip_rows: int = 0,
                         reverse_list: bool = False, deduplicate: bool = True,
                         valid_name_pattern: str = '.*.csv',
                         exclude_name_pattern: str = r'^ignore_',
                         src_encoding: str = 'utf-8-sig',
                         save_encoding: str = 'utf-8-sig'
                         ) -> Optional[pd.DataFrame]:
        """
        合并指定目录下除 'output_name' 以及 'ignore_' 开头的 csv 文件, 并去重, 保存为 'output_name'.csv
        若当前目录下有excel文件,请自行调用 convert_dir_excel() 转换成csv文件再调用本方法进行合并
        要读取和保存的列名为由 'usecols' 定义, 请确保这些列名存在, 若不存在会自动创建一列空白列
        最后会新增一列: 'result_src' 用以记录当前数据来源于哪份文档

        :param src_dir: 源csv/xls/xlsx 文件所在目录, 输出文件也会存储在这个目录中, 比如脚本所在目录: os.path.dirname(os.path.abspath(__file__))
        :param output_csv_name: 最终合并生成的csv文件名(不包含 .csv 后缀), 传空表示不保存
        :param reverse_list: 获取到的csv文件是按名称自然排序的, 是否要倒序
        :param on_column: 合并和去重数据时的列依据, 非空, 若 rename_cols 非空, 则要求 on_column存在于重命名后的列名中
        :param rename_cols: 读取csv后, 对列名进行重命名, 格式为: { 原列名: 新列名 }
        :param usecols: 读取csv文件时要读取的列数据, None表示全部读取
        :param skip_rows: 读取csv文件时, 要跳过的表头行数, 注意若跳过后读取到的df不存在 on_column 列, 则会取消跳过,重新读取文件
        :param deduplicate: 合并后的数据是否要去重
        :param valid_name_pattern: 要合并的csv文件名(包含后缀)要满足的正则表达式
        :param exclude_name_pattern: 要剔除的csv文件名正则表达式
        :param src_encoding: 原csv所用编码, 用于读取
        :param save_encoding: csv合并后保存时所用的编码

        比如对于微信对账单excel文件, 会先转化为csv, 然后合并csv(基于时间去重)
        微信对账单前16行为统计信息表头, 需要跳过
        微信对账单的详情列名为:
        交易时间,交易类型,交易对方,商品,收/支,金额(元),支付方式,当前状态,交易单号,商户单号,备注
        """
        if CommonUtil.isNoneOrBlank(output_csv_name):
            output_csv = ''
        else:
            output_csv: str = f'{src_dir}/{output_csv_name}.csv'  # 最终生成的全量csv文件(已去重)
        file_list: list = FileUtil.listAllFilePath(src_dir, depth=1)

        valid_csv_list = []
        for file in file_list:
            full_name, name, ext = FileUtil.getFileName(file)

            if output_csv_name != name and ext == 'csv':
                if re.search(valid_name_pattern, full_name) and not re.search(exclude_name_pattern, full_name):
                    valid_csv_list.append(file)

        valid_csv_list = sorted(valid_csv_list, reverse=reverse_list)
        CommonUtil.printLog(f'待合并的csv文件列表为: {[FileUtil.getFileName(x)[0] for x in valid_csv_list]}')
        df = None
        for file in valid_csv_list:
            full_name, name, ext = FileUtil.getFileName(file)
            df_file = CSVUtil.read_csv(file, skip_rows=skip_rows, encoding=src_encoding)
            if not CommonUtil.isNoneOrBlank(rename_cols):
                df_file = df_file.rename(columns=rename_cols)

            if on_column not in df_file.columns:
                df_file = CSVUtil.read_csv(file, encoding=src_encoding)

                if not CommonUtil.isNoneOrBlank(rename_cols):
                    df_file = df_file.rename(columns=rename_cols)

            df_file = CSVUtil.reorder_cols(df_file, usecols)
            df_file['result_src'] = full_name  # 数据来源
            if df is None:
                df = df_file
                continue
            df = pd.concat([df, df_file], ignore_index=True)  # 确保数据完整,与原始值保持一致
            # df = CSVUtil.merge_dataframe(df, df_file, on_column=on_column, deduplicate=deduplicate)

        if df is None:
            print('merge_csv_files fail: df is None')
        else:
            if deduplicate:
                df = CSVUtil.deduplicate(df, on_column)  # 去重
            if not CommonUtil.isNoneOrBlank(output_csv):
                CSVUtil.to_csv(df, output_csv, encoding=save_encoding)
            print(f'merge_csv_files success: {output_csv_name}.csv saved, total rows: {len(df)}')
        return df

    @staticmethod
    def statistics_multi_col(df: pd.DataFrame, cols: List[str],
                             output_dir: str = None,
                             generate_img: bool = True,
                             show_img: bool = False,
                             merged_img_name: Optional[str] = 'merged_image_distribution.png',
                             round_digits: int = 1,
                             min_value: Union[float, int, str] = 1e-5,
                             nan_replace_value: Union[float, int, str] = 1e-6,
                             custom_index: List[str] = None) -> pd.DataFrame:
        """
        同时计算多列的统计数据并绘制各列的正态分布图, 然后将图合并成一张, 保存到 output_dir/merged_image_distribution.png
        :param df: 待统计的DataFrame
        :param cols: 待统计的列名列表
        :param output_dir: 输出目录, 用于存储图片, 若传空, 则不保存图片
        :param generate_img: 是否要绘制正则分布图
        :param show_img: 所有正态分布图绘制完成后,是否要显示合并结果图 默认False,
        :param merged_img_name: 合并所有正态分布图后生成的合并图片名称(带后缀), 非空时才会合并图片
        :param round_digits: 极大值/极小值/中位数/平均值/标准差 这几个float数据四舍五入要保留几位小数, 默认1位
        :param min_value: 统计列数据时, 允许的最小值, 只统计 >=min_value 的数据部分
        :param nan_replace_value: nan数据替换为指定值
        :param custom_index: 自定义列名, 若为空, 则使用 cols 作为最终返回的dataframe index名, 允许部分元素为空, 会使用 cols 替代
        :return 峰会各列的统计数据汇总表, 包含: '样本数', '极大值', '极小值', '中位数', '平均值', '标准差', '正态分布图'
        """
        index = []
        sample_list, max_list, min_list, median_list, mean_list, std_list = [], [], [], [], [], []
        img_list = []  # 正态分布图的保存路径

        custom_index_size = 0 if CommonUtil.isNoneOrBlank(custom_index) else len(custom_index)
        for i in range(len(cols)):
            col = cols[i]
            custom_col_name = col
            if custom_index_size > 0 and i < custom_index_size:
                custom_col_name = custom_index[i]
            index.append(custom_col_name)

            # 此处不显示,避免阻塞后续流程
            col_dict = CSVUtil.statistics_col(df, col, output_dir=output_dir,
                                              generate_img=generate_img, show_img=False,
                                              min_value=min_value, custom_col_name=custom_col_name)
            sample_list.append(col_dict['sample_size'])
            max_list.append(col_dict['max'])
            min_list.append(col_dict['min'])
            median_list.append(col_dict['median'])
            mean_list.append(col_dict['mean'])
            std_list.append(col_dict['std'])
            img_list.append(col_dict['img_path'])

        # 创建 DataFrame
        data = {
            'sample_size': sample_list,
            'max': max_list,
            'min': min_list,
            'median': median_list,
            'mean': mean_list,
            'std': std_list,
            '正态分布图': img_list
        }
        df = pd.DataFrame(data, index=index)

        # 设置列名（如果需要）
        df.columns = ['样本数', '极大值', '极小值', '中位数', '平均值', '标准差', '正态分布图']

        # 样本数列转为int型
        df['样本数'] = df['样本数'].fillna(nan_replace_value).astype(int)

        # 将极大值/极小值/中位数/平均值/标准差 float数据保留1位小数（先填充 NaN 值为 0）
        df[['极大值', '极小值', '中位数', '平均值', '标准差']] = (df[['极大值', '极小值', '中位数', '平均值', '标准差']]
                                                                  .fillna(nan_replace_value)
                                                                  .round(round_digits))

        # 将所有正态分布图合并为一张
        # 过滤 img_list 非空的数据
        img_list = [x for x in img_list if x]
        img_size = len(img_list)
        if img_size >= 2 and not CommonUtil.isNoneOrBlank(merged_img_name):
            mod = img_size % 2
            row_size = img_size // 2 + mod  # 2张图一行
            from util.ImageUtil import ImageUtil
            merge_image = ImageUtil.merge_images(img_list, rows=row_size)
            image_path = FileUtil.recookPath(f'{output_dir}/{merged_img_name}')
            ImageUtil.save_img(image_path, merge_image)
            CommonUtil.printLog(f'{cols}的正态分布图合并成功: {image_path}')
            # CommonUtil.printLog(f'{cols}的极大值极小值等统计信息如下: {df}')
            if generate_img and show_img:
                ImageUtil(merge_image).show()
        return df

    @staticmethod
    def statistics_col(df: pd.DataFrame, col: str,
                       x_label_name: str = '耗时',
                       output_dir: str = None,
                       generate_img: bool = True,
                       show_img: bool = True,
                       min_value: float = 1e-5,
                       custom_col_name: str = '') -> Dict[str, Union[float, int, str, None]]:
        """
        统计指定列的的各指标主句并绘制正态分布图 (双Y轴设计:频率占比% + 概率密度)
        :param df: 待统计的DataFrame
        :param col: 待统计的列名
        :param x_label_name: 绘制正态分布图时, x轴的名称
        :param output_dir: 输出目录, 用于存储图片, 若传空, 则不保存图片
        :param generate_img: 是否要绘制正则分布图
        :param show_img: 正态分布图绘制完成后,是否要直接显示
        :param min_value: 统计列数据时, 允许的最小值, 只统计 >=min_value 的数据部分
        :param custom_col_name: 自定义列名, 若为空, 则使用 col 作为正态分布图的标题名
        :return dict: 统计数据及正态分布图保存地址
                key: max/min/median/mean/std/sample_size/img_path
                含义: 极大值/极小值/中位数/平均值/标准差/样本数/正态分布图片保存地址
        """
        result_keys = ['max', 'min', 'median', 'mean', 'std', 'sample_size', 'img_path']
        result_dict: Dict[str, Union[float, int, str, None]] = {item: None for item in result_keys}
        custom_col_name = col if CommonUtil.isNoneOrBlank(custom_col_name) else custom_col_name

        # 避免 SettingWithCopyWarning
        df = df.copy()

        # 先转换为数值类型，处理字符串和空值
        df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=[col])
        df = df[df[col] >= min_value]

        if not df.empty:
            # 计算统计数据
            max_cost = df[col].max()  # 极大值
            min_cost = df[col].min()  # 极小值
            median_cost = df[col].median()  # 中位数
            mean_cost = df[col].mean()  # 平均值
            std_cost = df[col].std()  # 标准差

            CommonUtil.printLog(f'📊 {custom_col_name} 统计数据:')
            CommonUtil.printLog(f'   极大值: {max_cost:.2f} ms')
            CommonUtil.printLog(f'   极小值: {min_cost:.2f} ms')
            CommonUtil.printLog(f'   中位数: {median_cost:.2f} ms')
            CommonUtil.printLog(f'   平均值: {mean_cost:.2f} ms')
            CommonUtil.printLog(f'   标准差: {std_cost:.2f} ms')
            CommonUtil.printLog(f'   样本数: {len(df)}')

            result_dict['max'] = max_cost  # 极大值
            result_dict['min'] = min_cost  # 极小值
            result_dict['median'] = median_cost  # 中位数
            result_dict['mean'] = mean_cost  # 平均值
            result_dict['std'] = std_cost  # 标准差
            result_dict['sample_size'] = len(df)  # 样本数

            if generate_img:  # 绘制正态分布图
                import matplotlib.pyplot as plt
                import matplotlib
                import matplotlib.ticker as mticker
                from scipy import stats

                matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei']  # 支持中文
                matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

                fig, ax1 = plt.subplots(1, 1, figsize=(12, 7))
                ax2 = ax1.twinx()

                # 提取数据列表
                data_list = df[col].tolist()
                data_count = len(data_list)
                data_range = max_cost - min_cost

                # 动态计算 bins
                if data_range == 0:
                    # 如果所有数据点都相同，创建一个以该值为中心的单个bin
                    single_value = min_cost
                    bins = [single_value - 5, single_value + 5]
                else:
                    # 动态bin计算逻辑
                    num_bins = max(1, min(15, int(np.sqrt(data_count))))
                    bin_width = max(1, np.ceil(data_range / num_bins))
                    start_bin = np.floor(min_cost / bin_width) * bin_width
                    end_bin = np.ceil(max_cost / bin_width) * bin_width + bin_width
                    bins = np.arange(start_bin, end_bin, bin_width)

                # 使用 weights 参数将直方图转换为百分比
                weights = np.ones_like(data_list) * 100. / data_count
                _, _, hist_patches = ax1.hist(data_list, bins=bins, weights=weights, alpha=0.6,
                                              color='#1f77b4', edgecolor='black')

                # 收集图例元素
                handles = [hist_patches[0]]
                labels = ['频率分布直方图']

                # 仅在标准差>0时绘制正态曲线
                if std_cost > 0:
                    x_curve = np.linspace(min_cost - std_cost, max_cost + std_cost, 200)
                    p_curve = stats.norm.pdf(x_curve, mean_cost, std_cost)
                    curve_line, = ax2.plot(x_curve, p_curve, 'r-', linewidth=2.5)
                    handles.append(curve_line)
                    labels.append('正态分布曲线')
                else:
                    # 如果不画曲线，隐藏右侧Y轴
                    ax2.get_yaxis().set_visible(False)

                # 绘制平均值和中位数虚线
                mean_line = ax1.axvline(mean_cost, color='red', linestyle='dashed', linewidth=1.5)
                median_line = ax1.axvline(median_cost, color='green', linestyle='dashed', linewidth=1.5)

                handles.extend([mean_line, median_line])
                labels.extend([
                    f'平均值: {mean_cost:.2f}',
                    f'中位数: {median_cost:.2f}'
                ])

                # 设置X轴刻度
                ax1.set_xticks(bins)
                ax1.xaxis.set_major_formatter(mticker.FormatStrFormatter('%d'))
                plt.setp(ax1.get_xticklabels(), rotation=30, ha="right")

                # 设置Y轴为百分比格式
                ax1.yaxis.set_major_formatter(mticker.PercentFormatter())

                # 设置标签和标题
                ax1.set_xlabel(x_label_name, fontsize=11, fontweight='bold')
                ax1.set_ylabel('频率占比 (%)', color='#1f77b4', fontweight='bold', fontsize=11)
                ax2.set_ylabel('概率密度', color='red', fontweight='bold', fontsize=11)
                ax1.tick_params(axis='y', labelcolor='#1f77b4', labelsize=10)
                ax2.tick_params(axis='y', labelcolor='red', labelsize=10)
                ax1.set_title(f'{custom_col_name}-正态分布', fontsize=16, weight='bold')

                # 添加统计信息文本框
                stats_text = (
                    f"统计信息\n"
                    f"----------------\n"
                    f"数据点数: {data_count}\n"
                    f"标准差: {std_cost:.2f} ms\n"
                    f"最小值: {min_cost:.2f} ms\n"
                    f"最大值: {max_cost:.2f} ms"
                )
                ax1.annotate(stats_text, xy=(0.85, 0.97), xycoords='axes fraction', ha='left', va='top',
                             bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.9, edgecolor='gray'),
                             fontsize=10)

                # 创建图例
                ax1.legend(handles, labels, loc='upper left', fontsize=9)

                # 设置网格
                ax1.grid(True, linestyle='--', alpha=0.6)
                ax2.grid(False)
                plt.tight_layout()

                # 保存图片
                if not CommonUtil.isNoneOrBlank(output_dir):
                    plot_file = f'{output_dir}/distribution_{custom_col_name}.png'
                    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
                    CommonUtil.printLog(f'📈 {custom_col_name}分布图已保存至: {plot_file}')
                    result_dict['img_path'] = plot_file

                # 显示图片（可选）
                if show_img:
                    plt.show()
        else:
            CommonUtil.printLog(f'⚠️ 没有找到 {custom_col_name} >= {min_value} 的数据')
        return result_dict
