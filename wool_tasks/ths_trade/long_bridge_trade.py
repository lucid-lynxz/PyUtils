import os
import traceback
from decimal import Decimal
from typing import List, Type, Optional, Union

from longport.openapi import Config, QuoteContext, SubType, SecurityQuote, OrderType, OrderSide, TimeInForceType, SecurityStaticInfo, PushQuote
from longport.openapi import TradeContext, OrderDetail, OrderStatus, OpenApiException

from util.CommonUtil import CommonUtil
from util.ConfigUtil import NewConfigParser
from util.FileUtil import FileUtil
from util.NetUtil import NetUtil
from util.TimeUtil import TimeUtil
from wool_tasks.ths_trade.bean.stock_position import StockPosition


class LBTrader(object):
    """
    长桥证券接口交易工具类
    只支持港股/美股, 且要有对应行情权限
    api权限申请: https://open.longportapp.com/
    api文档: https://open.longportapp.com/zh-CN/docs
    sdk安装: https://open.longportapp.com/sdk    pip install longport
    apiKey/token/secret 的配置文档: https://open.longportapp.com/zh-CN/docs/getting-started
    """

    def __init__(self, config_path: str = None, cacheDir: str = None):
        """
        :param config_path: 配置文件路径, 若为空,则会依次尝试使用 {cacheDir}/config.ini 或者 当前目录下的 config.ini 文件
        :param cacheDir: 缓存目录, 默认为当前目录下的 cache 目录
        """
        if CommonUtil.isNoneOrBlank(cacheDir):
            cacheDir = FileUtil.create_cache_dir(None, __file__, clear=False)

        # 配置文件解析器
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = f'{cacheDir}/config.ini' if CommonUtil.isNoneOrBlank(config_path) else config_path
        if not FileUtil.isFileExist(config_path):
            config_path = FileUtil.recookPath(f'{cur_dir}/config.ini')

        configParser = NewConfigParser(allow_no_value=True).initPath(config_path)
        lb_settings = configParser.getSectionItems('LongBridge')

        self.app_key = lb_settings.get('app_key')
        self.app_secret = lb_settings.get('app_secret')
        self.access_token = lb_settings.get('access_token')
        self.expire_day = lb_settings.get('expire_day')

        self.auto_stop: bool = lb_settings.get('auto_stop', 'True') == 'True'  # 是否允许自动止盈止损
        self.stop_loss_pct: float = float(lb_settings.get('stop_loss_pct', '5'))  # 止损比例, 默认5, 表示5%, >0 有效
        self.stop_profit_pct: float = float(lb_settings.get('stop_profit_pct', '8'))  # 止盈比例, 默认8, 表示8%, >0 有效
        self.bounce_pct: float = float(lb_settings.get('bounce_pct', '0.5'))  # 止盈回落比例,默认0.5%, 当止盈触发后, 若价格回落超过此比例, 则会触发止损

        self.order_detail_dict: dict[str, OrderDetail] = {}  # 订单详情信息, key-订单id, value-订单详情

        # token过期提醒: https://open.longportapp.com/zh-CN/account
        fmt = '%Y-%m-%d'
        today = TimeUtil.getTimeStr(fmt)
        dif_day = TimeUtil.dateDiff(today, self.expire_day, fmt)
        # print(f'dif_day={dif_day}')
        if dif_day >= -3:
            NetUtil.push_to_robot(f'长桥证券api参数将于 {self.expire_day} 过期, 请及时更新')

        self.active = (not CommonUtil.isNoneOrBlank(self.app_key)
                       and not CommonUtil.isNoneOrBlank(self.app_secret)
                       and not CommonUtil.isNoneOrBlank(self.access_token))

        if not self.active:
            CommonUtil.printLog('长桥证券初始化失败, 请检查配置文件')
            return

        # 从系统环境变量中获取app_key等参数
        # config = Config.from_env()
        config = Config(app_key=self.app_key,
                        app_secret=self.app_secret,
                        access_token=self.access_token,
                        http_url='https://openapi.longportapp.cn',
                        quote_ws_url='wss://openapi-quote.longportapp.cn',
                        trade_ws_url='wss://openapi-trade.longportapp.cn')

        # 获取资产总览: https://open.longportapp.com/zh-CN/docs/getting-started#%E5%9C%BA%E6%99%AF%E7%A4%BA%E8%8C%83
        try:
            self.tradeCtx = TradeContext(config)
            resp = self.tradeCtx.account_balance()
            CommonUtil.printLog(resp)

            # 订阅行情
            self.quoteCtx = QuoteContext(config)

            # 获取持仓信息
            self.stock_positions: Union[dict[str, StockPosition], None] = None
            self.get_stock_position()

        except Exception as e:
            NetUtil.push_to_robot(f'长桥证券初始化失败, 请检查配置文件, 错误信息: {e}')
            self.active = False

    def set_on_subscribe(self, listener):
        """
        行情订阅回调函数, 比如:
        def on_quote(symbol: str, quote: PushQuote):
            # 注意: 若subscribe时传入的symbol前缀是0, 回调时, 0会被删除
            print(symbol, quote)
        """
        CommonUtil.printLog(f'set_on_subscribe({listener})')
        self.quoteCtx.set_on_quote(listener)

    def subscribe(self, symbols: List[str], sub_types: List[Type[SubType]], is_first_push: bool = False) -> 'LBTrader':
        """
        订阅指定标的实时行情, 会不断回调 on_quote 函数
        :param symbols: 标的代码列表,比如: ["700.HK", "AAPL.US", "TSLA.US", "NFLX.US"]
        :param sub_types: 订阅类型列表, 比如:  [SubType.Quote]
        :param is_first_push: 是否立即推送当前数据
        """
        CommonUtil.printLog(f'subscribe({symbols},{sub_types},{is_first_push})')
        self.quoteCtx.subscribe(symbols, sub_types, is_first_push)
        return self

    def quote(self, symbols: List[str]) -> List[SecurityQuote]:
        """
        查询指定标的实时行情, 只希望获取最新价格的话, 使用 get_latest_price 函数
        https://open.longportapp.com/zh-CN/docs/quote/pull/quote
        :param symbols: 标的代码列表,比如: ["700.HK", "AAPL.US", "TSLA.US", "NFLX.US"]
        :return:
        """
        try:
            return self.quoteCtx.quote(symbols)
        except Exception as e:
            CommonUtil.printLog(f'quote Exception:{e}, symbols: {symbols}')
            traceback.print_exc()
            return []

    def get_latest_price(self, symbols: list[str]) -> list[float]:
        """
        获取最新价格
        :param symbols: 股票代码列表, 比如: ['700.HK', 'AAPL.US', 'TSLA.US', 'NFLX.US']
        :return: 最新价格列表, 比如: [56.25, 180.0, 720.0, 500.0]
        """
        return [float(item.last_done) for item in self.quote(symbols)]

    def static_info(self, symbols: List[str]) -> List[SecurityStaticInfo]:
        """
        获取标的基础信息, 比如每手股票数量等
        https://open.longportapp.com/zh-CN/docs/quote/pull/static
        :param symbols: 标的代码列表,比如: ["700.HK", "AAPL.US", "TSLA.US", "NFLX.US"]
        :return:
        """
        return self.quoteCtx.static_info(symbols)

    def deal(self, symbol: str, price: float, amount: float):
        """
        买卖股票
        文档: https://open.longportapp.com/zh-CN/docs/trade/order/submit
        :param symbol: 股票代码, 比如: '700.HK'
        :param price: 价格, 大于0有效, 若传入 <=0 的值, 则表示使用软件提供的买卖价进行交易, 一般卖出操作时, 会使用买一价, 买入操作时,使用卖一价
        :param amount: 数量,单位:股,  正数表示买入, 负数表示卖出
        :return SubmitOrderResponse 类型

        可能的报错:
        longport.OpenApiException: OpenApiException: (code=602001, trace_id=f7bf2eb409b2605ad23ebe3730253c68) The submitted quantity does not comply with the required multiple of the lot size
        --> 这个表示下单数量不符合该股票的最低下单量, 可通过 self.quoteCtx.static_info([f'{code}'])[0].lot_size 来获取该股票的每手数量
        """
        try:
            order_type = OrderType.MO if price <= 0 else OrderType.LO  # M0: 市价单  L0:限价单 选哟传递价格
            order_side = OrderSide.Buy if amount > 0 else OrderSide.Sell  # 买入:Buy  卖出:Sell
            submitted_price = None if price <= 0 else Decimal(price)
            _resp = self.tradeCtx.submit_order(symbol, order_type, order_side, Decimal(abs(amount)),
                                               TimeInForceType.Day, submitted_price, remark='deal from python sdk')
            NetUtil.push_to_robot(f'长桥 deal({symbol},{price},{amount})={_resp}')
            return _resp
        except Exception as e:
            NetUtil.push_to_robot(f'长桥 deal({symbol},{price},{amount}) fail: {e}')
            traceback.print_exc()
            return None

    def get_stock_position(self, symbols: Optional[List[str]] = None, force: bool = True) -> dict[str, StockPosition]:
        """
        获取取股票持仓
        https://open.longportapp.com/zh-CN/docs/trade/asset/stock
        StockPositionsResponse { channels: [StockPositionChannel { account_channel: "lb", positions: [StockPosition { symbol: "TSM.US", symbol_name: "Taiwan Semiconductor", quantity: 4, available_quantity: 4, currency: "USD", cost_price: 284.610, market: US, init_quantity: Some(4) }, StockPosition { symbol: "CRCL.US", symbol_name: "Circle", quantity: 2, available_quantity: 2, currency: "USD", cost_price: 125.280, market: US, init_quantity: Some(2) }, StockPosition { symbol: "BIDU.US", symbol_name: "Baidu", quantity: 8, available_quantity: 8, currency: "USD", cost_price: 131.769, market: US, init_quantity: Some(8) }, StockPosition { symbol: "2050.HK", symbol_name: "SANHUA", quantity: 400, available_quantity: 400, currency: "HKD", cost_price: 34.795, market: HK, init_quantity: Some(400) }, StockPosition { symbol: "1211.HK", symbol_name: "BYD COMPANY", quantity: 200, available_quantity: 200, currency: "HKD", cost_price: 101.100, market: HK, init_quantity: Some(400) }, StockPosition { symbol: "1024.HK", symbol_name: "KUAISHOU-W", quantity: 200, available_quantity: 200, currency: "HKD", cost_price: 67.100, market: HK, init_quantity: Some(0) }] }] }
        Name	Type	Required	Description
        list	object[]	false	股票持仓信息
        ∟ account_channel	string	true	账户类型
        ∟ stock_info	object[]	false	股票列表
        ∟∟ symbol	string	true	股票代码
        ∟∟ symbol_name	string	true	股票名称
        ∟∟ quantity	string	true	持仓股数
        ∟∟ available_quantity	string	false	可用股数
        ∟∟ currency	string	true	币种
        ∟∟ market	string	true	市场
        ∟∟ cost_price	string	true	成本价格 (具体根据客户端选择平均买入还是摊薄成本)
        ∟∟ init_quantity	string	false	开盘前初始持仓
        """
        if not force and self.stock_positions is not None:
            return self.stock_positions

        resp = self.tradeCtx.stock_positions(symbols)
        # CommonUtil.printLog(f'ori get_stock_position{symbols})={resp}')
        result = {}
        for channel in resp.channels:
            for position in channel.positions:
                s_position = StockPosition()
                s_position.code = position.symbol
                s_position.name = position.symbol_name
                s_position.balance = float(position.quantity)
                s_position.available_balance = float(position.available_quantity)
                s_position.cost_price = float(position.cost_price)
                s_position.market = f'{position.market}_长桥'
                result[position.symbol] = s_position
        self.stock_positions = result
        return result

    def get_order_detail(self, order_id: str, enable_from_cache: bool = False, print_log: bool = False) -> Union[OrderDetail, None]:
        """
        获取订单详情
        https://open.longportapp.com/zh-CN/docs/trade/order/order_detail
        @param order_id: 订单id
        @param enable_from_cache: 是否从缓存中获取
        @param print_log: 是否打印日志
        """
        if enable_from_cache and order_id in self.order_detail_dict:
            return self.order_detail_dict[order_id]

        resp = self.tradeCtx.order_detail(order_id)
        success = LBTrader.is_order_success(resp)
        CommonUtil.printLog(f'get_order_detail({order_id}) success={success},detail={resp}', print_log)
        self.order_detail_dict[order_id] = resp
        return resp

    @staticmethod
    def is_order_success(order: Union[OrderDetail, None]) -> bool:
        """
        订单是否执行成功
        """
        return order is None or order.status == OrderStatus.Filled

    @staticmethod
    def is_order_fail(order: Union[OrderDetail, None]) -> bool:
        """
        订单是否明确执行失败(不包括未提交等尚未执行状态)
        Rejected已拒绝   Expired已过期
        """
        return order is not None and order.status in [OrderStatus.Rejected, OrderStatus.Expired]

    def cancel_order(self, order_id: str) -> bool:
        """
        撤销订单
        https://open.longportapp.com/zh-CN/docs/trade/order/withdraw
        """
        result = False
        msg = ''
        try:
            self.tradeCtx.cancel_order(order_id)
            result = True
        except Exception as e:
            # OpenApiException(601011, '599f1dd826d5f0d619a68a9b745bf41d', 'Order has been cancelled.')
            # OpenApiException: (code=603301, trace_id=5d80ea709416b4766d9499ebecdb2494) The symbol currently does not support short selling.
            if isinstance(e, OpenApiException):
                result = e.code == 601011  # order has been cancelled
                result = result or e.code == 603301  # 已经清仓,然后又有条件单触发进行卖出,被系统认为是做空
                msg = f',{e.message}'
            else:
                msg = f',Exception:{e}'

        detail = self.get_order_detail(order_id)

        order_info = '' if detail is None else f'\n原订单信息: {detail.side} {detail.stock_name} {detail.quantity}股,价格:{detail.price}元 {detail.status}\n{detail.msg}'
        NetUtil.push_to_robot(f'cancel_order({order_id})={result}{msg}{order_info.strip()}')
        return result


