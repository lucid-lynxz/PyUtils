from pybroker import ExecContext
from pybroker.vect import cross
from util.pybroker.base_strategy import BaseStrategy
from util.pybroker.indicators import generate_macd_indicator


class StrategyMACD(BaseStrategy):
    """
    生成MACD指标信息: (DIF,DEA)
    https://zhuanlan.zhihu.com/p/348987788

    参数说明:
    * fastperiod: 快速EMA周期，默认为12。用于计算短期指数移动平均线，反映价格短期趋势。
    * slowperiod: 慢速EMA周期，默认为26。用于计算长期指数移动平均线，反映价格长期趋势。
    * signalperiod: 信号线周期，默认为9。用于计算DIF的指数移动平均线，生成信号线(DEA)。

    MACD指标计算原理:
    1. DIF线：快速EMA线与慢速EMA线的差值
       DIF = EMA(close, fastperiod) - EMA(close, slowperiod)
    2. DEA线：DIF线的M日指数移动平均
       DEA = EMA(DIF, signalperiod)
    3. MACD柱状图：(DIF-DEA)×2

    使用方法:
    - 当DIF线上穿DEA线时，为买入信号
    - 当DIF线下穿DEA线时，为卖出信号
    - MACD柱状图的变化可以反映趋势的强弱
    """

    def __init__(self, fastperiod: int = 12, slowperiod: int = 26, signalperiod: int = 9, **kwargs):
        """
        :param fastperiod: 快速EMA周期，默认为12。用于计算短期指数移动平均线，反映价格短期趋势。
        :param slowperiod: 慢速EMA周期，默认为26。用于计算长期指数移动平均线，反映价格长期趋势。
        :param signalperiod: 信号线周期，默认为9。用于计算DIF的指数移动平均线，生成信号线(DEA)
        :param kwargs: 其他参数
        """
        self.fastperiod = fastperiod
        self.slowperiod = slowperiod
        self.signalperiod = signalperiod
        super().__init__(**kwargs)
        print(f'MACD策略 fastperiod:{fastperiod}, slowperiod:{slowperiod}, signalperiod:{signalperiod}')

    def generate_indicators(self) -> list:
        dea, dif = generate_macd_indicator(self.fastperiod, self.slowperiod, self.signalperiod)
        return [dea, dif]

    def buy_func(self, ctx: ExecContext) -> None:
        dif = ctx.indicator('dif')  # 快线
        dea = ctx.indicator('dea')  # 慢线

        # 检查短期均线是否上穿长期均线（产生买入信号）
        buy_signal = cross(dif, dea)[-1]
        # 检查短期均线是否下穿长期均线（产生卖出信号）
        sell_signal = cross(dea, dif)[-1]

        if buy_signal and not ctx.long_pos():
            self.update_buy_shares(ctx)
            # self.update_stop_info(ctx) # 不设置止盈止损
            # print('买入信号', ctx.dt, buy_signal)

        if sell_signal and ctx.long_pos():
            ctx.sell_all_shares()
            # print('卖出信号', ctx.dt, sell_signal)
