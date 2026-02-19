import os
import re
from typing import List, Optional, Dict, Tuple

import pandas as pd
import numpy as np
from util.CSVUtil import CSVUtil
from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

"""
依赖库: pip install pdfplumber matplotlib pillow numpy

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
    def __init__(self, csv_dir: str, delete_src_excel: bool = True, ignore_family_card: bool = False):
        """
        :param csv_dir: excel/csv文件所在目录路径, 若为空, 则表示当前py脚本所在目录
        :param delete_src_excel: excel转为csv后是否自动删除excel源文件
        :param ignore_family_card: 是否忽略亲属卡支付数据
        """
        # 微信账单的列名
        cols_str = '交易时间,交易类型,交易对方,商品,收/支,金额(元),支付方式,当前状态,交易单号,商户单号,备注'
        self.usecols = cols_str.split(',')

        if csv_dir is None:
            csv_dir = os.path.dirname(os.path.abspath(__file__))  # 当前脚本所在目录

        self.csv_dir = csv_dir
        CSVUtil.convert_dir_excels(csv_dir, delete_src_excel)  # 转换目录下所有excel文件为csv
        self.ignore_family_card = ignore_family_card
        self.unique_col = '交易单号'  # 微信和支付宝合并和去重依据的列, 确保唯一性, 如: '交易时间'  请使用二者共有的字段
        self.df_wx = None  # 微信账单合并后的总dataframe
        self.df_zfb = None  # 支付宝账单合并后的总dataframe
        self.df_all = None  # 微信 & 支付宝 账单最终合并后的总dataframe

    def merge_wx_csv(self, output_csv_name: str = 'merge_bill_wx', valid_name_pattern=r'微信支付') -> Optional[pd.DataFrame]:
        """
        :param output_csv_name: 合并微信账单后生成的csv文件名, 若传空, 则不保存成文件
        :param valid_name_pattern: 要合并的csv文件名(包含后缀)要满足的正则表达式
        """
        # 合并所有微信的账单记录
        _df_wx = CSVUtil.merge_csv_in_dir(self.csv_dir, '', self.unique_col, usecols=self.usecols, skip_rows=16, valid_name_pattern=valid_name_pattern)
        if _df_wx is None or _df_wx.empty:
            print('微信账单为空')
            return _df_wx

        _df_wx['金额(元)'] = _df_wx['金额(元)'].apply(lambda x: float(str(x).replace('¥', '').replace(',', '')))  # 去掉 ¥ 符号并转换为浮点数
        if self.ignore_family_card:
            _df_wx = _df_wx[~_df_wx['支付方式'].str.contains('亲属卡|亲情卡', na=False)]  # na=False表示将NaN值视为不包含
        if not CommonUtil.isNoneOrBlank(output_csv_name):
            CSVUtil.to_csv(_df_wx, f'{self.csv_dir}/{output_csv_name}.csv')

        if self.df_wx is not None:
            self.df_wx = pd.concat([self.df_wx, _df_wx], ignore_index=True)
            CSVUtil.deduplicate(self.df_wx, self.unique_col)
            # 按照 '交易时间' 列进行升序排序
            self.df_wx = self.df_wx.sort_values(by='交易时间', ascending=True)
        else:
            self.df_wx = _df_wx
        return _df_wx

    def merge_zfb_csv(self, output_csv_name: str = 'merge_bill_zfb', valid_name_pattern=r'支付宝') -> Optional[pd.DataFrame]:
        """
        合并支付宝对账单, 并将其列名改为与微信一致后, 保存为 merge_bill_zfb.csv
        :param output_csv_name: 合并微信账单后生成的csv文件名(不行 .csv 后缀), 若传空, 则不保存成文件
        :param valid_name_pattern: 要合并的csv文件名(包含后缀)要满足的正则表达式
        """
        # 将支付宝的列名改为跟微信一致
        rename_cols = {'交易分类': '交易类型',
                       '商品说明': '商品',
                       '金额': '金额(元)',
                       '收/付款方式': '支付方式',
                       '交易状态': '当前状态',
                       '交易订单号': '交易单号',
                       '商家订单号': '商户单号'}

        # 合并所有微信的账单记录
        _df_zfb = CSVUtil.merge_csv_in_dir(self.csv_dir, '', self.unique_col, rename_cols=rename_cols, usecols=self.usecols,
                                           skip_rows=24, valid_name_pattern=valid_name_pattern, src_encoding='GBK')
        if _df_zfb is None or _df_zfb.empty:
            print('支付宝账单为空')
            return _df_zfb

        _df_zfb['金额(元)'] = _df_zfb['金额(元)'].apply(lambda x: float(str(x).replace('¥', '').replace(',', '')))  # 去掉 ¥ 符号并转换为浮点数
        if self.ignore_family_card:
            _df_zfb = _df_zfb[~_df_zfb['支付方式'].str.contains('亲属卡|亲情卡', na=False)]  # na=False表示将NaN值视为不包含

        if not CommonUtil.isNoneOrBlank(output_csv_name):
            CSVUtil.to_csv(_df_zfb, f'{self.csv_dir}/{output_csv_name}.csv')

        if self.df_zfb is not None:
            self.df_zfb = pd.concat([self.df_zfb, _df_zfb], ignore_index=True)
            self.df_zfb = CSVUtil.deduplicate(self.df_zfb, self.unique_col)
            # 按照 '交易时间' 列进行升序排序
            self.df_zfb = self.df_zfb.sort_values(by='交易时间', ascending=True)

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
            _df_all = CSVUtil.deduplicate(_df_all, self.unique_col)
            # 按照 '交易时间' 列进行升序排序
            _df_all = _df_all.sort_values(by='交易时间', ascending=True)

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
    def analyze_by_counterparty(df: pd.DataFrame, decimals: int = 0) -> pd.DataFrame:
        """
        根据交易方名称和收支关系进行分类和统计, 汇总所有数据
        :param decimals: 金额要保留的小数位数
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

        # # 对除'交易对方' 外的各列数据进行汇总求和
        # summary = result.loc[:, result.columns != '交易对方'].sum()  # 计算除'交易对方'外其他列的和
        # summary_row = pd.DataFrame([['合计'] + summary.tolist()], columns=['交易对方'] + list(summary.index))  # 创建汇总行
        # result = pd.concat([result, summary_row], ignore_index=True)  # 将汇总行添加到原DataFrame

        result['收入'] = result['收入'].round(decimals)
        result['支出'] = result['支出'].round(decimals)
        result['净额'] = result['净额'].round(decimals)

        return result

    @staticmethod
    def query_counterparty_stats(df: pd.DataFrame, counterparty_names: List[str], decimals: int = 0) -> Dict:
        """
        查询特定交易对方的统计信息，包括年度和月度统计

        参数:
        - df: 数据框
        - counterparty_names: 交易对方名称列表, 若不确定, 可以通过 find_matching_counterparties(...) 方法正则匹配得到
        - param decimals: 金额要保留的小数位数

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
        # 处理多级列名
        yearly_stats.columns = [f"{col[1]}_{col[0]}" for col in yearly_stats.columns]  # 交换层级顺序
        # 重命名列
        yearly_stats = yearly_stats.rename(columns={
            '收入_sum': '收入金额',
            '收入_count': '收入次数',
            '支出_sum': '支出金额',
            '支出_count': '支出次数'
        })
        # 确保列重命名完成后再计算净额
        if all(col in yearly_stats.columns for col in ['收入金额', '支出金额']):
            yearly_stats['净额'] = yearly_stats['收入金额'] - yearly_stats['支出金额']
        else:
            # 如果列名不匹配，使用原始列名计算
            yearly_stats['净额'] = yearly_stats.get('收入_sum', 0) - yearly_stats.get('支出_sum', 0)
        yearly_stats = yearly_stats.reset_index()  # 将年份从索引转为列
        yearly_stats = yearly_stats.sort_values('年份', ascending=False)

        # 月度统计
        monthly_stats = party_transactions.groupby(['年份', '月份', '收/支'])['金额(元)'].agg(['sum', 'count']).unstack(fill_value=0)
        # 处理多级列名
        monthly_stats.columns = [f"{col[0]}_{col[1]}" for col in monthly_stats.columns]  # 保持原始顺序
        # 重命名列
        monthly_stats = monthly_stats.rename(columns={
            '收入_sum': '收入金额',
            '收入_count': '收入次数',
            '支出_sum': '支出金额',
            '支出_count': '支出次数'
        })
        # 确保列重命名完成后再计算净额
        if all(col in monthly_stats.columns for col in ['收入金额', '支出金额']):
            monthly_stats['净额'] = monthly_stats['收入金额'] - monthly_stats['支出金额']
        else:
            # 如果列名不匹配，使用原始列名计算
            monthly_stats['净额'] = monthly_stats.get('收入_sum', 0) - monthly_stats.get('支出_sum', 0)
        monthly_stats = monthly_stats.reset_index()  # 将年份和月份从索引转为列
        monthly_stats = monthly_stats.sort_values(['年份', '月份'], ascending=False)

        # 只保留整数, 四舍五入
        pending_cols = ['收入金额', '支出金额', '净额', 'sum_不计收支', 'sum_支出', 'sum_收入']
        for df_item in [yearly_stats, monthly_stats]:
            for col in pending_cols:
                if col in df_item.columns:
                    df_item[col] = df_item[col].round(decimals)

        return {
            '交易对方': counterparty_name,
            '总收入': income_amount.round(decimals),
            '总支出': expense_amount.round(decimals),
            '净额': (income_amount - expense_amount).round(decimals),
            '交易次数': transaction_count,
            '年度统计': yearly_stats,
            '月度统计': monthly_stats,
            '详细记录': party_transactions
        }

    @staticmethod
    def analyze_overall_by_time(df: pd.DataFrame, decimals: int = 0) -> Dict[str, pd.DataFrame]:
        """
        统计整个数据集的总体收支情况，按年和按月进行汇总
        :param df: 数据源
        :param decimals: 总收入/总支出/总净额 要保留几位小数,默认只保留整数
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

        # 对除'年份' 外的各列数据进行汇总求和
        summary = yearly_stats.loc[:, yearly_stats.columns != '年份'].sum()  # 计算除'年份'外其他列的和
        summary_row = pd.DataFrame([['合计'] + summary.tolist()], columns=['年份'] + list(summary.index))  # 创建汇总行
        yearly_stats = pd.concat([yearly_stats, summary_row], ignore_index=True)  # 将汇总行添加到原DataFrame

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

        # 对除'年份'/'月份' 外的各列数据进行汇总求和
        summary = pd.DataFrame({'年份': ['合计'], '月份': ['']})  # 创建汇总行
        for col in monthly_stats.columns:
            if col not in ['年份', '月份']:  # 对除'年份'和'月份'外的列求和
                summary[col] = [monthly_stats[col].sum()]
        monthly_stats = pd.concat([monthly_stats, summary], ignore_index=True)  # 将汇总行添加到原DataFrame

        # 只保留整数, 四舍五入
        for df_item in [yearly_stats, monthly_stats]:
            df_item['总收入'] = df_item['总收入'].round(decimals)
            df_item['总支出'] = df_item['总支出'].round(decimals)
            df_item['总净额'] = df_item['总净额'].round(decimals)

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

    @staticmethod
    def visualize_crop_area(pdf_path, crop_box=(0, 150, 0, 0), save_img_path="crop_preview.png", resolution=150):
        """
        可视化PDF裁剪区域（精准调整裁剪参数）
        1. 生成第一页的截图，标注所有文本的坐标
        2. 绘制裁剪区域的红色边框，直观展示裁剪范围
        3. 保存预览图到本地，可根据预览图调整裁剪参数
        打开生成的 crop_preview.png，你会看到：
        🟥 红色半透明区域：当前裁剪范围
        🟨 黄色标注框：关键文本（日期 / 金额）的坐标
        📝 预览图标题：当前裁剪参数
        📜 控制台：裁剪后的文本预览（能看到是否只保留了表格）
        :param pdf_path: 招行流水PDF路径
        :param crop_box: 待测试的裁剪参数 (left, top, right, bottom)
                         对于right和bottom尺寸, 若小于0, 则表示以页面边界内缩指定尺寸
        :param save_img_path: 预览图保存路径
        :param resolution: 预览图分辨率（dpi），不影响裁剪精度
        """
        import pdfplumber
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        import matplotlib.font_manager as fm
        from PIL import Image

        # 方案A：使用系统自带的中文字体（无需额外安装）
        font_path = CommonUtil.find_system_chinese_font()
        font_prop = None
        if font_path:
            font_prop = fm.FontProperties(fname=font_path)
            plt.rcParams['font.sans-serif'] = [font_prop.get_name()]

        # 解决负号显示问题
        plt.rcParams['axes.unicode_minus'] = False

        # 1. 打开PDF并获取第一页
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]
            # PDF原始尺寸（pt）：width=页面宽度，height=页面高度
            pdf_width_pt = page.width
            pdf_height_pt = page.height

            # 补全裁剪框的right和bottom（默认用页面宽高）
            left = crop_box[0]
            top = crop_box[1]
            right = crop_box[2] if crop_box[2] > 0 else page.width + crop_box[2]
            bottom = crop_box[3] if crop_box[3] > 0 else page.height + crop_box[3]
            # right = crop_box[2] if crop_box[2] != 0 else page.width
            # bottom = crop_box[3] if crop_box[3] != 0 else page.height - 50

            crop_box_pt = (left, top, right, bottom)

            # ========== 3. 生成预览图并计算像素/pt换算比例（核心校准） ==========
            # 生成预览图（resolution仅影响图片清晰度，不影响坐标）
            img = page.to_image(resolution=resolution)
            img_array = np.array(img.original)
            # 预览图像素尺寸
            img_width_px = img_array.shape[1]
            img_height_px = img_array.shape[0]
            # 计算换算比例：1pt = 多少px
            px_per_pt_x = img_width_px / pdf_width_pt
            px_per_pt_y = img_height_px / pdf_height_pt

            # ========== 4. 将PDF裁剪坐标（pt）换算为预览图坐标（px） ==========
            crop_box_px = (
                crop_box_pt[0] * px_per_pt_x,  # left (px)
                crop_box_pt[1] * px_per_pt_y,  # top (px)
                crop_box_pt[2] * px_per_pt_x,  # right (px)
                crop_box_pt[3] * px_per_pt_y  # bottom (px)
            )

            # ========== 5. 绘制预览图（精准对齐） ==========
            fig, ax = plt.subplots(1, figsize=(15, 10))
            ax.imshow(img_array)

            # 绘制裁剪区域（红色边框，半透明）
            rect = patches.Rectangle(
                (crop_box_px[0], crop_box_px[1]),  # 左上角（px）
                crop_box_px[2] - crop_box_px[0],  # 宽度（px）
                crop_box_px[3] - crop_box_px[1],  # 高度（px）
                linewidth=3,
                edgecolor='red',
                facecolor='red',
                alpha=0.2
            )
            ax.add_patch(rect)

            # ========== 6. 标注关键文本（PDF原始坐标+预览图像素坐标） ==========
            for word in page.extract_words():
                if any(key in word['text'] for key in ['Date', 'Balance', 'Party']):
                    # 文本的PDF坐标（pt）→ 预览图坐标（px）
                    word_x_px = word['x0'] * px_per_pt_x
                    word_y_px = word['top'] * px_per_pt_y
                    # 标注文本（同时显示PDF原始坐标和预览图像素坐标）
                    ax.text(
                        word_x_px, word_y_px,
                        f"{word['text']}\nPDF坐标：({word['x0']:.0f},{word['top']:.0f}pt)\n像素坐标：({word_x_px:.0f},{word_y_px:.0f}px)",
                        fontsize=8,
                        color='blue',
                        bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.7),
                        fontproperties=font_prop
                    )

            # ========== 7. 保存预览图 + 打印关键信息 ==========
            ax.axis('off')
            plt.title(
                f"PDF Crop Preview (分辨率={resolution}dpi | 裁剪框PDF坐标：{crop_box_pt})",
                fontsize=14,
                fontproperties=font_prop
            )
            plt.tight_layout()
            plt.savefig(save_img_path, dpi=resolution, bbox_inches='tight')
            plt.close()

            # 打印校准信息
            print("=" * 60)
            print(f"✅ 精准预览图已保存：{save_img_path}")
            print(f"📏 PDF原始尺寸：{pdf_width_pt:.0f}pt × {pdf_height_pt:.0f}pt")
            print(f"🖼️ 预览图尺寸：{img_width_px}px × {img_height_px}px")
            print(f"🔍 换算比例：1pt = {px_per_pt_x:.4f}px（水平） | 1pt = {px_per_pt_y:.4f}px（垂直）")
            print(f"🎯 实际裁剪参数（PDF坐标）：left={crop_box_pt[0]}pt, top={crop_box_pt[1]}pt, right={crop_box_pt[2]}pt, bottom={crop_box_pt[3]}pt")
            print("=" * 60)

            # 验证：打印裁剪后的文本（实际裁剪结果）
            cropped_page = page.crop(crop_box_pt)
            cropped_text = cropped_page.extract_text()[:500]
            print("\n📝 实际裁剪后的文本预览（前500字符）：")
            print("-" * 50)
            print(cropped_text if cropped_text else "无文本")
            print("-" * 50)

    @staticmethod
    def cmb_pdf_to_csv(pdf_path, csv_path: Optional[str] = None, crop_box: Tuple[int] = (0, 0, 0, 0)):
        """
        纯Python适配招行无框线流水PDF转CSV（英文列名）
        :param pdf_path: 招行PDF流水路径
        :param csv_path: 输出CSV路径, 非空时有效
        :param crop_box: 首页pdf的裁剪区域,格式:left top right bottom, 只识别裁剪区域内的信息
                         其中: 对于right和bottom尺寸, 若小于0, 则表示以页面边界内缩指定尺寸
        """
        if not CommonUtil.is_library_installed('pdfplumber'):
            CommonUtil.printLog(f'cmb_pdf_to_csv fail, please do: pip install pdfplumber')
            return None

        import pdfplumber
        all_data = []
        # 🌟 按要求修改的表头（含空格的英文命名）
        header = [
            "Date",  # 记账日期
            "Currency",  # 货币
            "Transaction Amount",  # 交易金额
            "Balance",  # 联机余额
            "Transaction Type",  # 交易摘要
            "Counter Party"  # 对手信息
        ]

        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                # ========== 核心：第一页裁剪（避开标题/账户信息干扰） ==========
                if page_idx == 0:
                    left = crop_box[0]
                    top = crop_box[1]
                    right = crop_box[2] if crop_box[2] > 0 else page.width + crop_box[2]
                    bottom = crop_box[3] if crop_box[3] > 0 else page.height + crop_box[3]

                    # 裁剪参数可根据你的PDF微调：(左, 上, 右, 下)
                    page = page.crop((left, top, right, bottom))

                # ========== 无框线表格精准识别 ==========
                table = page.extract_table(table_settings={
                    "vertical_strategy": "text",  # 按文本对齐识别列
                    "horizontal_strategy": "text",  # 按文本行间距识别行
                    "text_y_tolerance": 2,  # 缩小垂直容忍度，避免行合并
                    "text_x_tolerance": 4,  # 按文本水平间隔识别列
                    "intersection_tolerance": 5,  # 放宽交叉点容忍度
                    "min_words_vertical": 2,  # 垂直方向最小有效词数	判定「一列有效」的最小文本数量→ 只有当一列中至少包含 N 个有效文本（非空 / 非空
                    "min_words_horizontal": 3  # 水平方向最小有效词数
                })

                if table:
                    for row in table:
                        # 清洗空值和空格
                        cleaned_row = [cell.strip() if cell and cell.strip() else "" for cell in row]
                        # 过滤无效行（至少3个有效字段+非表头）
                        if len([c for c in cleaned_row if c]) >= 3 and cleaned_row != header:
                            all_data.append(cleaned_row)

        # ========== 数据清洗与CSV导出 ==========
        # 在创建DataFrame之前添加数据验证
        if all_data:
            # 获取实际数据的列数
            actual_cols = len(all_data[0])
            print(f"实际提取的列数: {actual_cols}: {all_data[0]}")

            # 如果实际列数与header不匹配，调整header
            if actual_cols != len(header):
                # 根据实际列数调整header
                if actual_cols > len(header):
                    # 如果实际列数更多，添加额外的列名
                    header.extend([f"Extra_{i}" for i in range(actual_cols - len(header))])
                else:
                    # 如果实际列数更少，截取相应数量的header
                    header = header[:actual_cols]

            # 用指定表头创建DataFrame
            df = pd.DataFrame(all_data, columns=header)

            # 金额字段转为数值型（适配Pandas统计）
            for col in ["Transaction Amount", "Balance"]:
                df[col] = df[col].astype(str).str.replace(",", "").str.strip()
                df[col] = pd.to_numeric(df[col], errors="coerce")

            # 日期字段标准化为datetime格式
            # 日期字段标准化为datetime格式
            # 尝试常见的日期格式
            date_formats = [
                '%Y-%m-%d',  # 2023-12-25
                '%Y/%m/%d',  # 2023/12/25
                '%Y%m%d',  # 20231225
                '%d-%m-%Y',  # 25-12-2023
                '%d/%m/%Y',  # 25/12/2023
                '%Y年%m月%d日',  # 2023年12月25日
            ]

            # 尝试不同的日期格式
            for fmt in date_formats:
                try:
                    df["Date"] = pd.to_datetime(df["Date"], format=fmt, errors='raise')
                    break  # 如果成功解析，跳出循环
                except:
                    continue  # 如果失败，尝试下一个格式
            else:
                # 如果所有格式都失败，使用原始方法
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

            # 过滤全空行
            df = df.dropna(how="all")

            # 保存CSV（UTF-8编码避免乱码）
            CSVUtil.to_csv(df, csv_path)
            print(f"✅ 转换完成！CSV已保存到：{csv_path}")
            return df
        else:
            print("❌ 未解析到有效表格数据，请检查PDF格式")
            return None


