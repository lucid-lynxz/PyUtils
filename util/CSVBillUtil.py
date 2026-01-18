import os
import re
from typing import List, Optional, Dict

import pandas as pd

from util.CSVUtil import CSVUtil
from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

"""
合并当前目录下除 output_name 以及 'ignore_' 开头的所有 csv 文件, 并去重, 保存为 output_name
要读取和保存的列名为由 usecols 定义, 请确保这些列名存在
最后会新增一列: result_src 用以记录当前数据来源于哪份文档
其他变量含义说明: 
 skip_rows: 指定要跳过的表头行数
 deduplicate_on_column: 去重数据时的列依据 
 output_dir: 要合并的csv文件所在的目录, 默认是当前脚本所在目录
 output_csv_name: 最终合并生成的csv文件名(不包含 .csv 后缀)

对于微信对账单excel文件, 会先转化为csv, 然后合并csv(基于时间去重)
微信对账单前16行为统计信息表头, 需要跳过
微信对账单的详情列名为("微信 - 我 - 服务 - 钱包 - 账单 - 右上角... - 下载账单 - 用于个人对账"):
交易时间,交易类型,交易对方,商品,收/支,金额(元),支付方式,当前状态,交易单号,商户单号,备注
微信单次申请的时长跨度是3个月, 每次都需要进行人脸验证, 若下面则发送到邮箱, 每次都要输邮箱, 最终邮件附件压缩包会带有密码

支付宝账单列名(“支付宝 - 我的 - 账单 - 右上角... - 开具交易流水证明"):
交易时间,交易分类,交易对方,对方账号,商品说明,收/支,金额,    收/付款方式,交易状态,交易订单号,商家订单号,备注,
支付宝单次申请的时长跨度是1年

招商银行列名("首页 - 收支明细 -右上角... - 打印流水"):
记账日期,货币,交易金额,联机余额,交易摘要,对手信息
招商银行单次申请的时长跨度最大是10年, 单次最大导出记录是2w条, 但只支持到处pdf文件,因此本脚本未对其进行适配

使用方法:
1. 运行本脚本, 根据提示输入: 微信&支付宝导出的对账单excel文件所在目录地址 以及是否要重新合并(默认直接回车即可)
2. 根据提示输入要特别进行统计的指定交易对象名(正则表达式, 以便模糊搜索出所有别名)
3. 统计结果会输出到 {csv目录}/bill_stats_result.md 文件中, 主要包含以下内容:
    3.1 整体按支出降序排列前10项
    3.2 整体按年收支情况
    3.3 特定交易对象的整体交易汇总以及按年度统计的交易记录
    
其他说明: 要特别统计的交易对象名支持配置多次, 每个都会单独进行统计
"""


