from typing import List, Optional

from base.Interfaces import Runnable
from util.AkShareUtil import AkShareUtil
from util.NetUtil import NetUtil
from util.TimeUtil import TimeUtil
from util.CommonUtil import CommonUtil
from util.MailUtil import MailUtil
from util.FileUtil import FileUtil
from wool_tasks.ths_trade.bean.stock_position import StockPosition
from wool_tasks.ths_trade.ths_auto_trade import THSTrader
from wool_tasks.ths_trade.long_bridge_trade import LBTrader
from wool_tasks.ths_trade.zj_auto_trade import ZJTrader
from util.QMTUtil import QmtUtil
from util.qmt.market_bean import StockData, MarketData


class ConditionOrder(Runnable):
    """
    条件单
    """
    ths_trader: THSTrader  # 同花顺工具类,用于实现买入/卖出等操作
    long_trader: LBTrader  # 长桥工具类,用于实现买入/卖出等操作
    zj_trader: ZJTrader  # 尊嘉工具类,用于实现买入/卖出等操作
    mailUtil: MailUtil  # 邮件工具类,用于将交易结果发送到指定邮箱

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
    def by_csv_row(cls, row: List[str]):
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
            base=row[3],  # 基准价 支持两种写法, 如:0.5%~1.5%  和 0.5, 前者表示比昨收价突破0.5%以上且1.5%以下, 后者表示0.5元
            break_up=row[4].lower() in ['true', 'up'],  # 是否是向上突破基准价, 支持的格式: true/up/false/down ,忽略大小写
            bounce_info=ConditionOrder.get_or_default(row, 5, "0.4%"),  # 反弹幅度
            deal_count=int(ConditionOrder.get_or_default(row, 6, "0")),  # 交易数量
            start_time=ConditionOrder.get_or_default(row, 7, "09:30:00"),  # 每日开始监测时间
            end_time=ConditionOrder.get_or_default(row, 8, "16:30:00"),  # 每日结束监测时间
            end_date=ConditionOrder.get_or_default(row, 9, "2099-12-1"),  # 结束监测日期
        )

    @staticmethod
    def by_stop_loss(position: StockPosition, stop_loss_pct: float = 5):
        """
        止损条件单
        :param position: 持仓股票信息, 至少包含 code, name, market 和 cost_price 字段
        :param stop_loss_pct: 止损百分比, 如: 5, 表示当价格低于成本价的5%时触发止损
        :return: ConditionOrder对象
        """
        return ConditionOrder(
            position,
            base=f'{position.cost_price * (1 - stop_loss_pct / 100)}',  # 基准价 支持两种写法, 如:0.5%~1.5%  和 0.5, 前者表示比昨收价突破0.5%以上且1.5%以下, 后者表示0.5元
            break_up=False,  # 是否是向上突破基准价, 支持的格式: true/up/false/down ,忽略大小写
            bounce_info='0',  # 反弹幅度, 止损时不做反弹判断, 达到就止损
            deal_count=-position.available_balance,  # 交易数量
            start_time="09:30:00",  # 每日开始监测时间
            end_time="23:30:00",  # 每日结束监测时间
            end_date="2099-12-1",  # 结束监测日期
        )

    @staticmethod
    def by_stop_profit(position: StockPosition, stop_profit_pct: float = 10, bounce_pct: float = 0.5):
        """
        从止盈/止损/止盈止损单中读取数据, 并创建ConditionOrder对象
        :param position: 持仓股票信息, 至少包含 code, name, market 和 cost_price 字段
        :param stop_profit_pct: 止盈百分比, 如: 10, 表示当价格高于成本价的10%时触发止盈并回落bounce_pct时进行止盈
        :param bounce_pct: 止盈回落幅度百分比
        :return: ConditionOrder对象
        """
        return ConditionOrder(
            position,
            base=f'{position.cost_price * (1 + stop_profit_pct / 100)}',  # 基准价 支持两种写法, 如:0.5%~1.5%  和 0.5, 前者表示比昨收价突破0.5%以上且1.5%以下, 后者表示0.5元
            break_up=True,  # 是否是向上突破基准价, 支持的格式: true/up/false/down ,忽略大小写
            bounce_info=f'{bounce_pct}%',  # 反弹幅度, 止损时不做反弹判断, 达到就止损
            deal_count=-position.available_balance,  # 交易数量
            start_time="09:30:00",  # 每日开始监测时间
            end_time="23:30:00",  # 每日结束监测时间
            end_date="2099-12-1",  # 结束监测日期
        )

    def __init__(self, position: StockPosition,
                 base: str,
                 bounce_info: str,
                 deal_count: float,
                 break_up: bool,
                 start_time: str = '09:30:00',
                 end_time: str = '16:30:00',
                 end_date: str = '2099-12-1',
                 base_pct: bool = False):
        """
        :param position: 股票的持仓信息
        :param base: 基准价格, 支持百分比写法和纯数字写法, 比如: 0.5%~1.5%  -0.5%~-1.5%  和 0.5, 注意百分比写法时,固定小的在前
                    0.5%~1.5% 表示: 当前价格 ≥ (昨收价 * 1.005) &&  当前价格 ≤ (昨收价 * 1.015) 时触发条件单
                    -1.5%~-0.5% 表示: 当前价格 ≥ (昨收价*0.985) &&  当前价格 ≤ (昨收价 * 0.995)  时触发条件单
                    0.5 表示当价格突破0.5元时触发条件单, 此时仅正数有效, 表示突破该价格后开始监控反弹力度, 0或负数表示不设置基准价格(默认会以持仓成本价/最新价为基准)
        :param bounce_info: 表示反弹幅度, 支持两种写法, 如:0.5% 和 0.5, 前者表示反弹0.5%, 后者表示反弹0.5元
        :param deal_count: 执行交易的股数, 正数表示买入, 负数表示卖出, 如: -100 表示卖出100股
        :param break_up: true-向上突破 false-向下突破
        :start_time: 每日开始监测的时间, 默认为9:30:00开盘, 若为了减少开盘前几分钟的大波动, 可以适当后延, 若为空, 则不做判断
        :end_time: 每日结束监测的时间, 默认为16:30:00, 若为空, 则不做判断
        :end_date: 条件单截止日期(含)
        :base_pct: 基准价格是否为百分比, 默认为false, 表示基准价格为固定值, 如: 100.00, 若为true, 则表示基准价格为昨收价基础上波动的百分比, 如: 0.5%
        """
        self.active: bool = True  # 是否有效, 超期/已触发 就会变为无效
        self.hit: bool = False  # 是否已突破基准价

        self.pre_close_checked: bool = False  # 是否已使用昨收价判断是否已触发基准价
        self.position = position  # 持仓信息
        self.is_hk = self.position.is_hk_stock  # 是否为港股

        self.is_base_unit_ration: bool = '%' in base
        if self.is_base_unit_ration:
            arr = base.split('~')
            _base_lower_limit: float = float(arr[0].replace('%', '')) / 100.0
            _base_upper_limit: float = float(arr[1].replace('%', '')) / 100.0
            self.base: float = _base_lower_limit
            self.base_upper_limit: float = _base_upper_limit
        else:
            cost_price = float(self.position.cost_price)  # 持仓成本价
            _base: float = float(base)
            self.base: float = cost_price if _base <= 0 else _base  # 基准价格
            self.base_upper_limit = self.base

        self.break_upward: bool = break_up  # 突破base基准价的方向

        self.is_bounce_unit_ratio: bool = '%' in bounce_info
        _bounce: float = float(bounce_info.replace('%', ''))
        self.bounce: float = _bounce / 100.0 if self.is_bounce_unit_ratio else _bounce  # 反弹幅度

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

        # 本条件单所在的配置文件路径和行号信息, 用于触发后将对应条件单置为无效
        self.config_path: Optional[str] = None  # 配置文件路径
        self.row_number: int = -1  # 行号, 从0开始, 0表示第一行
        self.row_str: Optional[str] = None  # 原始内容

        symbol = AkShareUtil.get_full_stock_code(self.position.code, self.position.market, False)

        # CommonUtil.printLog(f'--> get_full_stock_code code={self.position.code},symbol={symbol},market={self.position.market}')

        def on_data(datas: dict):
            if not self.active:
                return

            if self.hit:
                QmtUtil().unsubscribe_quote(symbol)
                return
            if symbol in datas.keys():
                symbol_data = datas[symbol]
                last_data = symbol_data[-1] if isinstance(symbol_data, List) else symbol_data
                data = MarketData.from_dict(last_data)
                # print(f'on_data: {symbol} 最新开盘价close={data.open},收盘价close={data.close},最高价high={data.high},最低价low={data.low},last_data={last_data}')

        try:
            QmtUtil().register_callback(on_data).register_pending_subscribe_stock(symbol)
            # QmtUtil.subscribe_quote(symbol, period='1m')
        except Exception as e:
            NetUtil.push_to_robot(f'QmtUtil.subscribe_quote error for {self.position.code}: {e}')

    def use_long_bridge(self) -> bool:
        """
        是否使用长桥进行交易
        """
        return '长桥' in self.position.market

    def use_zhunjia(self) -> bool:
        """
        是否使用尊嘉app(android端)进行交易
        """
        return '尊嘉' in self.position.market

    def run(self):
        """
        使用akshare库获取最新价格,并检测是否命中条件单
        支持以下参数：
            code (str): 代码
            market_info (pd.DataFrame):其他信息, 与code不能同时为空
        """
        # 若今天不是交易日,则不做检测
        if not self.active or self.position.code.endswith('.US'):
            return

        # 先使用昨收价判断下是否已触发基准价
        if not self.pre_close_checked or self.position.prev_close <= 0.0:
            prev_close = AkShareUtil.get_prev_close(self.position.code, self.is_hk)
            self.position.prev_close = prev_close
            self.check_condition(prev_close, '昨收价')
            self.pre_close_checked = True

        # 获取最新价格
        latest_price = 0.0
        try:
            if self.position.is_hk_stock and self.long_trader is not None:
                resp = self.long_trader.quote([self.position.symbol])[0]
                latest_price = float(resp.last_done)  # 最新价
                self.position.open_price = float(resp.open)  # 开盘价
                self.position.prev_close = float(resp.prev_close)  # 昨收价
                self.position.cur_price = latest_price  # 最新价
                self.position.high_price = float(resp.high)  # 最高价
                self.position.low_price = float(resp.low)  # 最低价
                # CommonUtil.printLog(f'长桥 {self.position.code} {self.position.name} 最新价格:{latest_price}')
            else:
                # latest_price = AkShareUtil.get_latest_price(self.position.code, self.is_hk)  # 获取最新价格
                stock_min_df = AkShareUtil.get_market_data(self.position.code, self.is_hk, 20, 1)
                if not stock_min_df.empty:
                    latest_data = stock_min_df.iloc[-1:]  # 最新1min的数据, 包含开盘价,收盘价,最高价,最低价,成交量,成交额等信息
                    latest_price: float = latest_data['收盘'].iloc[-1]  # 最新价格
                    self.position.cur_price = latest_price
                    self.position.open_price = latest_data['开盘'].iloc[-1]  # 开盘价
                    self.position.high_price = latest_data['最高'].iloc[-1]  # 最高价
                    self.position.low_price = latest_data['最低'].iloc[-1]  # 最低价
                    self.position.prev_close = stock_min_df.iloc[-2]['收盘'].iloc[0]  # 昨收价
        except Exception as e:
            NetUtil.push_to_robot(f'get_latest_price error for {self.position.code}: {e}')

        # 先使用昨收价判断下是否已触发基准价
        if not self.pre_close_checked:
            self.check_condition(self.position.prev_close, '昨收价')
            self.pre_close_checked = True

        if latest_price == 0.0:
            CommonUtil.printLog(f'conditionOrder 最新价格为0,应该是获取失败了,跳过本轮检测,{self.summary_info_1line}')
            return

        self.check_condition(latest_price)

    def check_condition(self, latest_price: float, price_tip: str = '最新价'):
        """
        根据最新价格,判断条件单是否命中
        :param latest_price: 最新价格
        :param price_tip: 最新价格提示, 默认为 '最新价', 也支持 '昨收价', 其默认会在 09:32:00 之前进行判断
        """
        if not self.active or latest_price <= 0.0:
            return
        # CommonUtil.printLog(f'conditionOrder 检测条件单 {self.summary_info_1line} {price_tip}:{latest_price}')

        if not self.is_hk and not AkShareUtil.is_trading_day():
            CommonUtil.printLog(f'conditionOrder 今天不是交易日,无需检测 {self.summary_info_1line}')
            self.active = False
            return

        # 若时间不满足,则不做检测
        if (not CommonUtil.isNoneOrBlank(self.start_time) and
                not TimeUtil.is_time_greater_than(self.start_time, include_equal=True)):
            # CommonUtil.printLog(f'conditionOrder 尚未到达开始检测的时间(>={self.start_time}),本次跳过:{self.summary_info_1line},{price_tip}:{latest_price}')
            return

        if not CommonUtil.isNoneOrBlank(self.end_time) and TimeUtil.is_time_greater_than(self.end_time):
            CommonUtil.printLog(f'conditionOrder 超过检测时段内(<={self.end_time}),今日跳过:{self.summary_info_1line},{price_tip}:{latest_price}')
            self.active = False
            return

        if TimeUtil.is_time_greater_than(self.end_date):
            CommonUtil.printLog(f'conditionOrder 超过检测日期{self.end_date},不再检测 {self.summary_info_1line},{price_tip}:{latest_price}')
            self.active = False
            return

        if self.is_base_unit_ration:
            if self.position.prev_close <= 0.0:
                CommonUtil.printLog(f'conditionOrder 昨收价为0,无法计算基准价,本次跳过:{self.summary_info_1line},{price_tip}:{latest_price}')
                return
            self.base = self.position.prev_close * (1 + self.base)  # 计算基准价格
            self.base_upper_limit = self.position.prev_close * (1 + self.base_upper_limit)  # 计算基准价格上限
            self.is_base_unit_ration = False

            # 计算开盘价是否处于昨收价的指定范围
            CommonUtil.printLog(f'conditionOrder 昨收价为 {self.position.prev_close},计算后的基准价为: {self.base}, 上限价格为: {self.base_upper_limit}')
            if latest_price > self.base_upper_limit:
                CommonUtil.printLog(f'conditionOrder 最新价格{latest_price}超过上限价格:{self.base_upper_limit},本次跳过:{self.summary_info_1line},{price_tip}:{latest_price}')
                self.active = False
                return

        # 卖出股票时, 若可用余额不足,则调整为可用余额
        # 列模式识别存在误差,可能提取不到导致无法卖出,此处不做限制
        # if self.deal_count < 0 and int(self.position.available_balance) < abs(self.deal_count):
        #     self.deal_count = int(self.position.available_balance) * -1

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
                msg = f'{self.summary_info}\n首次突破基准价:{self.base},极值:{self.extreme_value},{price_tip}:{latest_price}'
                NetUtil.push_to_robot(msg, printLog=True)
                return  # 首次突破后返回, 等待下一次价格变化再做检测
            else:
                return  # 未突破基准价, 跳过本次检测

        # 达到基准价后, 检测反弹力度
        if self.break_upward:  # 向上突破
            # high_price = self.position.high_price if self.position.high_price > 0 else self.extreme_value
            # self.extreme_value = max(latest_price, self.extreme_value, high_price)
            self.extreme_value = max(latest_price, self.extreme_value)
            delta = abs(self.extreme_value - latest_price)
        else:
            # low_price = self.position.low_price if self.position.low_price > 0 else self.extreme_value
            # self.extreme_value = min(latest_price, self.extreme_value, low_price)
            self.extreme_value = min(latest_price, self.extreme_value)
            delta = abs(self.extreme_value - latest_price)

        if self.is_bounce_unit_ratio:
            expected_delta = self.extreme_value * self.bounce
        else:
            expected_delta = self.bounce

        # 反弹幅度超过预设值,触发交易
        if delta >= expected_delta:
            if delta > 3 * expected_delta or (TimeUtil.is_time_greater_than('09:32:00') and '昨收价' == price_tip):
                msg = f'{self.summary_info}\n极值:{self.extreme_value},{price_tip}:{latest_price},波动了:{delta},超过3倍反弹幅度或者昨收价超期失效,跳过本次交易'
                NetUtil.push_to_robot(msg, printLog=True)
                return

            self.active = False

            CommonUtil.printLog(f'进行交易:{self.summary_info},极值:{self.extreme_value},{price_tip}:{latest_price}, 反弹幅度:{delta}, 预设反弹幅度:{expected_delta}')
            app_name = '同花顺'
            deal_img_path: str = ''  # 交易的截图文件保存路径
            if self.use_long_bridge():
                app_name = '长桥'
                # from longport.openapi import SubmitOrderResponse
                result = self.long_trader.deal(self.position.symbol, latest_price, self.deal_count)
                success = result is not None and not CommonUtil.isNoneOrBlank(result.order_id)
            elif self.use_zhunjia():
                app_name = '尊嘉'
                # from longport.openapi import SubmitOrderResponse
                success = self.zj_trader.deal(self.position.code, latest_price, self.deal_count)
                deal_img_path = self.zj_trader.last_deal_img_path
            else:
                success = ConditionOrder.ths_trader.deal(self.position.code, latest_price, self.deal_count)
                deal_img_path = self.ths_trader.last_deal_img_path

            # 交易成功后,更新持仓信息
            if success:
                if self.deal_count >= 0:  # 买入
                    self.position.balance = str(self.position.balance + self.deal_count)
                    if self.is_hk:  # 港股通是T+0 买入当天可进行卖出
                        self.position.available_balance = str(self.position.available_balance + self.deal_count)
                else:  # 卖出
                    self.position.balance = str(self.position.balance + self.deal_count)
                    self.position.available_balance = str(self.position.available_balance + self.deal_count)

            msg = f'{self.summary_info}\n极值:{self.extreme_value},{price_tip}:{latest_price}\n进行deal操作:{success} by {app_name}'
            NetUtil.push_to_robot(msg, printLog=True)

            # 将交易结果发送到指定邮箱
            if not CommonUtil.isNoneOrBlank(deal_img_path) and self.mailUtil is not None:
                self.mailUtil.obtainMailMsg(True)  # 清空邮件内容
                # 正文中插入图片, 测试后,该文件不会再显示再附件中(qq邮箱)
                # 1. 添加图片附件
                cid = self.mailUtil.addAttachFile(deal_img_path, "image")
                # 2. 插入image标签
                self.mailUtil.setMailMsg('<html><body><h1>imgName:%s</h1>' % deal_img_path +
                                         '<p><img src="cid:%s"></p>' % cid, subject=f'{FileUtil.getFileName(deal_img_path)[0]}')
                # 发送到指定邮箱
                senderrs = self.mailUtil.sendTo()
                NetUtil.push_to_robot(f'发送邮件结果:{senderrs}\ndeal_img_path={deal_img_path}', printLog=True)

            # 将条件单配置文件中的对应项置为无效
            if success and not CommonUtil.isNoneOrBlank(self.config_path) and self.row_number >= 0:
                lines = FileUtil.readFile(self.config_path)
                if self.row_number < len(lines):
                    line_str = lines[self.row_number]
                    cur_line_str = f'# {line_str}'
                    lines[self.row_number] = cur_line_str

                    write_success = FileUtil.write2File(self.config_path, ''.join(lines))
                    msg = f'将条件单配置文件中的对应项置为无效,写入结果:{write_success},行号:{self.row_number},内容:"{self.row_str}",文件路径:{self.config_path}\noriLine={line_str}'
                    NetUtil.push_to_robot(msg, printLog=True)