def main():
    target_csv_dir = os.path.dirname(os.path.abspath(__file__))  # 当前脚本所在目录
    # target_csv_dir = './cache/wechat_zfb_bill'  # csv所在目录

    target_csv_dir = CommonUtil.get_input_info(f'请输入csv文件所在目录(默认{target_csv_dir}): ', target_csv_dir)
    force_merge = CommonUtil.get_input_info('是否强制重新合并所有csv文件? y/n(默认): ', 'n') == 'y'
    ignore_family_card = CommonUtil.get_input_info('是否忽略亲情卡数据? y/n(默认): ', 'n') == 'y'

    billUtil = CSVBillUtil(target_csv_dir, ignore_family_card=ignore_family_card)
    df_all = billUtil.merge_all_csv(force_merge=force_merge)
    md_stats_file = f'{billUtil.csv_dir}/bill_stats_result.md'  # 结果输出md文件路径
    backup_dir = f'{billUtil.csv_dir}/backup/'
    FileUtil.backup_file(md_stats_file, backup_dir)

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
    md_msg += f'\n> 强制重新合并={force_merge},忽略亲情卡:{ignore_family_card}\n'

    df_headN = stats_result_sorted.head(10).reset_index()
    summary = df_headN.loc[:, df_headN.columns != '交易对方'].sum()  # 计算除'交易对方'外其他列的和
    summary_row = pd.DataFrame([['合计'] + summary.tolist()], columns=['交易对方'] + list(summary.index))  # 创建汇总行
    df_headN = pd.concat([df_headN, summary_row], ignore_index=True)  # 将汇总行添加到原DataFrame
    md_msg += f'\n### 整体按支出降序排列前10项:\n{df_headN.to_markdown()}'

    # 整体按年/月统计收支情况
    overall_time_stats = CSVBillUtil.analyze_overall_by_time(df_all)
    yearly_stats = overall_time_stats['年度统计']
    md_msg += f'\n\n### 整体按年收支情况:\n{yearly_stats.to_markdown()}'
    # monthly_stats = overall_time_stats['月度统计']
    # md_msg += f'\n\n### 整体按月收支情况:\n{monthly_stats.to_markdown()}'

    # 查询指定人员的交易记录
    while True:
        name = CommonUtil.get_input_info('请输入要查询的人员姓名(正则表达式),默认不查询并退出: ', '')  # 人员姓名正则表达式, 今年匹配出可能的变体
        if CommonUtil.isNoneOrBlank(name):
            break

        names = CSVBillUtil.find_matching_counterparties(df_all, name)
        if len(names) == 0:
            print(f'未找到匹配的别名！请检查输入的姓名是否正确！')
            continue
        names_str = names[0]
        dict_special = CSVBillUtil.query_counterparty_stats(df_all, names)

        md_msg += f'\n\n## 跟 {names_str} 的交易情况:\n> 包含的别名:{"|".join(names)}\n\n'
        exclude_keys = {'详细记录', '月度统计', '年度统计'}
        # print({k: v for k, v in dict_special.items() if k not in exclude_keys})
        display_dict = {k: v for k, v in dict_special.items() if k not in exclude_keys}  # 格式化输出字典
        # md_msg += f'{json.dumps(display_dict, ensure_ascii=False, indent=2, default=str)}'

        md_msg += "| 字段 | 值 |\n"
        md_msg += "|----|----|\n"
        for k, v in display_dict.items():
            if isinstance(v, float):
                v = '{:.0f}'.format(v)
            md_msg += f"| {k} | {v} |\n"
            # md_msg += f' - {k: <4}:\t{v}\n'

        md_msg += f'\n\n### 按年度统计结果:\n{dict_special["年度统计"].to_markdown()}'
        # print(f'\n按月统计结果:\n{dict_special["月度统计"].to_string()}')
        # print(f'\n按年度计结果:\n{dict_special["年度统计"].to_string()}')

    print(f'\n\n{md_msg}')
    FileUtil.write2File(md_stats_file, md_msg)
    CommonUtil.printLog(f'以上结果已保存到 {md_stats_file}', prefix='\n')