class CSVBillUtil(object):
    def __init__(self, csv_dir: str, delete_src_excel: bool = True):
        """
        :param csv_dir: excel/csv文件所在目录路径, 若为空, 则表示当前py脚本所在目录
        :param delete_src_excel: excel转为csv后是否自动删除excel源文件
        """
        # 微信账单的列名
        cols_str = '交易时间,交易类型,交易对方,商品,收/支,金额(元),支付方式,当前状态,交易单号,商户单号,备注'
        self.usecols = cols_str.split(',')

        if csv_dir is None:
            csv_dir = os.path.dirname(os.path.abspath(__file__))  # 当前脚本所在目录

        self.csv_dir = csv_dir
        CSVUtil.convert_dir_excels(csv_dir, delete_src_excel)  # 转换目录下所有excel文件为csv

        self.unique_col = '交易时间'  # 微信和支付宝合并和去重依据的列, 确保唯一性, 如: '交易时间'  请使用二者共有的字段
        self.df_wx = None  # 微信账单合并后的总dataframe
        self.df_zfb = None  # 支付宝账单合并后的总dataframe
        self.df_all = None  # 微信 & 支付宝 账单最终合并后的总dataframe

    def merge_wx_csv(self, output_csv_name: str = 'merge_bill_wx', valid_name_pattern=r'微信支付') -> pd.DataFrame:
        """
        :param output_csv_name: 合并微信账单后生成的csv文件名, 若传空, 则不保存成文件
        :param valid_name_pattern: 要合并的csv文件名(包含后缀)要满足的正则表达式
        """
        # 合并所有微信的账单记录
        _df_wx = CSVUtil.merge_csv_in_dir(self.csv_dir, '', self.unique_col, usecols=self.usecols, skip_rows=16, valid_name_pattern=valid_name_pattern)
        _df_wx['金额(元)'] = _df_wx['金额(元)'].apply(lambda x: float(str(x).replace('¥', '').replace(',', '')))  # 去掉 ¥ 符号并转换为浮点数
        if not CommonUtil.isNoneOrBlank(output_csv_name):
            CSVUtil.to_csv(_df_wx, f'{self.csv_dir}/{output_csv_name}.csv')

        if self.df_wx is not None:
            self.df_wx = pd.concat([self.df_wx, _df_wx], ignore_index=True)
            CSVUtil.deduplicate_dataframe(self.df_wx, self.unique_col)
        else:
            self.df_wx = _df_wx
        return _df_wx

    def merge_zfb_csv(self, output_csv_name: str = 'merge_bill_zfb', valid_name_pattern=r'支付宝') -> pd.DataFrame:
        """
        合并支付宝对账单, 并将其列名改为与微信一致后, 保存为 merge_bill_zfb.csv
        :param output_csv_name: 合并微信账单后生成的csv文件名(不行 .csv 后缀), 若传空, 则不保存成文件
        :param valid_name_pattern: 要合并的csv文件名(包含后缀)要满足的正则表达式
        """
        # 合并所有微信的账单记录
        _df_zfb = CSVUtil.merge_csv_in_dir(self.csv_dir, '', self.unique_col, skip_rows=24, valid_name_pattern=valid_name_pattern, src_encoding='GBK')
        # 将支付宝的列名改为跟微信一致
        _df_zfb.rename(columns={'交易分类': '交易类型',
                                '商品说明': '商品',
                                '金额': '金额(元)',
                                '收/付款方式': '支付方式',
                                '交易状态': '当前状态',
                                '交易订单号': '交易单号',
                                '商家订单号': '商户单号'}, inplace=True)
        _df_zfb = CSVUtil.reorder_cols(_df_zfb, self.usecols)
        _df_zfb['金额(元)'] = _df_zfb['金额(元)'].apply(lambda x: float(str(x).replace('¥', '').replace(',', '')))  # 去掉 ¥ 符号并转换为浮点数
        if not CommonUtil.isNoneOrBlank(output_csv_name):
            CSVUtil.to_csv(_df_zfb, f'{self.csv_dir}/{output_csv_name}.csv')

        if self.df_zfb is not None:
            self.df_zfb = pd.concat([self.df_zfb, _df_zfb], ignore_index=True)
            self.df_zfb = CSVUtil.deduplicate_dataframe(self.df_zfb, self.unique_col)
        else:
            self.df_zfb = _df_zfb
        return _df_zfb

    def merge_all_csv(self, df_list: Optional[List[pd.DataFrame]] = None, output_csv_name: str = 'merge_bill_all', force_merge: bool = False) -> pd.DataFrame:
        """
        :param df_list: 待合并的list列表, 若传空,默认合并的是 self.df_wx  和  self.df_zfb
        :param output_csv_name: 合并微信账单后生成的csv文件名, 若传空, 则不保存成文件
        :param force_merge: 若 output_csv_name 文件已存在, 是否仍需要重新汇总统计
        """
        output_csv_path = f'{self.csv_dir}/{output_csv_name}.csv'
        need_save = not FileUtil.isFileExist(output_csv_path) or force_merge
        if CommonUtil.isNoneOrBlank(df_list):
            if FileUtil.isFileExist(output_csv_path) and not force_merge:
                CommonUtil.printLog(f'merge_all_csv 直接读取已汇总的数据文件: {output_csv_path}')
                df_list = [CSVUtil.read_csv(output_csv_path)]
            else:
                if self.df_wx is None:
                    self.merge_wx_csv()
                if self.df_zfb is None:
                    self.merge_zfb_csv()

                df_list = [self.df_wx, self.df_zfb]
                CommonUtil.printLog(f'merge_all_csv 合并微信和支付宝账单数据: {len(df_list)} 个')

        df_list = [x for x in df_list if not CommonUtil.isNoneOrBlank(x)]
        if CommonUtil.isNoneOrBlank(df_list):
            _df_all = pd.DataFrame()
        else:
            # 合并微信和支付宝数据, 得到总支出表
            _df_all = pd.concat(df_list, ignore_index=True)
            _df_all['金额(元)'] = _df_all['金额(元)'].apply(lambda x: float(str(x).replace('¥', '').replace(',', '')))  # 去掉 ¥ 符号并转换为浮点数
            _df_all = CSVUtil.deduplicate_dataframe(_df_all, self.unique_col)
            if not CommonUtil.isNoneOrBlank(output_csv_name) and need_save:
                CSVUtil.to_csv(_df_all, f'{self.csv_dir}/{output_csv_name}.csv', index=False)
        self.df_all = _df_all
        return self.df_all

    @staticmethod
    def find_matching_counterparties(df: pd.DataFrame, pattern: str, col: str = '交易对方') -> List[str]:
        """
        使用正则表达式匹配指定列(默认'交易对方'列)中的所有可能的名字

        参数:
        - df: 包含交易记录的数据框
        - pattern: 用于匹配的正则表达式字符串

        返回:
        - 匹配到的交易对方名称列表（去重后）
        """
        # 获取所有唯一的交易对方名称
        unique_names = df[col].unique()

        # 编译正则表达式
        regex = re.compile(pattern)

        # 找出所有匹配的名称
        matched_names = [name for name in unique_names if regex.search(name)]

        return matched_names

    @staticmethod
    def analyze_by_counterparty(df: pd.DataFrame) -> pd.DataFrame:
        """
        根据交易方名称和收支关系进行分类和统计, 汇总所有数据
        输出结果:
            交易对方: 商家或个人名称
            总收入: 从该对方获得的收入总额
            总支出: 向该对方支付的支出总额
            交易次数: 与该对方的交易总次数
            净额: 收入减去支出的余额
        """

        # 按交易对方和收支类型分组
        grouped = df.groupby(['交易对方', '收/支'])['金额(元)'].agg(['sum', 'count']).reset_index()

        # 透视表格式化
        pivot_table = grouped.pivot(index='交易对方', columns='收/支', values='sum').fillna(0)
        count_table = grouped.pivot(index='交易对方', columns='收/支', values='count').fillna(0)

        # 合并结果
        result = pd.DataFrame({
            '收入': pivot_table.get('收入', pd.Series(0, index=pivot_table.index)),
            '支出': pivot_table.get('支出', pd.Series(0, index=pivot_table.index)),
            '收入次数': count_table.get('收入', pd.Series(0, index=count_table.index)).astype(int),
            '支出次数': count_table.get('支出', pd.Series(0, index=count_table.index)).astype(int)
        }).fillna(0)

        result['净额'] = result['收入'] - result['支出']

        # 重置索引，将"交易对方"变成普通列
        result = result.reset_index()

        result = result.sort_values('支出', ascending=False)
        return result

    @staticmethod
    def query_counterparty_stats(df: pd.DataFrame, counterparty_names: List[str]) -> Dict:
        """
        查询特定交易对方的统计信息，包括年度和月度统计

        参数:
        - df: 数据框
        - counterparty_names: 交易对方名称列表, 若不确定, 可以通过 find_matching_counterparties(...) 方法正则匹配得到

        返回:
        - 包含总体、年度和月度统计信息的字典
        """
        CommonUtil.printLog(f'query_counterparty_stats 查询交易方: {counterparty_names}')
        counterparty_name = counterparty_names[0]
        party_transactions = df[df['交易对方'].isin(counterparty_names)].copy()

        if party_transactions.empty:
            return {"message": f"未找到与 {counterparty_name} 的交易记录"}

        # 提取年份和月份 - 修复日期转换警告
        try:
            party_transactions['交易时间'] = pd.to_datetime(party_transactions['交易时间'],
                                                            format='%Y-%m-%d %H:%M:%S',
                                                            errors='coerce')
            # 如果上面的格式不匹配，则尝试自动推断
            if party_transactions['交易时间'].isna().all():
                party_transactions['交易时间'] = pd.to_datetime(party_transactions['交易时间'])
        except:
            party_transactions['交易时间'] = pd.to_datetime(party_transactions['交易时间'])

        party_transactions['年份'] = party_transactions['交易时间'].dt.year
        party_transactions['月份'] = party_transactions['交易时间'].dt.month

        # 总体统计
        income_amount = party_transactions[party_transactions['收/支'] == '收入']['金额(元)'].sum()
        expense_amount = party_transactions[party_transactions['收/支'] == '支出']['金额(元)'].sum()
        transaction_count = len(party_transactions)

        # 年度统计
        yearly_stats = party_transactions.groupby(['年份', '收/支'])['金额(元)'].agg(['sum', 'count']).unstack(fill_value=0)
        # 获取实际的列数
        col_count = len(yearly_stats.columns)
        # 根据实际列数设置列名
        if col_count == 4:
            yearly_stats.columns = ['收入金额', '收入次数', '支出金额', '支出次数']
        else:
            # 如果列数不匹配，使用原始的多级列名
            yearly_stats.columns = [f"{col[0]}_{col[1]}" for col in yearly_stats.columns]

        yearly_stats = yearly_stats.reset_index()  # 将年份从索引转为列
        if '收入金额' in yearly_stats.columns and '支出金额' in yearly_stats.columns:
            yearly_stats['净额'] = yearly_stats['收入金额'] - yearly_stats['支出金额']
        else:
            yearly_stats['净额'] = yearly_stats.get('sum_收入', 0) - yearly_stats.get('sum_支出', 0)
        yearly_stats = yearly_stats.sort_values('年份', ascending=False)

        # 月度统计
        monthly_stats = party_transactions.groupby(['年份', '月份', '收/支'])['金额(元)'].agg(['sum', 'count']).unstack(fill_value=0)
        # 获取实际的列数
        col_count = len(monthly_stats.columns)
        # 根据实际列数设置列名
        if col_count == 4:
            monthly_stats.columns = ['收入金额', '收入次数', '支出金额', '支出次数']
        else:
            # 如果列数不匹配，使用原始的多级列名
            monthly_stats.columns = [f"{col[0]}_{col[1]}" for col in monthly_stats.columns]

        monthly_stats = monthly_stats.reset_index()  # 将年份和月份从索引转为列
        if '收入金额' in monthly_stats.columns and '支出金额' in monthly_stats.columns:
            monthly_stats['净额'] = monthly_stats['收入金额'] - monthly_stats['支出金额']
        else:
            monthly_stats['净额'] = monthly_stats.get('sum_收入', 0) - monthly_stats.get('sum_支出', 0)
        monthly_stats = monthly_stats.sort_values(['年份', '月份'], ascending=False)

        return {
            '交易对方': counterparty_name,
            '总收入': income_amount,
            '总支出': expense_amount,
            '净额': income_amount - expense_amount,
            '交易次数': transaction_count,
            '年度统计': yearly_stats,
            '月度统计': monthly_stats,
            '详细记录': party_transactions
        }

    @staticmethod
    def analyze_overall_by_time(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        统计整个数据集的总体收支情况，按年和按月进行汇总
        返回结果包含两个部分：
        - 年度统计: 按年份汇总的总体收支情况
        - 月度统计: 按月份汇总的总体收支情况
        """
        # 首先转换日期列，指定日期格式以避免警告
        df_with_date = df.copy()
        try:
            # 尝试常见的日期格式
            df_with_date['交易时间'] = pd.to_datetime(df_with_date['交易时间'],
                                                      format='%Y-%m-%d %H:%M:%S',
                                                      errors='coerce')
            # 如果上面的格式不匹配，则尝试自动推断
            if df_with_date['交易时间'].isna().all():
                df_with_date['交易时间'] = pd.to_datetime(df_with_date['交易时间'])
        except:
            df_with_date['交易时间'] = pd.to_datetime(df_with_date['交易时间'])

        df_with_date['年份'] = df_with_date['交易时间'].dt.year
        df_with_date['月份'] = df_with_date['交易时间'].dt.month

        # 按年份统计
        yearly_grouped = df_with_date.groupby(['年份', '收/支'])['金额(元)'].agg(['sum', 'count']).reset_index()
        yearly_pivot_sum = yearly_grouped.pivot_table(
            index='年份',
            columns='收/支',
            values='sum',
            fill_value=0
        ).fillna(0)
        yearly_pivot_count = yearly_grouped.pivot_table(
            index='年份',
            columns='收/支',
            values='count',
            fill_value=0
        ).fillna(0)

        # 合并年度统计
        yearly_stats = pd.DataFrame({
            '总收入': yearly_pivot_sum.get('收入', pd.Series(0, index=yearly_pivot_sum.index)),
            '总支出': yearly_pivot_sum.get('支出', pd.Series(0, index=yearly_pivot_sum.index)),
            '总收入次数': yearly_pivot_count.get('收入', pd.Series(0, index=yearly_pivot_count.index)).astype(int),
            '总支出次数': yearly_pivot_count.get('支出', pd.Series(0, index=yearly_pivot_count.index)).astype(int)
        }).fillna(0)
        yearly_stats['总净额'] = yearly_stats['总收入'] - yearly_stats['总支出']
        yearly_stats = yearly_stats.reset_index()
        yearly_stats = yearly_stats.sort_values('年份', ascending=False)

        # 按月份统计
        monthly_grouped = df_with_date.groupby(['年份', '月份', '收/支'])['金额(元)'].agg(['sum', 'count']).reset_index()
        monthly_pivot_sum = monthly_grouped.pivot_table(
            index=['年份', '月份'],
            columns='收/支',
            values='sum',
            fill_value=0
        ).fillna(0)
        monthly_pivot_count = monthly_grouped.pivot_table(
            index=['年份', '月份'],
            columns='收/支',
            values='count',
            fill_value=0
        ).fillna(0)

        # 合并月度统计
        monthly_stats = pd.DataFrame({
            '总收入': monthly_pivot_sum.get('收入', pd.Series(0, index=monthly_pivot_sum.index)),
            '总支出': monthly_pivot_sum.get('支出', pd.Series(0, index=monthly_pivot_sum.index)),
            '总收入次数': monthly_pivot_count.get('收入', pd.Series(0, index=monthly_pivot_count.index)).astype(int),
            '总支出次数': monthly_pivot_count.get('支出', pd.Series(0, index=monthly_pivot_count.index)).astype(int)
        }).fillna(0)
        monthly_stats['总净额'] = monthly_stats['总收入'] - monthly_stats['总支出']
        monthly_stats = monthly_stats.reset_index()
        monthly_stats = monthly_stats.sort_values(['年份', '月份'], ascending=[False, False])

        return {
            '年度统计': yearly_stats,
            '月度统计': monthly_stats
        }

    @staticmethod
    def merge_counterparty_stats(stats_list):
        """
        合并多个交易对方的统计结果,主要用于同一个人但有多个名称的场景

        参数:
        - stats_list: 包含多个统计字典的列表

        返回:
        - 合并后的统计字典
        """
        if not stats_list:
            return {}

        # 初始化合并结果
        merged = {
            '交易对方': stats_list[0]['交易对方'],  # 可以使用规范名称
            '总收入': 0,
            '总支出': 0,
            '净额': 0,
            '交易次数': 0,
            '详细记录': pd.DataFrame()  # 如果需要合并详细记录
        }

        # 遍历所有统计结果进行累加
        for stat in stats_list:
            merged['总收入'] += stat.get('总收入', 0)
            merged['总支出'] += stat.get('总支出', 0)
            merged['净额'] += stat.get('净额', 0)
            merged['交易次数'] += stat.get('交易次数', 0)

            # 如果有详细记录，合并DataFrame
            if '详细记录' in stat and not stat['详细记录'].empty:
                merged['详细记录'] = pd.concat([
                    merged['详细记录'],
                    stat['详细记录']
                ], ignore_index=True)

        return merged


if __name__ == '__main__':
    target_csv_dir = os.path.dirname(os.path.abspath(__file__))  # 当前脚本所在目录
    # target_csv_dir = './cache/wechat_zfb_bill'  # csv所在目录

    target_csv_dir = CommonUtil.get_input_info(f'请输入csv文件所在目录(默认{target_csv_dir}): ', target_csv_dir)
    force_merge = CommonUtil.get_input_info('是否强制合并所有csv文件? y/n(默认): ', 'n') == 'y'

    billUtil = CSVBillUtil(target_csv_dir)
    df_all = billUtil.merge_all_csv(force_merge=force_merge)
    md_stats_file = f'{billUtil.csv_dir}/bill_stats_result.md'  # 结果输出md文件路径

    # # 设置pandas显示选项以改善表格对齐
    # pd.set_option('display.max_columns', None)  # 显示所有列，不会出现列省略号...
    # pd.set_option('display.max_rows', None)  # 最多显示多少行行,None表示显示所有行
    # pd.set_option('display.width', None)  # 自动适配屏幕宽度，不限制总宽度
    # pd.set_option('display.max_colwidth', 30)  # 显示单元格全部内容，None表示不截断、不省略
    # pd.set_option('display.unicode.ambiguous_as_wide', True)  # 中文对齐专用：中文占2字符宽度
    # pd.set_option('display.unicode.east_asian_width', True)  # 正确处理东亚字符宽度
    # pd.set_option('display.float_format', '{:,.2f}'.format)  # 设置浮点数显示格式

    stats_result = CSVBillUtil.analyze_by_counterparty(df_all)

    stats_result_sorted = stats_result.sort_values('支出', ascending=False)  # 降序排列
    md_msg = f'## 微信&支付宝整体收支情况'
    md_msg += f'\n### 整体按支出降序排列前10项:\n{stats_result_sorted.head(10).reset_index().to_markdown()}'

    # 整体按年/月统计收支情况
    overall_time_stats = CSVBillUtil.analyze_overall_by_time(df_all)
    yearly_stats = overall_time_stats['年度统计']
    monthly_stats = overall_time_stats['月度统计']
    md_msg += f'\n\n### 整体按年收支情况:\n{yearly_stats.to_markdown()}'

    # 查询指定人员的交易记录
    while True:
        name = CommonUtil.get_input_info('请输入要查询的人员姓名(正则表达式),默认不查询并退出: ', '')  # 人员姓名正则表达式, 今年匹配出可能的变体
        if CommonUtil.isNoneOrBlank(name):
            break

        names = CSVBillUtil.find_matching_counterparties(df_all, name)
        names_str = names[0]
        dict_special = CSVBillUtil.query_counterparty_stats(df_all, names)

        md_msg += f'\n\n## 跟 {names_str} 的交易情况:\n'
        exclude_keys = {'详细记录', '月度统计', '年度统计'}
        # print({k: v for k, v in dict_special.items() if k not in exclude_keys})
        display_dict = {k: v for k, v in dict_special.items() if k not in exclude_keys}  # 格式化输出字典
        # md_msg += f'{json.dumps(display_dict, ensure_ascii=False, indent=2, default=str)}'

        md_msg += "| 字段 | 值 |\n"
        md_msg += "|----|----|\n"
        for k, v in display_dict.items():
            if isinstance(v, float):
                v = '{:.2f}'.format(v)
            md_msg += f"| {k} | {v} |\n"
            # md_msg += f' - {k: <4}:\t{v}\n'

        md_msg += f'\n\n### 按年度统计结果:\n{dict_special["年度统计"].to_markdown()}'
        # print(f'\n按月统计结果:\n{dict_special["月度统计"].to_string()}')
        # print(f'\n按年度计结果:\n{dict_special["年度统计"].to_string()}')

    print(f'\n\n{md_msg}')
    FileUtil.write2File(md_stats_file, md_msg)
    CommonUtil.printLog(f'以上结果已保存到 {md_stats_file}', prefix='\n')
