#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
from typing import Dict, Optional, Tuple

from util.CommonUtil import CommonUtil


class CSVKeywordProcessor:
    """
    传入关键字及其类型的映射关系表, 支持从csv中读取数据后, 匹配关键字映射表, 并将映射的类型信息填入指定的列中
    主要方法:
    CSVKeywordProcessor(): 初始化方法, 传入关键字映射表, 二次处理规则, 连接符, 兜底处理方法, 预处理方法
    process_csv(): 处理csv文件, 匹配关键字, 并将处理后的文本填入指定的列中, 最后写入到文件中
    """

    def __init__(self, keyword_mapping: Optional[Dict[str, str]] = None,
                 remove_rules: Optional[Dict[str, list]] = None,
                 join_separator: str = '-',
                 preprocessing: Optional[callable] = None,
                 fallback_processor: Optional[callable] = None,
                 common_tip: Optional[str] = None
                 ):
        """
        初始化CSV关键字处理器

        :param keyword_mapping: 关键字映射关系，键为关键字（支持正则表达式），值为映射结果
        :param remove_rules: 二次处理规则，键为类别名，值为删除规则列表
                            每个元素都可以是正则表达式, query作用后删除民众的部分,剩余部分拼接到类别中, 使用 join_separator 进行连接
        :param join_separator: 连接符，默认为'-'
        :param fallback_processor: 兜底处理方法，接收query参数，返回处理结果tuple[str,str],第一个str表示category,第二个str表示slot
                                   主要用于query可能不合理的情况, 兜底处理, 第一个category返回非空时才有效
        :param preprocessing: 预处理方法，接收query参数，返回处理最终的query结果
                              主要用于query可能不合理的情况, 预先进行数据清洗
                              比如: 去除空格, 去除特殊字符, 去除标点符号, 去除敏感词等
        :param common_tip: 公共提示语, 若类型文本中不包含该提示语, 会追加到结尾
        """
        if keyword_mapping is None:
            # 默认关键字映射关系
            self.keyword_mapping = {'周杰伦': '明星'}
        else:
            self.keyword_mapping = keyword_mapping

        self.preprocessing = preprocessing  # 预处理方法
        self.fallback_processor = fallback_processor  # 兜底处理方法

        # 二次处理规则
        self.secondary_processing_rules = remove_rules or {}

        # 连接符
        self.join_separator = join_separator
        self.common_tip: str = common_tip  # 公共提示信息

        # 编译正则表达式模式以提高性能
        self.compiled_patterns = {}
        for pattern, result in self.keyword_mapping.items():
            try:
                self.compiled_patterns[re.compile(pattern)] = result
            except re.error:
                # 如果不是有效的正则表达式，则当作普通字符串处理
                self.compiled_patterns[re.compile(re.escape(pattern))] = result

        # 编译二次处理规则
        self.compiled_secondary_patterns = {}
        for category, rules in self.secondary_processing_rules.items():
            self.compiled_secondary_patterns[category] = []
            for rule in rules:
                try:
                    self.compiled_secondary_patterns[category].append(re.compile(rule))
                except re.error:
                    # 如果不是有效的正则表达式，则当作普通字符串处理
                    self.compiled_secondary_patterns[category].append(re.compile(re.escape(rule)))

    def match_keyword(self, text: str) -> Optional[str]:
        """
        检查文本是否匹配任何关键字，并返回对应的映射结果

        :param text: 要检查的文本
        :return: 匹配的关键字对应的映射结果，如果没有匹配则返回None
        """
        if not text:
            return None

        for pattern, result in self.compiled_patterns.items():
            if pattern.search(text):
                return result
        return None

    def apply_secondary_processing(self, text: str, category: str, slot: Optional[str] = None) -> str:
        """
        对匹配到的类别进行二次处理，提取关键信息并追加到类别中

        :param text: 原始文本
        :param category: 匹配到的类别
        :param slot: 匹配到的槽位信息，默认为None, 若非None,则直接拼接返回最终结果
        :return: 处理后的类别
        """
        if slot:
            return f"{category}{self.join_separator}{slot}"

        # 如果没有为该类别定义二次处理规则，则直接返回原类别
        if category not in self.compiled_secondary_patterns:
            return category

        # 获取该类别的二次处理规则
        rules = self.compiled_secondary_patterns[category]

        # 应用每个规则
        slot = text
        for pattern in rules:
            # 删除匹配到的部分
            slot = pattern.sub('', slot)

        # 去除首尾空格
        slot = slot.strip()

        # 如果处理后的文本为空，则直接返回原类别
        if not slot:
            return category

        # 将处理后的文本追加到类别中
        return f"{category}{self.join_separator}{slot}"

    def process_with_fallback(self, query: str) -> Optional[Tuple[str, str]]:
        """
        使用兜底处理方法处理query

        :param query: 查询文本
        :return: 处理结果
        """
        if self.fallback_processor and callable(self.fallback_processor):
            try:
                return self.fallback_processor(query)
            except Exception as e:
                print(f"兜底处理方法执行出错: {e}")
                return None
        return None

    def process_csv(self,
                    input_file: str,
                    output_file: Optional[str] = None,
                    query_column: str = 'query',
                    result_column: str = 'result',
                    category_limit: Optional[int] = None,
                    input_file_encoding: Optional[str] = None,
                    deduplicate: bool = False) -> str:
        """
        处理CSV文件，根据关键字映射关系填充结果列

        :param input_file: 输入CSV文件路径
        :param output_file: 输出CSV文件路径，如果为None且与输入文件路径相同则覆盖原文件
        :param query_column: 包含查询文本的列名，默认为 'query'
        :param result_column: 结果要保存的列名，默认为 'result'
        :param category_limit: 每种类别的处理阈值，None表示不限制，默认为None
        :param input_file_encoding: 输入文件编码，传None表示使用默认为'utf-8-sig',允许修改, 输出文件固定是: utf-8-sig
        :param deduplicate: 是否需要对input_file进行去重(只对加载的数据去重, 不修改原始文件内容)
        :return: 输出文件路径
        """
        # 如果输出文件路径未指定，则与输入文件相同（将覆盖原文件）
        if output_file is None:
            output_file = input_file

        # 确保输出目录存在
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 已处理过的 query_column 数据, 用于去重(deduplicate=True时启用)
        query_history = set()

        # 读取并处理CSV文件
        input_encoding = input_file_encoding or 'utf-8-sig'
        with open(input_file, 'r', encoding=input_encoding) as infile:
            # 使用csv.reader处理文件
            reader = list(csv.reader(infile))

            if not reader:
                raise ValueError("CSV文件为空")

            # 获取表头并去除BOM字符
            header = reader[0]
            # 去除可能存在的BOM字符
            if header and len(header) > 0:
                header[0] = header[0].lstrip('\ufeff')

            # 查找query列索引
            try:
                query_index = header.index(query_column)
            except ValueError:
                # 如果没有找到精确匹配，尝试查找去除BOM后的列名
                bom_query_column = '\ufeff' + query_column
                try:
                    query_index = header.index(bom_query_column)
                    # 如果找到了带BOM的列名，更新query_column
                    query_column = bom_query_column
                except ValueError:
                    raise ValueError("未找到指定的查询列 '{}'".format(query_column))

            # 检查结果列是否存在，如果不存在则添加
            if result_column in header:
                result_index = header.index(result_column)
            else:
                header.append(result_column)
                result_index = len(header) - 1
                # 更新所有行以确保列数一致
                for i in range(1, len(reader)):
                    row = reader[i]
                    while len(row) < len(header):
                        row.append('')

            # 初始化类别计数器
            category_counts = {}

            # 处理每一行数据（跳过表头）
            for i in range(1, len(reader)):
                row = reader[i]

                # 跳过空白行
                if not row or all(cell.strip() == '' for cell in row):
                    continue

                # 获取query文本
                query_text = ''
                if len(row) > query_index:
                    query_text = row[query_index]

                # 如果要去重, 跳过已处理过的query
                if deduplicate and query_text in query_history:
                    continue

                # 如果结果列已经有值，则跳过
                if len(row) > result_index and row[result_index].strip() != '':
                    # 如果要去重,则缓存该query
                    if deduplicate:
                        query_history.add(query_text)
                    continue

                # 对query数据进行预处理
                if self.preprocessing and callable(self.preprocessing):
                    query_text = self.preprocessing(query_text)
                    row[query_index] = query_text

                # 匹配关键字并获取结果
                category: str = self.match_keyword(query_text)
                slot: str = ''

                # 如果没有匹配结果，尝试使用兜底处理方法
                if category is None and self.fallback_processor:
                    fallback_result = self.process_with_fallback(query_text)

                    # 如果没有匹配结果，跳过
                    if isinstance(fallback_result, tuple):
                        category, slot = fallback_result

                if CommonUtil.isNoneOrBlank(category):
                    continue

                # 检查类别限制
                if category_limit is not None:
                    # 获取当前类别的计数
                    count = category_counts.get(category, 0)

                    # 如果已达到限制，则跳过
                    if count >= category_limit:
                        continue

                    # 更新计数器
                    category_counts[category] = count + 1

                # 确保行有足够的列来存储结果
                while len(row) <= result_index:
                    row.append('')

                # 设置结果值
                row[result_index] = self.apply_secondary_processing(query_text, category, slot)
                if self.common_tip is not None and self.common_tip not in row[result_index]:
                    row[result_index] += self.common_tip

                # 如果要去重,则缓存该query
                if deduplicate:
                    query_history.add(query_text)

            # 写入处理后的数据到输出文件，使用Excel兼容的编码
            with open(output_file, 'w', encoding='utf-8-sig', newline='') as outfile:
                writer = csv.writer(outfile)
                writer.writerows(reader)

        return output_file


