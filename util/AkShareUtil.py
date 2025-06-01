# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os
import datetime

import akshare as ak
import pandas as pd

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil
from util.TimeUtil import TimeUtil, log_time_consume

"""
akshare 工具类
pip install akshare pandas openpyxl --upgrade
文档: https://akshare.akfamily.xyz/data/stock/stock.html#id27
"""


class AkShareUtil:
    stock_zh_a_code_name_df: pd.DataFrame = None  # A股股票代码和名称的缓存
    trade_days_df: pd.DataFrame = None  # 交易日历数据, 包含所有交易日信息, 用于判断是否交易日
    cache_dir: str = '.'  # 缓存目录, 默认为当前目录, 会存储请求的都得所有股票名称和代码数据信息
    stock_summary_dict: dict = {}  # 获取过的股票摘要信息, 接口: get_stock_summary()

    @staticmethod
    @log_time_consume()
    def get_stock_name(code: str) -> str:
        """
        沪深京 A 股股票代码和股票简称数据
        自测耗时14s左右, 是个dataframe, 包含两列数据, 名称依次是: code  name
        :param code: 股票代码
        :return 股票名称, 若未找到, 则返回''
        """
        df: pd.DataFrame = AkShareUtil.stock_zh_a_code_name_df
        file_path = f'{AkShareUtil.cache_dir}/stock_zh_a_code_name.csv'
        file_path = FileUtil.recookPath(file_path)
        if df is None:
            if FileUtil.isFileExist(file_path):
                df = pd.read_csv(file_path, dtype={'code': str})

        result = pd.Series() if df is None else df.query(f"code == '{code}'")['name']
        stock_name: str = '' if result.empty else result.values[0]

        if CommonUtil.isNoneOrBlank(stock_name):  # 未找到名称,则从网络获取
            print(f'invoke stock_info_a_code_name from net')
            df = ak.stock_info_a_code_name()
            df['code'].astype(str)
            df.to_csv(file_path)

            result = pd.Series() if df is None else df.query(f"code == '{code}'")['name']
            stock_name: str = '' if result.empty else result.values[0]

        AkShareUtil.stock_zh_a_code_name_df = df
        return stock_name

    @staticmethod
    @log_time_consume()
    def get_stock_summary(code: str) -> pd.DataFrame:
        """
        沪深京 A 股股票代码和股票简称数据, 比如 涨跌停价, 所属收益, 交易所等
        获取属性值的操作如下, 比如涨停价:
          price:float = df[df['item'] == '涨停']['value'].iloc[0]}
        支持的字段: '涨停'/'跌停'/'昨收'/'今开'/'名称'/'交易所' 等
        :param code: 股票代码
        """
        if code in AkShareUtil.stock_summary_dict:
            return AkShareUtil.stock_summary_dict[code]

        df = ak.stock_individual_spot_xq(symbol=f'{AkShareUtil.get_full_stock_code(code)}')
        AkShareUtil.stock_summary_dict[code] = df
        return df

    @staticmethod
    def get_latest_price(code: str, hk: bool = False, n_day_ago: int = 0, period: int = 1) -> float:
        """
        获取指定股票的最新价格(支持A股和港股)
        :param code: 股票代码
        :param hk: 是否为港股, 默认False表示A股
        :param n_day_ago: 获取往前推多少天的数据, 0表示当天  1表示前一天  -1 表示后一天
        :param period: 分时间隔, 默认为1分钟, 支持 1, 5, 15, 30, 60 分钟的数据频率
        :return: 最新价格, 若指定日期吴交易数据, 则返回0
        """
        if hk:
            stock_min_df = AkShareUtil.query_stock_min_history_hk(code, n_day_ago, period)
        else:
            stock_min_df = AkShareUtil.query_stock_min_history(code, n_day_ago, period)
        if not stock_min_df.empty:
            latest_data = stock_min_df.iloc[-1:]  # 最新1min的数据, 包含开盘价,收盘价,最高价,最低价,成交量,成交额等信息
            latest_price: float = latest_data['收盘'].iloc[-1]  # 最新价格
            return latest_price
        return 0.0

    # @staticmethod
    # def get_latest_price_hk(code: str, n_day_ago: int = 0, period: int = 1) -> float:
    #     """
    #     获取港股指定股票的最新价格
    #     文档: https://akshare.akfamily.xyz/data/stock/stock.html#id65
    #     :param code: 港股股票代码
    #     :param n_day_ago: 获取往前推多少天的数据, 0表示当天  1表示前一天  -1 表示后一天
    #     :param period: 分时间隔, 默认为1分钟, 支持 1, 5, 15, 30, 60 分钟的数据频率
    #     :return: 最新价格, 若指定日期吴交易数据, 则返回0
    #     """
    #     stock_min_df = ak.stock_hk_hist_min_em(symbol=code)
    #     if not stock_min_df.empty:
    #         latest_data = stock_min_df.iloc[-1:]  # 最新1min的数据, 包含开盘价,收盘价,最高价,最低价,成交量,成交额等信息
    #         latest_price: float = latest_data['收盘'].iloc[-1]  # 最新价格
    #         return latest_price
    #     return 0.0

    @staticmethod
    # @log_time_consume()
    def query_stock_min_history(code: str, n_day_ago: int = 0, period: int = 1) -> pd.DataFrame:
        """
        使用akshare获取指定日期的股票分时信息
        东方财富网-行情首页-沪深京 A 股-每日分时行情; 该接口只能获取近期的分时数据
        文档: https://akshare.akfamily.xyz/data/stock/stock.html#id27
        获取分时数据有两个接口:
        新浪接口: stock_zh_a_minute
                period参数表示频率,目前可以获取 1, 5, 15, 30, 60 分钟的数据频率, 可以指定是否复权
                adjust  默认为空:返回不复权的数据   qfq:返回前复权后的数据   hfq:返回后复权后的数据
        东方财富接口: stock_zh_a_hist_min_em  注意:  1 分钟数据只返回近 5 个交易日数据且不复权

        获取后通过读取最新价格操作:
        if not stock_min_df.empty:
            latest_data = stock_min_df.iloc[-1:] # 最新1min的数据, 包含开盘价,收盘价,最高价,最低价,成交量,成交额等信息
            latest_data['收盘'].iloc[-1] # 最新价格

        :param code: 股票代码
        :param n_day_ago: 获取往前推多少天的数据, 0表示当天  1表示前一天  -1 表示后一天
        :param period: 分时间隔, 默认为1分钟, 支持 1, 5, 15, 30, 60 分钟的数据频率
        """
        # stock_min_df = ak.stock_zh_a_minute(symbol=code, period="1", adjust="qfq") # 新浪接口
        date = TimeUtil.getTimeStr('%Y%m%d', n_day_ago)
        stock_min_df = ak.stock_zh_a_hist_min_em(symbol=code, period=f'{period}', adjust="qfq", start_date=date,
                                                 end_date=date)  # 东财接口
        return stock_min_df

    @staticmethod
    # @log_time_consume()
    def query_stock_min_history_hk(code: str, n_day_ago: int = 0, period: int = 1) -> pd.DataFrame:
        """
        使用akshare获取指定日期的股票分时信息(港股)
        接口: stock_hk_hist_min_em
        目标地址: http://quote.eastmoney.com/hk/00948.html
        描述: 东方财富网-行情首页-港股-每日分时行情
        限量: 单次返回指定上市公司最近 5 个交易日分钟数据, 注意港股有延时

        symbol	str	symbol="01611"; 港股代码可以通过 ak.stock_hk_spot_em() 函数返回所有的 pandas.DataFrame 里面的 代码 字段获取
        period	str	period='5'; choice of {'1', '5', '15', '30', '60'}; 其中 1 分钟数据返回近 5 个交易日数据且不复权
        adjust	str	adjust=''; choice of {'', 'qfq', 'hfq'}; '': 不复权, 'qfq': 前复权, 'hfq': 后复权, 其中 1 分钟数据返回近 5 个交易日数据且不复权
        start_date	str	start_date="1979-09-01 09:32:00"; 日期时间; 默认返回所有数据
        end_date	str	end_date="2222-01-01 09:32:00"; 日期时间; 默认返回所有数据

        输出结果:
        名称	类型	描述
        时间	object	-
        开盘	float64	注意单位: 港元
        收盘	float64	注意单位: 港元
        最高	float64	注意单位: 港元
        最低	float64	注意单位: 港元
        成交量	float64	注意单位: 股
        成交额	float64	注意单位: 港元
        最新价	float64	注意单位: 港元

        获取后通过读取最新价格操作:
        if not stock_min_df.empty:
            latest_data = stock_min_df.iloc[-1:] # 最新1min的数据, 包含开盘价,收盘价,最高价,最低价,成交量,成交额等信息
            latest_data['收盘'].iloc[-1] # 最新价格

        :param code: 股票代码
        :param n_day_ago: 获取往前推多少天的数据, 0表示当天  1表示前一天  -1 表示后一天
        :param period: 分时间隔, 默认为1分钟, 支持 1, 5, 15, 30, 60 分钟的数据频率
        """
        date = TimeUtil.getTimeStr('%Y%m%d', n_day_ago)
        stock_min_df = ak.stock_hk_hist_min_em(symbol=code, period=f'{period}', adjust="qfq",
                                               start_date=f'{date} 09:00:00',
                                               end_date=f'{date} 18:00:00')
        return stock_min_df

    @staticmethod
    def get_full_stock_code(stock_code: str) -> str:
        """
        根据股票代码生成带交易所前缀的完整代码（如 SZ000001、SH600519、BJ8开头）

        参数:
            stock_code (str): 6位数字股票代码（如 '000001'）

        返回:
            str: 带前缀的完整代码（如 'SZ000001'）

        异常:
            ValueError: 代码格式错误或类型未知时抛出
        """
        if len(stock_code) == 8:
            CommonUtil.printLog(f'generate_full_stock_code(${stock_code}) 已是8位,无需处理')
            return stock_code

        # 1. 校验代码格式（必须为6位纯数字）
        if len(stock_code) != 6 or not stock_code.isdigit():
            raise ValueError("股票代码必须为6位纯数字！例如：'000001'")

        # 2. 提取代码前缀（前两位或第一位，针对北交所）
        first_two = stock_code[:2]
        first_char = stock_code[0]

        # 3. 判断交易所并拼接前缀
        if first_two in ['60', '68']:  # 沪市主板（60开头）、科创板（68开头）
            return f"SH{stock_code}"
        elif first_two in ['00', '30']:  # 深市主板（00开头）、创业板（30开头）
            return f"SZ{stock_code}"
        elif first_char == '8' or first_two in ['92']:  # 北交所（8开头）
            return f"BJ{stock_code}"
        else:
            raise ValueError(f"未知的股票代码类型：{stock_code} "
                             "（目前支持沪市、深市、北交所，其他市场需手动处理）")

    @staticmethod
    def is_today_can_trade(refresh_days=7) -> bool:
        """
        判断今天是否可以交易
        接口: tool_trade_date_hist_sina
        目标地址: https://finance.sina.com.cn
        文档: https://akshare.akfamily.xyz/data/tool/tool.html#id1
        描述: 新浪财经-股票交易日历数据
        限量: 单次返回从 1990-12-19 到 2024-12-31 之间的股票交易日历数据, 这里补充 1992-05-04 进入交易日
        :param refresh_days: 缓存刷新间隔（天）
        """
        df: pd.DataFrame = AkShareUtil.trade_days_df
        file_path = f'{AkShareUtil.cache_dir}/stock_zh_a_trade_days.csv'
        file_path = FileUtil.recookPath(file_path)
        today = datetime.date.today()  # 今日日期
        need_refresh: bool = False  # 是否需要刷新本地数据, 从网络上获取
        if df is None:
            if FileUtil.isFileExist(file_path):
                modified_time = datetime.date.fromtimestamp(os.path.getmtime(file_path))
                if (today - modified_time).days < refresh_days:
                    df = pd.read_csv(file_path, parse_dates=['trade_date'])
                    df['trade_date'] = df['trade_date'].dt.date  # 转换为date类型
                    # 若今日日期大于最后一天日期, 则说明本地缓存的记录过期了, 需要重新获取
                    need_refresh = today > df['trade_date'].max()
                else:
                    need_refresh = True
            else:
                need_refresh = True
        if need_refresh:
            print(f'invoke tool_trade_date_hist_sina from net')
            df = ak.tool_trade_date_hist_sina()
            df.to_csv(file_path)

        AkShareUtil.trade_days_df = df

        if today in df['trade_date'].values:
            return True
        else:
            return False
