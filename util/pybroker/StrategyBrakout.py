from pybroker import ExecContext

from util.pybroker.base_strategy import BaseStrategy


class StrategyBreakout(BaseStrategy):
    """
    突破策略: 股价突破近10日新高时买入, 跌破近10日新低时卖出
    """

    def __init__(self, days: int = 11, **kwargs):
        super().__init__(**kwargs)
        self.days = days
        self.name = '突破策略'
        self.description = f'股价突破近{days}日新高时买入, 跌破近{days}日新低时卖出'

    def buy_func(self, ctx: ExecContext) -> None:
        high = ctx.high[-self.days:-1].max()  # 近10日最高价
        low = ctx.low[-self.days:-1].min()  # 近10日最低价

        pos = ctx.long_pos()  # 获取当前的长期持有的股票
        if not pos and ctx.close[-1] > high:  # 如果当前价格大于近10日最高价
            self.update_buy_shares(ctx)
            self.update_stop_info(ctx)

        if pos and ctx.close[-1] < low:  # 如果当前价格小于近10日最低价
            ctx.sell_all_shares()
