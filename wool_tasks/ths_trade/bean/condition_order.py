from typing import List

from base.Interfaces import Runnable
from util.AkShareUtil import AkShareUtil
from util.NetUtil import NetUtil
from util.TimeUtil import TimeUtil
from util.CommonUtil import CommonUtil
from wool_tasks.ths_trade.bean.stock_position import StockPosition
from wool_tasks.ths_trade.ths_auto_trade import THSTrader
from wool_tasks.ths_trade.long_bridge_trade import LBTrader


class ConditionOrder(Runnable):
    """
    条件单
    """
    ths_trader: THSTrader  # 同花顺工具类,用于实现买入/卖出等操作
    long_trader: LBTrader  # 长桥工具类,用于实现买入/卖出等操作

    @staticmethod
    def get_or_default(data: List[str], index: int, def_value: str):
        """
        从列表获取指定序号的元素, 若不存在(None或者""),则返回默认值
        """
        _size = len(data)
        if index >= _size:
            return def_value
        if CommonUtil.isNoneOrBlank(data[index]):
            return def_value
        return data[index]

    @classmethod
    def from_csv_row(cls, row: List[str]):
        """
        从csv文件中读取一行数据, 并创建ConditionOrder对象
        :param row: csv文件中的行数据,
                    格式: 股票代码,股票名称,交易市场,基准价,向上突破(true/false/up/down),反弹幅度,交易股数,每日开始监测时间,每日结束监测时间,结束监测的日期
                    其中  '交易市场' 支持: 'A股'/'港股通'/'港股'/'美股', 其中港股/美股 会使用尊嘉等交易软件, A股/港股通则使用同花顺
                    '每日开始监测时间' 和 '每日结束监测时间' : 若放空,则表示不做判断, 否则超出检测时间范围的,今日失效,明日重新检测
                    '向上突破': 表示是否时线上突破基准价, 支持的格式: true/false/up/down ,忽略大小写, true/up 表示线上突破基准价   false/down 表示向下突破基准价
                    '交易股数' 非0时才会发起交易, 若时0,则只做监控, 触发条件时发出通知
        :return: ConditionOrder对象
        """
        return ConditionOrder(
            StockPosition(
                code=row[0],  # 股票代码
                name=row[1],  # 名称
                market=row[2]),  # 交易市场
            base=float(row[3]),  # 基准价
            break_up=row[4].lower() in ['true', 'up'],  # 是否是向上突破基准价, 支持的格式: true/up/false/down ,忽略大小写
            bounce_info=ConditionOrder.get_or_default(row, 5, "0.4%"),  # 反弹幅度
            deal_count=int(ConditionOrder.get_or_default(row, 6, "0")),  # 交易数量
            start_time=ConditionOrder.get_or_default(row, 7, "09:30:00"),  # 每日开始监测时间
            end_time=ConditionOrder.get_or_default(row, 8, "16:30:00"),  # 每日结束监测时间
            end_date=ConditionOrder.get_or_default(row, 9, "2099-12-1"),  # 结束监测日期
        )

    def __init__(self, position: StockPosition,
                 base: float,
                 bounce_info: str,
                 deal_count: int,
                 break_up: bool,
                 start_time: str = '09:30:00',
                 end_time: str = '16:30:00',
                 end_date: str = '2099-12-1'):
        """
        :param position: 股票的持仓信息
        :param base: 基准价格, 正数有效, 表示突破该价格后开始监控反弹力度, 0或负数表示不设置基准价格(默认会以持仓成本价/最新价为基准)
        :param bounce_info: 表示反弹幅度, 支持两种写法, 如:0.5% 和 0.5, 前者表示反弹0.5%, 后者表示反弹0.5元
        :param deal_count: 执行交易的股数, 正数表示买入, 负数表示卖出, 如: -100 表示卖出100股
        :param break_up: true-向上突破 false-向下突破
        :start_time: 每日开始监测的时间, 默认为9:30:00开盘, 若为了减少开盘前几分钟的大波动, 可以适当后延, 若为空, 则不做判断
        :end_time: 每日结束监测的时间, 默认为16:30:00, 若为空, 则不做判断
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

        self.deal_count = deal_count  # 执行交易时买卖的股数, 负数表示卖出 0只做监控, 发出通知,不触发交易
        self.start_time: str = start_time
        self.end_time = end_time
        self.end_date: str = end_date  # 条件单截止日期(含)

        self.summary_info = f"""{self.position.code} {self.position.name}({self.position.market})\n基准:{self.base}, 幅度:{self.bounce}, 方向:{'向上' if self.break_upward else '向下'},数量:{self.deal_count}"""
        self.summary_info_1line = self.summary_info.replace('\n', ' ').strip()

    def run(self):
        """
        使用akshare库获取最新价格,并检测是否命中条件单
        支持以下参数：
            code (str): 代码
            market_info (pd.DataFrame):其他信息, 与code不能同时为空
        """
        # 若今天不是交易日,则不做检测
        if not self.active:
            return

        # 获取最新价格
        if self.position.is_hk_stock and self.long_trader is not None:
            resp = self.long_trader.quote([f'{self.position.code}.HK'])[0]
            latest_price = float(resp.last_done)  # 最新价
            self.position.open_price = float(resp.open)  # 开盘价
            # CommonUtil.printLog(f'长桥 {self.position.code} {self.position.name} 最新价格:{latest_price}')
        else:
            latest_price = AkShareUtil.get_latest_price(self.position.code, self.is_hk)  # 获取最新价格
        if latest_price == 0.0:
            CommonUtil.printLog(f'conditionOrder 最新价格为0,应该是获取失败了,跳过本轮检测,{self.summary_info_1line}')
            return

        self.check_condition(latest_price)

    def check_condition(self, latest_price: float):
        """
        根据最新价格,判断条件单是否命中
        :param latest_price: 最新价格
        """
        if not self.active:
            return

        if not self.is_hk and not AkShareUtil.is_trading_day():
            CommonUtil.printLog(f'conditionOrder 今天不是交易日,无需检测 {self.summary_info_1line}')
            self.active = False
            return

        # 若时间不满足,则不做检测
        if (not CommonUtil.isNoneOrBlank(self.start_time) and
                not TimeUtil.is_time_greater_than(self.start_time, include_equal=True)):
            CommonUtil.printLog(
                f'conditionOrder 尚未到达开始检测的时间(>={self.start_time}),本次跳过:{self.summary_info_1line}')
            return

        if not CommonUtil.isNoneOrBlank(self.end_time) and TimeUtil.is_time_greater_than(self.end_time):
            CommonUtil.printLog(
                f'conditionOrder 超过检测时段内(<={self.end_time}),今日跳过:{self.summary_info_1line}')
            self.active = False
            return

        if TimeUtil.is_time_greater_than(self.end_date):
            CommonUtil.printLog(f'conditionOrder 超过检测日期{self.end_date},不再检测 {self.summary_info_1line}')
            self.active = False
            return

        # 卖出股票时, 若可用余额不足,则调整为可用余额
        if self.deal_count < 0 and int(self.position.available_balance) < abs(self.deal_count):
            self.deal_count = int(self.position.available_balance) * -1

        self.position.cur_price = latest_price  # 当前价格

        # 若基准价为0,则优先使用成本价替代, 若无成本价,则使用最新价
        if self.base <= 0:
            self.base = latest_price

        # 判断是否已达到了基准价
        if not self.hit:
            if self.break_upward and latest_price >= self.base:
                self.hit = True
            elif not self.break_upward and latest_price <= self.base:
                self.hit = True

            if self.hit:
                msg = f'{self.summary_info}\n首次突破基准价:{self.base},最新:{latest_price}'
                NetUtil.push_to_robot(msg, printLog=True)

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
            success = ConditionOrder.ths_trader.deal(self.position.code, 0, self.deal_count)

            # 交易成功后,更新持仓信息
            if success:
                if self.deal_count >= 0:  # 买入
                    self.position.balance = str(self.position.balance + self.deal_count)
                    if self.is_hk:  # 港股通是T+0 买入当天可进行卖出
                        self.position.available_balance = str(self.position.available_balance + self.deal_count)
                else:  # 卖出
                    self.position.balance = str(self.position.balance + self.deal_count)
                    self.position.available_balance = str(self.position.available_balance + self.deal_count)
            msg = f'{self.summary_info}\n极值:{self.extreme_value},最新:{latest_price}\n进行deal操作:{success}'
            NetUtil.push_to_robot(msg, printLog=True)
