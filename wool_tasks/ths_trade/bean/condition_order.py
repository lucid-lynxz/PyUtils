from typing import List

from base.Interfaces import Runnable
from util.AkShareUtil import AkShareUtil
from util.NetUtil import NetUtil
from util.TimeUtil import TimeUtil
from wool_tasks.ths_trade.bean.stock_position import StockPosition
from wool_tasks.ths_trade.ths_auto_trade import THSTrader


class ConditionOrder(Runnable):
    """
    条件单
    """
    ths_trader: THSTrader  # 同花顺工具类,用于实现买入/卖出等操作

    @classmethod
    def from_csv_row(cls, row: List[str]):
        """
        从csv文件中读取一行数据, 并创建ConditionOrder对象
        :param row: csv文件中的一行数据, 格式: 股票代码,股票名称,是否港股,基准价,向上突破(true/false),反弹幅度,交易股数,开始监测的时间,结束监测的日期
        :return: ConditionOrder对象
        """
        return ConditionOrder(StockPosition(code=row[0], name=row[1], market='港股通' if row[2] else ''),
                              base=float(row[3]),
                              break_up=row[4].lower() == 'true',
                              bounce_info=row[5],
                              deal_count=int(row[6]),
                              start_time=row[7],
                              end_date=row[8]
                              )

    def __init__(self, position: StockPosition,
                 base: float,
                 bounce_info: str,
                 deal_count: int,
                 break_up: bool,
                 start_time: str = '09:30:00',
                 end_date: str = '2099-12-1'):
        """
        :param position: 股票的持仓信息
        :param base: 基准价格, 正数有效, 表示突破该价格后开始监控反弹力度, 0或负数表示不设置基准价格(默认会以持仓成本价/最新价为基准)
        :param bounce_info: 表示反弹幅度, 支持两种写法, 如:0.5% 和 0.5, 前者表示反弹0.5%, 后者表示反弹0.5元
        :param deal_count: 执行交易的股数, 正数表示买入, 负数表示卖出, 如: -100 表示卖出100股
        :param break_up: true-向上突破 false-向下突破
        :start_time: 开始检测的时间, 默认为9:30:00开盘, 若为了减少开盘前几分钟的大波动, 可以适当后延
        :end_date: 条件单截止日期(含)
        """
        self.active: bool = True  # 是否有效, 超期/已触发 就会变为无效
        self.hit: bool = False  # 是否已突破基准价

        self.position = position  # 持仓信息
        self.is_hk = self.position.is_hk_stock  # 是否为港股

        cost_price = float(self.position.cost_price)  # 持仓成本价
        self.base: float = cost_price if base <= 0 else base  # 基准价格
        self.break_upward: bool = break_up  # 突破base基准价的方向

        self.is_unit_ratio: bool = '%' in bounce_info
        _bounce: float = float(bounce_info.replace('%', ''))
        self.bounce: float = _bounce / 100.0 if self.is_unit_ratio else _bounce  # 反弹幅度

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

        # 卖出股票时, 若可用余额不足,则调整为可用余额
        if self.deal_count < 0 and int(self.position.available_balance) < abs(self.deal_count):
            self.deal_count = int(self.position.available_balance) * -1

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
            ConditionOrder.ths_trader.deal(self.position.code, latest_price, self.deal_count)

            # 交易成功后,更新持仓信息
            if self.deal_count >= 0:  # 买入
                self.position.balance = str(int(self.position.balance) + self.deal_count)
                if self.is_hk:  # 港股通是T+0 买入当天可进行卖出
                    self.position.available_balance = str(int(self.position.available_balance) + self.deal_count)
            else:  # 卖出
                self.position.balance = str(int(self.position.balance) + self.deal_count)
                self.position.available_balance = str(int(self.position.available_balance) + self.deal_count)
            msg = f"""
            触发条件单:{self.position.code} {self.position.name}
            基准价={self.base}, 反弹幅度={self.bounce}, 方向={self.break_upward}
            极值={self.extreme_value}, 最新价={latest_price}
            """
            NetUtil.push_to_robot(msg,printLog=True)

#
# if __name__ == '__main__':
#     Condition().run(name="测试")
