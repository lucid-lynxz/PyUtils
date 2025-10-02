from pybroker import ExecContext

from util.pybroker.base_strategy import BaseStrategy


class StrategyReversal(BaseStrategy):
    """
    ### 高低点反转策略
    **策略原理**：基于股票价格在高低点之间的反转趋势进行操作。
    **具体操作**：
    - **买入条件**：当股票价格连续下跌后，出现当日最低价低于前几日的最低价，且当日收盘价高于当日最低价一定幅度（如5%），则认为可能出现反转，以当日收盘价买入股票。止损设置为买入价下跌8%，止盈设置为买入价上涨15%。
    - **卖出条件**：当股票价格达到止盈价位或者跌破止损价位时卖出。此外，若买入后股票价格未能持续上涨，再次出现当日最高价低于前几日最高价，且收盘价低于当日最高价一定幅度（如3%），也可考虑卖出股票，避免进一步损失。
    """

    def __init__(self, days: int = 5, bounce_low: float = 1.05, bounce_high: float = 0.97, **kwargs):
        """
        :param days: 需要计算最近多少天的最高价和最低价, 请传入大于1的整数, 默认5天
        :param bounce_low: 当日收盘价时当日最低价的倍数, 请传入大于1的浮点数, 此时表示当日低点反转成功, 即: 上涨, 此时可能非尝试买入
        :param bounce_high: 当日收盘价时当日最高价的倍数, 请传入小于1的浮点数, 此时表示当日高点反转成功, 即: 下跌, 此时可能非尝试卖出
        :param kwargs: 其他参数
        """
        super().__init__(**kwargs)
        self.days = days
        self.bounce_low = bounce_low
        self.bounce_high = bounce_high
        self.name = '高低点反转策略'

    def buy_func(self, ctx: ExecContext) -> None:
        high = ctx.high[-self.days:-1].max()  # 近10日最高价
        low = ctx.low[-self.days:-1].min()  # 近10日最低价

        pos = ctx.long_pos()  # 获取当前的长期持有的股票
        if not pos and ctx.low[-1] < low and ctx.close[-1] > ctx.low[-1] * self.bounce_low:
            self.update_buy_shares(ctx)
            self.update_stop_info(ctx)

        if pos and ctx.high[-1] < high and ctx.close[-1] < ctx.high[-1] * self.bounce_high:
            ctx.sell_all_shares()