def main(keyword_mapping: dict,  # 映射关系
         input_file: str,  # csv源文件路径, 首行为列名, 必须包含 query_column
         output_file: Optional[str] = None,  # 输出文件路径,不传表示直接修改源文件
         query_column: str = 'query',  # 包含query文本的列名
         result_column: str = 'result',  # 结果要保存的列名
         category_limit: Optional[int] = None,  # 每种类别的处理阈值个数, None表示不限制
         print_result_limit: Optional[int] = None,  # 处理完成后要打印的结果数据数,None表示全部打印, 10 表示只打印前10个
         secondary_processing_rules: Optional[Dict[str, list]] = None,  # 二次处理规则
         join_separator: str = '-',  # 连接符
         input_file_encoding: Optional[str] = None,
         preprocessing: Optional[callable] = None,  # 预处理方法
         fallback_processor: Optional[callable] = None,  # 兜底处理方法
         common_tip: Optional[str] = None,
         deduplicate: bool = False
         ) -> str:
    """
    主函数，用于处理CSV文件
    :param keyword_mapping: 关键字映射关系，键为关键字（支持正则表达式），值为映射结果
    :param input_file: 输入CSV文件路径
    :param output_file: 输出CSV文件路径，如果为None且与输入文件路径相同则覆盖原文件
    :param query_column: 包含查询文本的列名，默认为 'query'
    :param result_column: 结果要保存的列名，默认为 'result'
    :param category_limit: 每种类别的处理阈值，None表示不限制，默认为None
    :param print_result_limit: 处理完成后要打印的结果数据数,None表示全部打印, 10 表示只打印前10个
    :param secondary_processing_rules: 二次处理规则，键为类别名，值为删除规则列表
    :param join_separator: 连接符，默认为'-'
    :param input_file_encoding: 输入文件编码，传None表示使用默认为'utf-8-sig',允许修改, 输出文件固定是: utf-8-sig
    :param fallback_processor: 兜底处理方法，接收query参数，返回处理结果tuple[str,str], 第一个str是category类别信息, 第二个str是slot信息
    :param common_tip: 公用提示语, 若类型文本中不包含该提示语, 会追加到结尾
    :param deduplicate: 是否需要对input_file进行去重(只对加载的数据去重, 不修改原始文件内容)
    :return: 输出文件路径
    """
    new_output_file = None
    processor = CSVKeywordProcessor(keyword_mapping, secondary_processing_rules, join_separator, preprocessing, fallback_processor, common_tip=common_tip)
    if os.path.exists(input_file):
        try:
            new_output_file = processor.process_csv(
                input_file=input_file,
                output_file=output_file,
                query_column=query_column,
                result_column=result_column,
                category_limit=category_limit,
                input_file_encoding=input_file_encoding,
                deduplicate=deduplicate
            )
            CommonUtil.printLog("文件处理完成，结果保存在: {}".format(new_output_file))

            # 显示处理结果
            if print_result_limit is None or print_result_limit > 0:
                with open(new_output_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    print("\n处理后的CSV内容:")
                    count = 0
                    for line in lines:
                        print(f'{count} {line.strip()}')
                        count += 1
                        if print_result_limit is not None and count >= print_result_limit:
                            print('...')
                            break
        except Exception as e:
            print("处理文件时出错: {}".format(e))
    else:
        print("示例文件不存在: {}".format(input_file))
        print("请将此文件中的input_file变量修改为你的实际CSV文件路径")
    return new_output_file


if __name__ == "__main__":
    # from util.CommonUtil import CommonUtil
    # CommonUtil.exeCmd('pwd', True)
    input_file = './cache/src.csv'  # 这里的相对路径是相对于项目根目录
    output_file = './cache/out.csv'
    category_limit = 100  # 各类别数据最大条数, 超过就不再处理该列别数据
    input_file_encoding: Optional[str] = None  # 源csv文件编码, None表示使用默认的utf-8-sig,若是其他编码,请传入正确值

    # 定义关键字映射关系
    keyword_mapping = {
        '周杰伦|周传雄|周华健': '明星',
        '周口|周一': '其他'
    }

    # 定义二次处理规则
    secondary_processing_rules = {
        '明星': [r'(?:搜索|查找)'],
    }

    main(keyword_mapping, input_file, output_file,
         'query', 'result', category_limit, 10,
         secondary_processing_rules, '-', input_file_encoding)
