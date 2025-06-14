from base.Interfaces import Runnable
from util.AkShareUtil import AkShareUtil
from util.TimeUtil import TimeUtil
from wool_tasks.ths_trade.stock_position import StockPosition
from wool_tasks.ths_trade.ths_auto_trade import THSTrader


class ConditionOrder(Runnable):
    """
    条件单
    """

    def __init__(self, ths_trader: THSTrader,
                 position: StockPosition,
                 base: float,
                 bounce: float,
                 deal_count: int,
                 break_upward: bool,
                 bounce_unit: str = 'ratio',
                 start_time: str = '09:30:00',
                 end_date: str = '2099-12-1'):
        """
        :param ths_trader: 同花顺工具类,用于实现买入/卖出等操作
        :param position: 股票的持仓信息
        :param base: 基准价格, 正数有效, 表示突破该价格后开始监控反弹力度, 0或负数表示不设置基准价格(默认会以持仓成本价/最新价为基准)
        :param bounce: 有基准价格base时, 表示反弹幅度, 此时非负数有效, 至于是价格还是比例, 由unit决定
                       反弹幅度达到一定时就触发交易
        :param deal_count: 执行交易的股数, 正数表示买入, 负数表示卖出, 如: -100 表示卖出100股
        :param break_upward: true-向上突破 false-向下突破
        :param bounce_unit: 反弹幅度的单位, 默认为比例, 比如0.5,表示相对于极值反弹 50%, 若单位为price, 则表示反弹0.5元
        :start_time: 开始检测的时间, 默认为9:30:00开盘, 若为了减少开盘前几分钟的大波动, 可以适当后延
        :end_date: 条件单截止日期(含)
        """
        self.active: bool = True  # 是否有效, 超期/已触发 就会变为无效
        self.hit: bool = False  # 是否已突破基准价

        self.ths_trader: THSTrader = ths_trader
        self.position = position  # 持仓信息
        self.is_hk = self.position.is_hk_stock  # 是否为港股

        cost_price = float(self.position.cost_price)  # 持仓成本价
        self.base: float = cost_price if base <= 0 else base  # 基准价格
        self.break_upward: bool = break_upward  # 突破base基准价的方向

        self.bounce: float = bounce
        self.is_unit_ratio: bool = bounce_unit == 'ratio'

        # 极值, 突破base基准价后的的最高/最低值, 用于判断是否已达到反弹幅度
        # break_upward=true, 向上突破成功时, 记录突破后的最高价
        # break_upward=false, 向下突破成功时, 记录突破后的最低价
        self.extreme_value: float = -999999 if self.break_upward else 999999

        self.deal_count = deal_count  # 执行交易时买卖的股数, 负数表示卖出

        self.start_time: str = start_time
        self.end_date: str = end_date  # 条件单截止日期(含)

    def run(self):
        """
        支持以下参数：
            code (str): 代码
            market_info (pd.DataFrame):其他信息, 与code不能同时为空
        """
        # 若今天不是交易日,则不做检测
        if not self.active or not AkShareUtil.is_trading_day():
            return

        # 若时间不满足,则不做检测
        if (not TimeUtil.is_time_greater_than(self.start_time)
                or TimeUtil.is_time_greater_than(self.end_date)):
            return

        # 卖出股票时, 若可用余额不足,则本轮不做检测
        if self.deal_count < 0 and int(self.position.available_balance) < abs(self.deal_count):
            return

        # 获取最新价格
        latest_price = AkShareUtil.get_latest_price(self.position.code, self.is_hk)  # 获取最新价格
        if latest_price == 0.0:
            return

        # 若基准价为0,则优先使用成本价替代, 若无成本价,则使用最新价
        if self.base <= 0:
            self.base = latest_price

        # 判断是否已达到了基准价
        if not self.hit:
            if self.break_upward and latest_price >= self.base:
                self.hit = True
            elif not self.break_upward and latest_price <= self.base:
                self.hit = True

        if not self.hit:
            return

        # 达到基准价后, 检测反弹力度
        if self.break_upward:  # 向上突破
            self.extreme_value = max(latest_price, self.extreme_value)
            delta = abs(self.extreme_value - latest_price)
        else:
            self.extreme_value = min(latest_price, self.extreme_value)
            delta = abs(self.extreme_value - latest_price)

        if self.is_unit_ratio:
            expected_delta = self.extreme_value * self.bounce
        else:
            expected_delta = self.bounce

        # 反弹幅度超过预设值,触发交易
        if delta >= expected_delta:
            self.active = False
            self.ths_trader.deal(self.position.code, latest_price, self.deal_count)
            print(
                f"触发条件单, code={self.position.code}, name={self.position.name}, 基准价={self.base}, 反弹幅度={self.bounce}, 方向={self.break_upward}, 极值={self.extreme_value}, 最新价={latest_price}")

#
# if __name__ == '__main__':
#     Condition().run(name="测试")