if __name__ == '__main__':
    trader = LBTrader()
    CommonUtil.printLog(f'>>>>>>>>>>>>>>>>>>>>')

    # symbols = ["700.HK", "AAPL.US", "TSLA.US", "NFLX.US"]
    symbols = ["1810.HK", "09868.HK"]  # 1810 小米集团 09868 小鹏汽车


    def on_quote(symbol_quote: str, quote_item: PushQuote):
        CommonUtil.printLog(f'--> on_quote {symbol_quote}, {quote_item}', False)


    trader.set_on_subscribe(on_quote)

    # trader.set_on_subscibe(lambda symbol, quote: print(symbol, quote))
    trader.subscribe(symbols=symbols, sub_types=[SubType.Quote], is_first_push=True)

    # resp = trader.get_latest_price(symbols)
    # CommonUtil.printLog(f'最新价格: {resp}')
    #
    # resp = trader.quote(symbols)
    # CommonUtil.printLog(f'行情: {resp}')
    # TimeUtil.sleep(10)
    #
    # resp = trader.static_info(symbols)
    # CommonUtil.printLog(resp)

    # resp = trader.deal('1810.HK', 56.25, 200)
    # CommonUtil.printLog(resp)

    CommonUtil.printLog(f'trader.get_stock_position()={trader.get_stock_position()}')

    trader.get_order_detail('1177783233673199616')
    trader.get_order_detail('1177436536254267392')
    trader.cancel_order('1177783233673199616')
    trader.cancel_order('1177436536254267392')

    TimeUtil.sleep(3)
