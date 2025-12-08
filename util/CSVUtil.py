# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import csv
from typing import Optional, List, Type, TypeVar, Union, Dict

import numpy as np
import pandas as pd

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

T = TypeVar('T')  # 泛型类型

"""
CSV/padans工具类
支持: 
* read_csv_to_objects(): 读取csv文件, 对行数据进行字符替换, 并将每行数据转化为特定的对象
* extract_csv(): 从csv文件中提取指定列的数据, 支持关键字和行号过滤, 并进行数据清洗和处理

* merge_csv(): 合并多个csv文件, 支持按列名合并, 并进行数据去重
* merge_dataframe(): 合并多个DataFrame, 支持按列名合并, 并进行数据去重

* calc_csv_accuracy(): 计算csv文件中指定列的准确率(基于指定的真值基准列, 去统计指定列的准确率)
* calc_dataframe_accuracy(): 计算DataFrame中指定列的准确率

* to_markdown(): 将DataFrame转换为Markdown格式的字符串, 并存储到指定的文件中
"""


class CSVUtil(object):
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
                    if '搜索历史记录' in row[0]:
                        print(f'搜索历史记录')
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
                    keyword: Optional[str] = None) -> pd.DataFrame:
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
        @param keyword: 待提取列数据中需包含的关键字，默认为None，不进行过滤
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

            # 提取指定列
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

            # 添加keyword过滤条件
            if keyword is not None:
                # 过滤出指定列包含keyword的数据
                final_df = final_df[final_df[column_name].astype(str).str.contains(keyword, na=False)].reset_index(drop=True)

            # 如果提供了处理函数，则对数据进行处理
            if process_func is not None and callable(process_func):
                final_df[column_name] = final_df[column_name].apply(process_func)

            # 删除空白行
            if remove_empty_row:
                final_df = final_df[final_df[column_name].str.strip() != '']

            # 如果提供了输出路径，则保存为新的CSV文件
            if output_path:
                FileUtil.createFile(output_path, False)
                final_df.to_csv(output_path, index=False, encoding=encoding, lineterminator='\n')
                CommonUtil.printLog(f'extract_csv 保存提取的数据到: {output_path}')
            return final_df
        except Exception as e:
            CommonUtil.printLog(f'extract_csv_columns fail: {e}')
            return pd.DataFrame()

    @staticmethod
    def merge_dataframe(df_left: pd.DataFrame, df_right: pd.DataFrame, on_column: str, priority_left: bool = True, keep_both: bool = True):
        """
        合并两个DataFrame，去重并解决冲突
        对于 'on_column' 列值相同的记录, 只会保留一行, 若其他column值存在冲突, 则以 'priority' 指定的数据为准

        :param df_left: 左侧DataFrame
        :param df_right: 右侧DataFrame
        :param on_column: 用于去重和合并的公共列名
        :param priority_left: 左侧 DataFrame的值在冲突时优先, 若为False, 则右侧 DataFrame的值优先
        :param keep_both: 是否保留两个DataFrame中的所有行(True: 保留所有行; False: 只保留优先级高的DataFrame中的行)
        :return: 合并并去重后的最终 DataFrame
        """
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
                merged_df[right_col] = np.where(merged_df[left_col].notna(), merged_df[left_col], merged_df[right_col])
                merged_df.drop(columns=[left_col], inplace=True)
                merged_df.rename(columns={right_col: right_col.replace('_right', '')}, inplace=True)

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
                    merged_df[left_col] = np.where(merged_df[left_col].notna(), merged_df[left_col], merged_df[right_col])
                    merged_df.drop(columns=[right_col], inplace=True)
                    merged_df.rename(columns={left_col: left_col.replace('_left', '')}, inplace=True)

                return merged_df
            else:
                # 保留右侧DataFrame中的行，如果有冲突则使用右侧的值
                merged_df = pd.merge(df_left, df_right, on=on_column, how='right', suffixes=('_left', '_right'))

                # 解决冲突，优先使用右侧的值
                right_columns = [col for col in merged_df.columns if col.endswith('_right')]
                for right_col in right_columns:
                    left_col = right_col.replace('_right', '_left')
                    # 优先使用右侧的值，如果右侧为空则使用左侧的值
                    merged_df[right_col] = np.where(merged_df[right_col].notna(), merged_df[right_col], merged_df[left_col])
                    merged_df.drop(columns=[left_col], inplace=True)
                    merged_df.rename(columns={right_col: right_col.replace('_right', '')}, inplace=True)

                return merged_df

    @staticmethod
    def merge_csv(csv1: str, csv2: str, on_column: str,
                  priority_left: bool = True,
                  encoding: str = 'utf-8-sig',
                  output_csv: Optional[str] = None,
                  keep_both: bool = True
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
        :return: 合并后的 DataFrame
        """
        df1 = pd.read_csv(csv1, encoding=encoding)
        df2 = pd.read_csv(csv2, encoding=encoding)

        merged_df = CSVUtil.merge_dataframe(df1, df2, on_column, priority_left, keep_both)
        if output_csv:
            merged_df.to_csv(output_csv, encoding=encoding, index=False)
        return merged_df

    @staticmethod
    def calc_dataframe_accuracy(df: pd.DataFrame, column_base: str, column_compare: str, keyword: Optional[str] = None, keyword_col: Optional[str] = None) -> dict:
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

        Returns:
            dict: 包含统计信息的字典，各key含义如下：
                - total_cnt (int): 总数据数，即数据框的总行数
                - valid_cnt (int): 有效数据数，即两个列均有值的行数
                - same_cnt (int): 匹配数据数，即两个列值相等的行数
                - accuracy (float): 准确率，计算公式为 same_cnt/valid_cnt
                - valid_df (pandas.DataFrame): 有效数据的DataFrame，即两个列均有值的数据子集
                - same_df (pandas.DataFrame): 匹配数据的DataFrame，即两个列值相等的数据子集
        """
        # 1. 总数据数
        total_cnt = len(df)

        # 2. column_base 和 column_compare 均有值的数据量
        valid_df = df[df[column_base].notna() & df[column_compare].notna()]

        # 3. 如果提供了keyword和keyword_col参数，则进一步过滤keyword_col包含关键字的数据
        keyword_col = column_compare if keyword_col is None else keyword_col
        if keyword is not None and keyword_col is not None and keyword_col in df.columns:
            valid_df = valid_df[valid_df[keyword_col].astype(str).str.contains(keyword, na=False)]

        valid_cnt = len(valid_df)

        # 4. column_base 和 column_compare 值相等的数据量及对应DataFrame
        same_df = valid_df[valid_df[column_base] == valid_df[column_compare]]
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
                          keyword: Optional[str] = None, keyword_col: Optional[str] = None, encoding: str = 'utf-8-sig'):
        """
        计算CSV文件指定列的准确率

        Args:
            csv_path (str): CSV文件路径
            column_base (str): 基准数据列名, 此为真值列
            column_compare (str): 待统计准确率的列名, 此为预测值列
            keyword (str, optional): 关键字过滤条件，如果提供且keyword_col不为空，则 keyword_col 列的值必须包含该关键字才被视为有效数据
            keyword_col (str, optional): 关键字所在的列名，用于判断是否满足条件。如果为None，则默认是: column_compare
            encoding (str): CSV文件的编码，默认为 'utf-8-sig'

        Returns:
            dict: 统计信息字典，包含准确率、有效数据数、匹配数据数、总数据数等信息
        """
        df = pd.read_csv(csv_path, encoding=encoding)
        return CSVUtil.calc_dataframe_accuracy(df, column_base, column_compare, keyword, keyword_col)

    @staticmethod
    def to_markdown(dataframe, include_index: bool = True, output_file: Optional[str] = None, encoding: str = 'utf-8-sig') -> str:
        """
        将 DataFrame 转换为 Markdown 表格字符串,并按需存储到文件中
        :param dataframe: 输入的 DataFrame
        :param include_index: 是否包含索引列（默认为 True）
        :param output_file: 输出的 Markdown 文件路径（可选）
        :param encoding: 文件编码（默认为 'utf-8-sig'）
        """
        if include_index:
            n_df = dataframe.reset_index()  # 将index变成数据列,并返回一个行的df
        else:
            n_df = dataframe

        markdown_str = "| " + " | ".join(n_df.columns) + " |\n"
        markdown_str += "| " + " | ".join(["---"] * len(n_df.columns)) + " |\n"
        for _, row in n_df.iterrows():
            markdown_str += "| " + " | ".join(str(v) for v in row) + " |\n"

        if output_file:
            FileUtil.write2File(output_file, markdown_str, encoding=encoding)

        return markdown_str