def main2():
    CommonUtil.printLog('开始转换招商银行账单PDF为CSV...')
    target_csv_dir = os.path.dirname(os.path.abspath(__file__))  # 当前脚本所在目录
    pdf_dir = f'{target_csv_dir}/cache/wechat_zfb_bill_lynxz'
    pdf_path = f'{pdf_dir}/招商银行交易流水_20260118.pdf'

    crop_box = (0, 260, 0, -60)
    CSVBillUtil.visualize_crop_area(pdf_path, crop_box=crop_box, save_img_path=f'{pdf_dir}/crop_preview.png')

    csv_path = f'{pdf_path[:-4]}.csv'
    df = CSVBillUtil.cmb_pdf_to_csv(pdf_path, csv_path)
    # CSVUtil.to_csv(df, csv_path)
    # 验证：Pandas统计示例
    if df is not None:
        CommonUtil.printLog("\n=== 流水统计结果 ===")
        total_income = df[df["Transaction Amount"] > 0]["Transaction Amount"].sum()  # 交易金额
        total_expense = df[df["Transaction Amount"] < 0]["Transaction Amount"].sum()
        CommonUtil.printLog(f"总收入：{total_income:.2f} 元")
        CommonUtil.printLog(f"总支出：{total_expense:.2f} 元")
        CommonUtil.printLog(f"净收支：{total_income + total_expense:.2f} 元")

        # 按日期分组统计
        daily_summary = df.groupby(df["Date"].dt.date)["Transaction Amount"].sum()
        print("\nDaily Transaction Summary:")
        print(daily_summary)
    else:
        CommonUtil.printLog("没有找到有效的流水数据")


if __name__ == '__main__':
    main()
    # main2()
