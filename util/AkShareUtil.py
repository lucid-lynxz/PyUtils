# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import datetime
import os
import traceback
from typing import Union, Optional

import akshare as ak
import pandas as pd

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil
from util.NetUtil import NetUtil
from util.TimeUtil import log_time_consume, TimeUtil

"""
akshare 工具类
pip install akshare pandas openpyxl --upgrade
文档: https://akshare.akfamily.xyz/data/stock/stock.html#id27
"""


class AkShareUtil:
    stock_zh_a_code_name_df: pd.DataFrame = None  # A股股票代码和名称的缓存
    trade_days_df: pd.DataFrame = None  # 交易日历数据, 包含所有交易日信息, 用于判断是否交易日
    cache_dir: str = FileUtil.create_cache_dir(None, __file__, clear=False)  # 缓存目录, 默认为当前目录, 会存储请求的都得所有股票名称和代码数据信息
    stock_summary_dict: dict = {}  # 获取过的股票摘要信息, 接口: get_stock_summary()
    _has_update_name_by_net: bool = False  # 是否已经从网络更新了股票名称

    @staticmethod
    # @log_time_consume()
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

        if CommonUtil.isNoneOrBlank(stock_name) and not AkShareUtil._has_update_name_by_net:  # 未找到名称,则从网络获取
            print(f'invoke stock_info_a_code_name from net')
            df = ak.stock_info_a_code_name()
            df['code'].astype(str)
            df.to_csv(file_path)

            result = pd.Series() if df is None else df.query(f"code == '{code}'")['name']
            stock_name: str = '' if result.empty else result.values[0]
            AkShareUtil._has_update_name_by_net = True

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
    def get_market_data(code: str, hk: bool = False, n_day_ago: int = 0, period: int = 1) -> pd.DataFrame:
        """
        获取指定股票的分钟级实时交易信息(支持A股和港股)
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
        return stock_min_df

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
        try:
            stock_min_df = AkShareUtil.get_market_data(code, hk, n_day_ago, period)
            if not stock_min_df.empty:
                latest_data = stock_min_df.iloc[-1:]  # 最新1min的数据, 包含开盘价,收盘价,最高价,最低价,成交量,成交额等信息
                latest_price: float = latest_data['收盘'].iloc[-1]  # 最新价格
                return latest_price
        except Exception as e:
            NetUtil.push_to_robot(f'get_latest_price error for {code}: {e}', printLog=True)
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

    @staticmethod
    def save_cache(df: pd.DataFrame, file_name: str) -> str:
        """
        缓存数据到本地
        """
        file_path = f'{AkShareUtil.cache_dir}/{file_name}.csv'
        file_path = FileUtil.recookPath(file_path)
        df.to_csv(file_path)
        return file_path

    @staticmethod
    def read_cache(file_name: str,
                   dtype: dict = None,
                   parse_dates: list = None) -> Union[pd.DataFrame, None]:
        """
        从本地缓存中读取数据,若缓存文件不存在,则返回None
        """
        file_path = f'{AkShareUtil.cache_dir}/{file_name}.csv'
        file_path = FileUtil.recookPath(file_path)
        if FileUtil.isFileExist(file_path):
            return pd.read_csv(file_path, dtype=dtype, parse_dates=parse_dates)
        return None

    @staticmethod
    def is_trading_day(n_days_ago: int = 0) -> bool:
        """
        判断某一天是否为A股交易日
        文档: https://akshare.akfamily.xyz/data/tool/tool.html#id1
        数据示例:
              trade_date
        0     1990-12-19
        1     1990-12-20
        2     1990-12-21
        """
        date_str = TimeUtil.getTimeStr('%Y-%m-%d', n_days_ago)
        _cache_name = 'trade_date_hist'
        calendar_df = AkShareUtil.read_cache(_cache_name)
        try:
            if calendar_df is None or TimeUtil.dateDiff(date_str, calendar_df['trade_date'].iloc[-1], '%Y-%m-%d') > 0:
                print(f'invoke tool_trade_date_hist_sina from net')
                calendar_df = ak.tool_trade_date_hist_sina()
                AkShareUtil.save_cache(calendar_df, _cache_name)
            return date_str in calendar_df['trade_date'].values  # 检查日期是否在交易日列表中
        except Exception as e:
            print(f"获取A股交易日历失败: {e}")
            return False

    @staticmethod
    def wait_next_deal_time(start_time: str = '09:30:00', end_time: str = '16:00:00'):
        """
        休眠等待到下一次的交易时间段
        :param start_time: 开盘时间, 默认为 09:30:00
        :param end_time: 收盘时间, 默认为 16:00:00
        """
        start_index = 0
        now = TimeUtil.getTimeStr(fmt="%H:%M:%S", n=0)
        diff = TimeUtil.calc_sec_diff(now, end_time, '%H:%M:%S')
        if diff > 0:  # 当前时间已超过收盘时间, 则休眠到下一个交易日的开盘时间
            CommonUtil.printLog(f'当前已超过收盘时间: {end_time}, 不管是否是交易日, 都需要等待到次日')
            start_index = -1

        next_trading_day = start_index  # 下一个交易日是几天之后?  -1 表示一天后也就是明天
        for i in range(start_index, -30, -1):
            if AkShareUtil.is_trading_day(i):
                next_trading_day = i
                break

        now = TimeUtil.getTimeStr()
        next_day = TimeUtil.getTimeStr('%Y-%m-%d', next_trading_day)
        diff = abs(TimeUtil.calc_sec_diff(now, f'{next_day} {start_time}', '%Y-%m-%d %H:%M:%S'))
        msg = f'wait_next_deal_time 等待 {next_day} {start_time} 后再执行, 休眠 {diff}秒'
        NetUtil.push_to_robot(msg, printLog=True)
        TimeUtil.sleep(diff)

    @staticmethod
    def query_stock_daily_history(code: str, hk: bool = False, n_day_ago: int = 0,
                                  period: str = 'daily') -> pd.DataFrame:
        """
        获取A股/港股股票历史数据
        文档: https://akshare.akfamily.xyz/data_tips.html
        A股使用接口: ak.stock_zh_a_hist()
        港股使用接口: ak.stock_hk_hist()

        获取后通过读取今日开盘/收盘等价格操作:
        字段:  "日期","开盘","收盘","最高","最低","成交量","成交额","振幅","涨跌幅","涨跌额","换手率","股票代码"

        _df_hist = AkShareUtil.query_stock_daily_history_hk('01810', 3)  # 小米集团
        _df_hist = AkShareUtil.query_stock_daily_history('689009', False, 3)  # 九号公司
        print(_df_hist)
        if not _df_hist.empty:
            _latest_data = _df_hist.iloc[-1:] # 最近一个交易日数据, 不一定是今日

            _target_date = TimeUtil.getTimeObj("%Y%m%d", 2)  # 获取指定天之前的交易数据, 非交易日无效
            _target_data = _df_hist[_df_hist['日期'] == _target_date.date()]
            print(f'\n{_target_date} 的信息:{_target_data}')
            if not _target_data.empty:
                print(f' 开盘:{_target_data["开盘"].iloc[0]}')  # float 开盘价
                print(f' 收盘:{_target_data["收盘"].iloc[0]}')  # float 收盘价

        :param code: 股票代码
        :param hk: 是否是港股
        :param n_day_ago: 获取往前推多少天的数据, 0表示当天  1表示前一天  -1 表示后一天
        :param period: 可取值: 'daily', 'weekly', 'monthly'
        """
        start_date = TimeUtil.getTimeStr('%Y%m%d', n_day_ago)
        today = TimeUtil.getTimeStr('%Y%m%d', 0)
        try:
            if hk:
                return ak.stock_hk_hist(symbol=code, period=period, start_date=start_date, end_date=today)
            else:
                return ak.stock_zh_a_hist(symbol=code, period=period, start_date=start_date, end_date=today)
        except Exception as e:
            CommonUtil.printLog(f'获取股票{code}历史数据失败: {e}')
            return pd.DataFrame()

    @staticmethod
    def get_stock_zh_index(symbol: str = '上证系列指数') -> pd.DataFrame:
        """
        获取指数行情
        文档: https://akshare.akfamily.xyz/data/index/index.html#id1
        描述: 东方财富网-行情中心-沪深京指数
        限量: 单次返回所有指数的实时行情数据
        返回数据示例:
              序号  代码     名称    最新价   涨跌幅   涨跌额  ... 振幅  最高  最低 今开 昨收  量比
        0      1  000116  信用100   183.69  0.01  0.02  ...  0.0 NaN NaN NaN   183.67 NaN
        1      2  000101   5年信用   233.04  0.01  0.02  ...  0.0 NaN NaN NaN   233.02 NaN
        2      3  000022   沪公司债   234.63  0.01  0.02  ...  0.0 NaN NaN NaN   234.61 NaN
        3      4  000061  沪企债30   169.79  0.01  0.01  ...  0.0 NaN NaN NaN   169.78 NaN
        4      5  000012   国债指数   206.03  0.00  0.01  ...  0.0 NaN NaN NaN   206.02 NaN
        ..   ...     ...    ...      ...   ...   ...  ...  ...  ..  ..  ..      ...  ..
        174  175  000005   商业指数  2351.11  0.00  0.00  ...  0.0 NaN NaN NaN  2351.11 NaN
        175  176  000004   工业指数  2703.99  0.00  0.00  ...  0.0 NaN NaN NaN  2703.99 NaN
        176  177  000003   Ｂ股指数   234.19  0.00  0.00  ...  0.0 NaN NaN NaN   234.19 NaN
        177  178  000002   Ａ股指数  3111.03  0.00  0.00  ...  0.0 NaN NaN NaN  3111.03 NaN
        178  179  000001   上证指数  2967.25  0.00  0.00  ...  0.0 NaN NaN NaN  2967.25 NaN
        [179 rows x 14 columns]

        只提取其中某个指数:
        _df = AkShareUtil.get_stock_zh_index()
        _data = _df[_df['名称'] == '上证指数'].iloc[0]

        :param symbol: "上证系列指数"；choice of {"沪深重要指数", "上证系列指数", "深证系列指数", "指数成份", "中证系列指数"}
        """
        return ak.stock_zh_index_spot_em(symbol=symbol)

    @staticmethod
    def get_prev_close(code: str, hk: bool) -> float:
        """
        获取前一个交易日的收盘价
        :param code: 股票代码
        :param hk: 是否是港股
        :return: 前一个交易日的收盘价, 0.0表示获取失败
        """
        _df = AkShareUtil.query_stock_daily_history(code, hk, 20)
        if not _df.empty:
            _prev_data = _df.iloc[-2:-1]
            return float(_prev_data['收盘'].iloc[0])
        return 0.0

    @staticmethod
    def get_industry_constituent_stock(symbol: str, order_by: str = '市盈率-动态', asc: bool = False, top_n: int = 10) -> Optional[pd.DataFrame]:
        """
        获取行业成分股
        :param symbol: 行业名称, 可通过 ak.stock_board_industry_name_em() 获取, 如:
                        '农牧饲渔', '银行', '酿酒行业', '食品饮料', '旅游酒店', '电力行业', '农药兽药', '铁路公路',
                       '航空机场', '贵金属', '小金属', '商业百货', '物流行业', '煤炭行业', '中药', '航运港口', '公用事业',
                       '燃气', '水泥建材', '珠宝首饰', '保险', '化肥行业', '电子化学品', '航天航空', '化纤行业',
                       '钢铁行业', '美容护理', '石油行业', '装修建材', '工程建设', '生物制品', '房地产开发', '医药商业',
                       '证券', '造纸印刷', '综合行业', '汽车整车', '化学制品', '玻璃玻纤', '化学原料', '非金属材料',
                       '装修装饰', '多元金融', '专业服务', '化学制药', '有色金属', '医疗器械', '纺织服装', '工程机械',
                       '房地产服务', '贸易行业', '包装材料', '文化传媒', '半导体', '汽车服务', '能源金属', '教育',
                       '家电行业', '环保行业', '采掘行业', '橡胶制品', '交运设备', '电源设备', '电网设备', '通信服务',
                       '船舶制造', '风电设备', '家用轻工', '计算机设备', '工程咨询服务', '游戏', '医疗服务', '塑料制品',
                       '仪器仪表', '通信设备', '专用设备', '软件开发', '通用设备', '汽车零部件', '光伏设备', '电子元件',
                       '电机', '光学光电子', '互联网服务', '电池', '消费电子'
        :param order_by: 排序字段,支持: '序号', '代码', '名称', '最新价', '涨跌幅', '涨跌额', '成交量', '成交额', '振幅', '最高', '最低','今开', '昨收', '换手率', '市盈率-动态', '市净率'
        :param asc: 是否升序,默认false表示降序
        :param top_n: 前N只股票
        :return: 行业成分股信息, 包括两列: '代码', '名称'
        """
        # 获取A股指定行业板块成分股数据
        # stock_board_industry_cons_em_df.columns 获取包含的字段:
        # ['序号', '代码', '名称', '最新价', '涨跌幅', '涨跌额', '成交量', '成交额', '振幅', '最高', '最低','今开', '昨收', '换手率', '市盈率-动态', '市净率'
        try:
            df = ak.stock_board_industry_cons_em(symbol=symbol)
            # print(df)

            # 根据指定指标排列,获取前N只股票
            # stock_qiche.columns 获取包含的字段:
            # stock_qiche["代码"].values
            top_n_stocks = df.sort_values(by=order_by, ascending=asc).iloc[0:top_n, :]
            # print(top_n_stocks.columns)  # 获取包含的字段
            # print(top_n_stocks)  # 打印前N只股票信息
            return top_n_stocks[["代码", "名称"]]
        except Exception as e:
            CommonUtil.printLog(f'获取{symbol}行业成分股失败: {e}')
            return None

    @staticmethod
    def index_zh_a_hist(symbol: str, period: str = 'daily', start_date: str = '20250101', end_date: str = '20251006') -> Optional[pd.DataFrame]:
        """
        接口: index_zh_a_hist
        目标地址: http://quote.eastmoney.com/center/hszs.html
        描述: 东方财富网-中国股票指数-行情数据
        限量: 单次返回具体指数指定 period 从 start_date 到 end_date 的之间的近期数据
        文档: https://akshare.akfamily.xyz/data/index/index.html#id7
        :param symbol: 指数名称,不用加市场, 比如沪深300, 传入:000300
        :param period: 可取值: 'daily', 'weekly','monthly'
        :param start_date: 开始日期, 格式: '20250101'
        :param end_date: 结束日期, 格式: '20301230'
        :return: 指数行情数据, 包含以下字段:
            日期	开盘	收盘	最高	最低	成交量	成交额	振幅	涨跌幅	涨跌额	换手率
            其中日期默认时object对象,成交量单位是手, 成交额单位是元, 振幅/涨跌幅/涨跌额/换手率 单位是%, 数据类型都是float64
        """
        try:
            df = ak.index_zh_a_hist(symbol=symbol, period=period, start_date=start_date, end_date=end_date)
            # 转换为datetime类型,并设置为index列
            # df['日期'] = pd.to_datetime(df['日期'])
            # df.set_index('日期', inplace=True)
            return df
        except Exception as e:
            CommonUtil.printLog(f'index_zh_a_hist 获取指数{symbol}历史数据失败: {e}')
            # traceback.print_exc()
            return None

    @staticmethod
    def stock_zh_index_daily(symbol: str, start_date: str = '2025-01-01', end_date: str = '2029-12-30', fmt: str = '%Y-%m-%d') -> Optional[pd.DataFrame]:
        """
        接口: stock_zh_index_daily
        目标地址: https://finance.sina.com.cn/realstock/company/sz399552/nc.shtml(示例)
        描述: 股票指数的历史数据按日频率更新
        限量: 单次返回指定 symbol 的所有历史行情数据
        文档: https://akshare.akfamily.xyz/data/index/index.html#id13
        :param symbol: 指数名称,需要包含市场名称,比如沪深300, 传入:sh000300
        :param start_date: 待获取数据的开始日期, 格式: '2025-01-01'
        :param end_date: 待获取数据的结束日期, 格式: '2030-12-30'
        :param fmt: 日期格式, 默认为: '%Y-%m-%d'
        :return: 指数行情数据, 包含以下字段:
            date open high low close volume volume
        """
        target_fmt = '%Y-%m-%d'
        start_date = TimeUtil.convertFormat(start_date, fmt, target_fmt)
        end_date = TimeUtil.convertFormat(end_date, fmt, target_fmt)
        cur_day = TimeUtil.getTimeStr(target_fmt, 0)
        end_date = end_date if TimeUtil.dateDiff(end_date, cur_day, target_fmt) <= 0 else cur_day

        _cache_name = f'stock_zh_index_daily_{symbol}'
        cache_df = AkShareUtil.read_cache(_cache_name)
        if cache_df is None or TimeUtil.dateDiff(end_date, cache_df['date'].iloc[-1], target_fmt) > 0:
            print(f'invoke stock_zh_index_daily from net for symbol:{symbol}')
            try:
                df = ak.stock_zh_index_daily(symbol=symbol)
                # # 转换为datetime类型,并设置为index列
                # df['date'] = pd.to_datetime(df['date'])
                # df.set_index('date', inplace=True)
                AkShareUtil.save_cache(df, _cache_name)
                cache_df = df
            except Exception as e:
                CommonUtil.printLog(f'stock_zh_index_daily 获取指数{symbol}历史数据失败: {e}')
                traceback.print_exc()

        if cache_df is not None:
            # 确保比较的日期类型一致，将日期转换为字符串进行比较
            filtered_df = cache_df[(cache_df['date'].astype(str) >= start_date) & (cache_df['date'].astype(str) <= end_date)]
            return filtered_df
        return cache_df


if __name__ == '__main__':
    # df = AkShareUtil.get_market_data('002651')
    # df = AkShareUtil.query_stock_daily_history('002651')
    # print(df)
    # _df_hist = AkShareUtil.query_stock_daily_history('002651', 3)
    # _df_hist = AkShareUtil.query_stock_daily_history('01810', True, 3)  # 小米集团

    # # 获取开盘收盘等信息
    # from TimeUtil import TimeUtil
    #
    # # _df_hist = AkShareUtil.query_stock_daily_history('689009', False, 20)  # 九号公司
    # _df_hist = AkShareUtil.query_stock_daily_history('09868', True, 20)  # 小鹏汽车-W
    # print(_df_hist)
    # if not _df_hist.empty:
    #     _latest_data = _df_hist.iloc[-1:]
    #     _yesterday_data = _df_hist.iloc[-2:-1]
    #
    #     print(f'\n最近一个交易日信息:{_latest_data}')
    #     print(f'开盘:{_latest_data["开盘"].iloc[0]}')
    #     print(f'收盘:{_latest_data["收盘"].iloc[0]}')
    #
    #     print(f'\n前一个交易日信息:{_yesterday_data}')
    #     print(f'开盘:{_yesterday_data["开盘"].iloc[0]}')
    #     print(f'收盘:{_yesterday_data["收盘"].iloc[0]}')
    #
    #     _target_date = TimeUtil.getTimeObj("%Y%m%d", 2)  # 字符串转为date对象
    #     _target_data = _df_hist[_df_hist['日期'] == _target_date.date()]
    #     print(f'\n{_target_date} 的信息:{_latest_data}')
    #     if not _target_data.empty:
    #         print(f' 开盘:{_target_data["开盘"].iloc[0]}')  # float 开盘价
    #         print(f' 收盘:{_target_data["收盘"].iloc[0]}')  # float 收盘价
    #
    # print(f'小鹏汽车昨收价:{AkShareUtil.get_prev_close("09868", True)}')
    #
    # print(AkShareUtil.get_industry_constituent_stock("汽车整车"))

    # df = akshare.query(
    #     symbols=stock_qiche["代码"].values,
    #     start_date='3/2/2021',
    #     end_date='3/1/2023',
    #     adjust="hfq",
    #     timeframe="1d",
    # )
    # df

    # print(AkShareUtil.index_zh_a_hist('000300'))
    print(AkShareUtil.stock_zh_index_daily('sh000300', '2025-04-01', '2025-09-30'))
