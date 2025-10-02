import pybroker
from pybroker.ext.data import AKShare, DataSource
from pybroker import ExecContext, StrategyConfig, Strategy, IndicatorSet
from pybroker.indicator import highest, lowest, Indicator
import talib

import pandas as pd
import datetime
import matplotlib.pyplot as plt
from typing import Union, Optional, Iterable
from typing_extensions import Self

from util.TimeUtil import TimeUtil

from abc import abstractmethod
from dataclasses import dataclass


@dataclass
class BackTestInfo:
    """
    回测结果数据类
    """
    init_value: float = 0.0  # 初始资金
    end_value: float = 0.0  # 最终资金
    profit: float = 0.0  # 利润  end_value - init_value
    profit_rate: float = 0.0  # 利润率 0.1 表示 profit/init_value=10%收益
    orders: pd.DataFrame = None  # 买卖交易操作记录


class BaseStrategy(object):
    """
    策略基类, 所有策略都应该继承此类, 并实现 buy_func 方法
    对于需要使用指标的策略, 可以重写 generate_indicators 方法, 返回需要的指标列表
    其他方法/属性说明:
    * backtest(): 执行回测
    * plot_portfolio(): 绘制回测的资金的变化情况
    *
    * self.backtest_result: 回测后的额完整结果
    * self.backtest_info: 获取回测结果信息,比如资金变化,收益率和订单信息等
    *
    * self.buy_shares: 买入股数, 默认为0.5, 表示50%  >=1 时表示股数
    * self.stop_loss_pct: 止损百分比, 10 表示 10%,大于0有效
    * self.stop_profit_pct: 止盈百分比,大于0有效
    * self.stop_trailing_pct: 移动止损, 最高市场价格下降N%时触发止损,大于0有效
    """

    def __init__(
            self,
            symbols: Union[str, Iterable[str]],
            buy_shares: float = 0.5,
            initial_cash: float = 100000,
            start_date: str = TimeUtil.getTimeStr(fmt='%Y%m%d', n=180),
            end_date: str = TimeUtil.getTimeStr(fmt='%Y%m%d'),
            data_source: Union[DataSource, pd.DataFrame] = AKShare(),
            stop_loss_pct: float = 8,
            stop_profit_pct: float = 13,
            stop_trailing_pct: float = 0
    ):
        """
        :param symbols: 股票代码, 默认为 '000001.SZ', 也可以传入多个股票代码, 如 ['000001.SZ', '000002.SZ']
        :param initial_cash: 初始资金, 默认为100000, 10W源
        :param start_date: 回测开始日期, 默认为180天前
        :param end_date: 回测结束日期, 默认为今天
        :param data_source: 数据源, 默认为 AKShare, 也可以传入 DataFrame
        :param buy_shares: 买入股数, 默认为0.5, 表示50%, 取值范围: (0, 1],   >1 时表示股数
        :param stop_loss_pct: 止损百分比, 默认8 表示 8%,大于0有效
        :param stop_profit_pct: 止盈百分比,默认13, 表示13%, 大于0有效
        :param stop_trailing_pct: 移动止损, 最高市场价格下降N%时触发止损,大于0有效, 默认0
        """
        # 创建策略配置对象，设置初始现金
        pybroker.enable_data_source_cache('akshare')
        self.config = StrategyConfig(initial_cash=initial_cash)
        self.strategy = Strategy(data_source=data_source, start_date=start_date, end_date=end_date, config=self.config)
        self.strategy.add_execution(fn=self.buy_func, symbols=symbols, indicators=self.generate_indicators())

        self.backtest_result: Optional[pybroker.TestResult] = None  # 执行回测的完整结果
        self.backtest_info: Optional[BackTestInfo] = None  # 从回测结果中提取的部分信息,比如收益率等

        # 以下参数可通过在子类的 buy_func() 中调用 update_stop_info() 和 update_buy_shares() 来生效
        self.buy_shares = buy_shares  # 买入股数, 默认为0.5, 表示50%  >=1 时表示股数
        self.stop_loss_pct: float = stop_loss_pct  # 止损百分比, 10 表示 10%,大于0有效
        self.stop_profit_pct: float = stop_profit_pct  # 止盈百分比,大于0有效
        self.stop_trailing_pct: float = stop_trailing_pct  # 移动止损, 最高市场价格下降N%时触发止损,大于0有效

        print(f'symbols:{symbols},initial_cash:{initial_cash}, start_date:{start_date}, end_date:{end_date}')

    def generate_indicators(self) -> Optional[Union[Indicator, Iterable[Indicator]]]:
        """
        子类按需返回所需的指标实现, 默认返回为空
        部分常用指标已经在 indicators.py 中实现, 可以直接使用
        """
        return []

    @abstractmethod
    def buy_func(self, ctx: ExecContext) -> None:
        """
        回测买卖函数, 之类必须要实现
        """
        pass

    def backtest(self, warmup: int = 15) -> Self:
        """
        执行回测
        :param warmup: 回测参数
        """
        self.backtest_result = self.strategy.backtest(warmup=warmup)

        # 获取回测结果信息,比如资金变化,收益率和订单信息等, 按需扩展
        df = self.backtest_result.metrics_df
        self.backtest_info = BackTestInfo()
        self.backtest_info.init_value = df['value'].loc[1]
        self.backtest_info.end_value = df['value'].loc[2]
        self.backtest_info.profit = self.backtest_info.end_value - self.backtest_info.init_value
        self.backtest_info.profit_rate = self.backtest_info.profit / self.backtest_info.init_value
        self.backtest_info.orders = self.backtest_result.orders
        return self

    def plot_portfolio(self) -> Self:
        """
        绘制回测的资金的变化情况
        """
        if self.backtest_result is None:
            return self
        self.backtest_result.portfolio.equity.plot()
        plt.show()  # 启动 matplotlib 的事件循环，使图形窗口保持显示
        return self

    def print_backtest_profit_info(self) -> Self:
        info = self.backtest_info
        if info is None:
            print('backtest result is None')
        print(f'print_backtest_profit_info: {info.init_value} -> {info.end_value}  {info.profit}  {info.profit_rate * 100:.2f}%')
        return self

    def update_buy_shares(self, ctx: ExecContext):
        """
        未持仓时,更新要买入的股数
        """
        if ctx.long_pos():
            return

        ctx.buy_shares = self.buy_shares if self.buy_shares > 1 else ctx.calc_target_shares(self.buy_shares)

    def update_stop_info(self, ctx: ExecContext) -> None:
        """
        未持仓时,更新止盈止损参数
        """
        if ctx.long_pos():
            return

        if self.stop_loss_pct > 0:
            ctx.stop_loss_pct = self.stop_loss_pct

        if self.stop_profit_pct > 0:
            ctx.stop_profit_pct = self.stop_profit_pct

        if self.stop_trailing_pct > 0:
            ctx.stop_trailing_pct = self.stop_trailing_pct
        # ctx.stop_trailing_pct = 0.8  # 移动止损, 最高市场价格下降N%时触发止损
