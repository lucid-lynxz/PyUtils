from pybroker import ExecContext
from pybroker.vect import cross
from util.pybroker.base_strategy import BaseStrategy
from util.pybroker.indicators import generate_sma_indicator


class StrategyDMA(BaseStrategy):
    """
    双均线策略-所谓的黄金交叉
    “双均线策略” 的英文名称是 “Dual Moving Average Strategy”，简称 “DMA Strategy”。
    “金叉” 的英文名称是 “Golden Cross”。“死叉” 的英文名称是 “Dead Cross”

    - **策略原理**：计算短期均线和长期均线，当短期均线上穿长期均线时，产生买入信号；当短期均线下穿长期均线时，产生卖出信号。同时，设置止损和止盈价位。
    - **具体操作**：
    - **买入条件**：假设短期均线为 5 日均线，长期均线为 20 日均线。当 5 日均线的值大于 20 日均线的值，且当日收盘价大于 5 日均线和 20 日均线时，以当日收盘价买入股票。
    - **卖出条件**：当 5 日均线的值小于 20 日均线的值，或者股票价格达到止盈价位（如买入后上涨 20%），或者股票价格达到止损价位（如买入后下跌 10%），则卖出股票。
    """

    def __init__(self, short_period: int = 5, long_period: int = 20, **kwargs):
        """
        :param short_period: 短期均线周期，默认为5。用于计算短期均线，反映价格短期趋势
        :param long_period: 长期均线周期，默认为20。用于计算长期均线，反映价格长期趋势
        :param kwargs: 其他参数
        """
        self.short_period = short_period
        self.long_period = long_period
        super().__init__(**kwargs)
        print(f'双均线策略, 短期均线周期:{self.short_period}, 长期均线周期:{self.long_period}')

    def generate_indicators(self) -> list:
        sma_short = generate_sma_indicator(self.short_period, 'sma_short')  # 定义短期均线指标
        sma_long = generate_sma_indicator(self.long_period, 'sma_long')  # 定义长期均线指标
        return [sma_short, sma_long]

    def buy_func(self, ctx: ExecContext) -> None:
        sma_short_values = ctx.indicator('sma_short')  # 获取短期均线数据
        sma_long_values = ctx.indicator('sma_long')  # 获取长期均线数据

        # 检查短期均线是否上穿长期均线（产生买入信号）
        buy_signal = cross(sma_short_values, sma_long_values)[-1]
        # 检查短期均线是否下穿长期均线（产生卖出信号）
        sell_signal = cross(sma_long_values, sma_short_values)[-1]

        if buy_signal and not ctx.long_pos():
            self.update_buy_shares(ctx)
            # self.update_stop_info(ctx) # 不设置止盈止损
            # print('买入信号', ctx.dt, buy_signal)

        if sell_signal and ctx.long_pos():
            ctx.sell_all_shares()
            # print('卖出信号', ctx.dt, sell_signal)
