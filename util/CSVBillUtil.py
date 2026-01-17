import os
import pandas as pd
from typing import List, Optional, Dict
from util.CSVUtil import CSVUtil
from util.CommonUtil import CommonUtil

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

支付宝账单列名(“支付宝 - 我的 - 账单 - 右上角... - 开具交易流水证明"):
交易时间,交易分类,交易对方,对方账号,商品说明,收/支,金额,    收/付款方式,交易状态,交易订单号,商家订单号,备注,
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

    def merge_all_csv(self, df_list: Optional[List[pd.DataFrame]] = None, output_csv_name: str = 'merge_bill_all') -> pd.DataFrame:
        """
        :param df_list: 待合并的list列表, 若传空,默认合并的是 self.df_wx  和  self.df_zfb
        :param output_csv_name: 合并微信账单后生成的csv文件名, 若传空, 则不保存成文件
        """
        if CommonUtil.isNoneOrBlank(df_list):
            if self.df_wx is None:
                self.merge_wx_csv()
            if self.df_zfb is None:
                self.merge_zfb_csv()

            df_list = [self.df_wx, self.df_zfb]

        df_list = [x for x in df_list if not CommonUtil.isNoneOrBlank(x)]
        if CommonUtil.isNoneOrBlank(df_list):
            _df_all = pd.DataFrame()
        else:
            # 合并微信和支付宝数据, 得到总支出表
            _df_all = pd.concat(df_list, ignore_index=True)
            _df_all['金额(元)'] = _df_all['金额(元)'].apply(lambda x: float(str(x).replace('¥', '').replace(',', '')))  # 去掉 ¥ 符号并转换为浮点数
            _df_all = CSVUtil.deduplicate_dataframe(_df_all, self.unique_col)
            if not CommonUtil.isNoneOrBlank(output_csv_name):
                CSVUtil.to_csv(_df_all, f'{self.csv_dir}/{output_csv_name}.csv', index=False)
        self.df_all = _df_all
        return self.df_all

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
        result = result.sort_values('支出', ascending=False)
        return result

    @staticmethod
    def query_counterparty_stats(df: pd.DataFrame, counterparty_names: List[str]) -> Dict:
        """
        查询特定交易对方的统计信息

        参数:
        - df: 数据框
        - counterparty_name: 交易对方名称

        返回:
        - 统计信息字典
        """
        counterparty_name = counterparty_names[0]
        party_transactions = df[df['交易对方'].isin(counterparty_names)]

        if party_transactions.empty:
            return {"message": f"未找到与 {counterparty_name} 的交易记录"}

        income_amount = party_transactions[party_transactions['收/支'] == '收入']['金额(元)'].sum()
        expense_amount = party_transactions[party_transactions['收/支'] == '支出']['金额(元)'].sum()
        transaction_count = len(party_transactions)

        return {
            '交易对方': counterparty_name,
            '总收入': income_amount,
            '总支出': expense_amount,
            '净额': income_amount - expense_amount,
            '交易次数': transaction_count,
            '详细记录': party_transactions  # 可以返回详细交易记录
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
    target_csv_dir = './cache/wechat_zfb_bill'  # csv所在目录
    billUtil = CSVBillUtil(target_csv_dir)
    df_all = billUtil.merge_all_csv()

    stats_result = CSVBillUtil.analyze_by_counterparty(df_all)
    # print("\n简化版本统计结果:")
    # print(stats_result.head(10))  # 显示前10个

    stats_result_sorted = stats_result.sort_values('支出', ascending=False)  # 降序排列
    print("\n按支出降序排列:")
    print(stats_result_sorted.head(10))

    # 查询指定人员的交易记录
    name = '小佛爷'
    dict_special = CSVBillUtil.query_counterparty_stats(df_all, [name, '巧虹(**虹)'])

    print(f'\n跟 {name} 的交易情况:')
    exclude_keys = {'详细记录'}  # 用 set 提升查找效率
    print({k: v for k, v in dict_special.items() if k not in exclude_keys})
