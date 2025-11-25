from xtquant import xtdata
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from typing import List, Optional, Union, Callable, Dict
from typing_extensions import Self
from util.TimeUtil import TimeUtil
from util.qmt.market_bean import StockData, MarketData
from util.CommonUtil import CommonUtil, singleton


@singleton
class QmtUtil:
    """
    miniQM%量化工具类, 提供一些常用的工具函数, 单例默默是
    创建对象: qmt_util = QmtUtil()
    注册行情数据获取回调函数: qmt_util.register(on_data_callback)
    立即订阅单股行情: qmt_util.subscribe_quote(stock_code, period='1d', start_time='', end_time='')
    立即订阅多股行情: qmt_util.subscribe_whole_quote(code_list)
    添加待订阅的股票: qmt_util.register_pending_subscribe_stock(stock_code)
    开始订阅所有待订阅的股票: qmt_util.start_subscribe()
    """

    # 创建交易回调类对象，并声明接收回调
    class MyXtQuantTraderCallback(XtQuantTraderCallback):
        def on_connected(self):
            pass

    def __init__(self, print_log: bool = False, activate: bool = True, userdata_mini_path: str = None):
        self.on_data_callback_list: List[Callable[[Dict], None]] = []
        self._monitor_code_set = set()  # 已订阅的股票代码集合, 用于去重
        self.print_log: bool = print_log  # 是否打印 on_data 回调
        self.activate: bool = activate  # 是否可用, 启用后才能收到回调信息
        self._pending_subscribe_stock_set = set()  # 待订阅的股票代码集合, 用于去重

        self.xt_trader: Union[XtQuantTrader, None] = None  # 交易对象
        self.trader_callback = self.MyXtQuantTraderCallback()  # 创建交易回调类对象
        self.update_user_data_mini_path(userdata_mini_path)

    def update_user_data_mini_path(self, userdata_mini_path: str) -> Self:
        """
        https://dict.thinktrader.net/nativeApi/xttrader.html#%E5%88%9B%E5%BB%BAapi%E5%AE%9E%E4%BE%8B
        """
        # if not CommonUtil.isNoneOrBlank(userdata_mini_path):
        #     # session_id为会话编号，策略使用方对于不同的Python策略需要使用不同的会话编号
        #     self.xt_trader = XtQuantTrader(userdata_mini_path, TimeUtil.currentTimeMillis())
        #     self.xt_trader.register_callback(self._default_on_data)
        #     self.xt_trader.start()  # 启动交易线程，准备交易所需的环境
        #     connect_result = self.xt_trader.connect()  # 连接MiniQMT, 连接结果信息，连接成功返回0，失败返回非0
        #     CommonUtil.printLog(f'connect_result={connect_result}')
        return self

    def _default_on_data(self, datas: dict):
        if not self.activate:
            # CommonUtil.printLog(f'_default_on_data fail as not activate')
            return

        if self.print_log:
            CommonUtil.printLog(f'{QmtUtil._TAG} _default_on_data: {datas}')

        for callback in self.on_data_callback_list:
            callback(datas)

    def register_callback(self, on_data_callback: Callable[[Dict], None]) -> Self:
        """
        注册数据回调函数
        """
        self.on_data_callback_list.append(on_data_callback)
        return self

    def register_pending_subscribe_stock(self, stock_code: str) -> Self:
        """
        注册待订阅的股票代码, 最终在触发 start_subscribe() 时订阅
        """
        self._pending_subscribe_stock_set.add(stock_code)
        return self

    def toggle_activate(self, activate: bool = True) -> Self:
        self.activate = activate
        return self

    def toggle_print_log(self, print_log: bool = True) -> Self:
        self.print_log = print_log
        return self

    def start_subscribe(self) -> Self:
        """
        开始订阅所有待订阅的股票代码
        """
        CommonUtil.printLog(f'QmtUtil start_subscribe: {self._pending_subscribe_stock_set}')
        if len(self._pending_subscribe_stock_set) > 0:
            try:
                self.subscribe_whole_quote(list(self._pending_subscribe_stock_set))
            except Exception as e:
                CommonUtil.printLog(f'QmtUtil start_subscribe fail: {e}')
                self.toggle_activate(False)
        return self

    def unsubscribe_quote(self, stock_code: Union[str, List]) -> Self:
        """反订阅"""
        CommonUtil.printLog(f'QmtUtil unsubscribe_quote({stock_code})')
        r_list = [stock_code] if isinstance(stock_code, str) else stock_code
        xtdata.unsubscribe_quote(r_list)
        for code in r_list:
            if code in self._monitor_code_set:
                self._monitor_code_set.remove(code)
        return self

    def subscribe_quote(self, stock_code: str, period: str = '1d', start_time: str = '', end_time: str = '') -> int:
        """
        订阅单股行情
        https://dict.thinktrader.net/nativeApi/xtdata.html#%E8%AE%A2%E9%98%85%E5%8D%95%E8%82%A1%E8%A1%8C%E6%83%85
        参数:
        stock_code - string 合约代码, 比如: '600580.SH'
        period - string 周期: 1d  1m  5m
        start_time - string 起始时间(含), 示例: 20251110
        end_time - string 结束时间(含), 若日期为空,则表示当前
        count - int 数据个数, -1表示返回所有数据
        callback - 数据推送回调
        回调定义形式为on_data(datas)，回调参数datas格式为 { stock_code : [data1, data2, ...] }
        def on_data(datas: dict):
            if symbol in datas.keys():
                symbol_data = datas[symbol]
                last_data = symbol_data[-1] if isinstance(symbol_data, List) else symbol_data
                data = MarketData.from_dict(last_data)
                print(f'on_data: 最新开盘价close={data.open},收盘价close={data.close},最高价high={data.high},最低价low={data.low},last_data={last_data}')
        """
        if not self.activate:
            CommonUtil.printLog(f'subscribe_quote({stock_code}) fail: self.activate is False')
            return -1

        if stock_code in self._monitor_code_set:
            CommonUtil.printLog(f'subscribe_quote fail:{stock_code} has subscribed')
            return -1

        self._monitor_code_set.add(stock_code)
        req_id = xtdata.subscribe_quote(stock_code, period=period, start_time=start_time, end_time=end_time, count=-1, callback=self._default_on_data)
        CommonUtil.printLog(f'QmtUtil subscribe_quote({stock_code}, {period}) req_id={req_id}')
        return req_id

    def subscribe_whole_quote(self, code_list: List[str]) -> int:
        """
        返回指定股票的实时数据
        https://dict.thinktrader.net/nativeApi/xtdata.html#%E8%AE%A2%E9%98%85%E5%85%A8%E6%8E%A8%E8%A1%8C%E6%83%85
        参数:
        code_list - string 合约代码列表, 比如: ['600580.SH', '300001.SZ']
        callback - 数据推送回调
        回调定义形式为on_data(datas)，回调参数datas格式为 { stock_code : data }
        def on_data(datas: dict):
            if symbol in datas.keys():
                symbol_data = datas[symbol]
                last_data = symbol_data[-1] if isinstance(symbol_data, List) else symbol_data
                data = MarketData.from_dict(last_data)
                print(f'on_data: 最新开盘价close={data.open},收盘价close={data.close},最高价high={data.high},最低价low={data.low},last_data={last_data}')
        """
        if not self.activate:
            CommonUtil.printLog(f'QmtUtil subscribe_whole_quote({code_list}) fail: self.activate is False')
            return -1

        # 保留不在 _monitor_code_set 中的元素
        result_code_list = [x for x in code_list if x not in self._monitor_code_set]
        if len(result_code_list) == 0:
            CommonUtil.printLog(f'QmtUtil subscribe_whole_quote fail:{code_list} has subscribed')
            return -1

        self._monitor_code_set.update(result_code_list)
        req_id = xtdata.subscribe_whole_quote(result_code_list, callback=self._default_on_data)
        CommonUtil.printLog(f'QmtUtil subscribe_whole_quote({result_code_list}) req_id={req_id}')
        return req_id


if __name__ == '__main__':
    symbol = '09988.HK'  # 阿里巴巴-W
    symbol1 = '301200.SZ'  # 大族数控
    symbol2 = '600580.SH'  # 卧龙电驱


    def on_data(datas: dict):
        CommonUtil.printLog(f'on_data: datas={datas}')
        if symbol in datas.keys():
            symbol_data = datas[symbol]
            last_data = symbol_data[-1] if isinstance(symbol_data, List) else symbol_data
            data = MarketData.from_dict(last_data)
            CommonUtil.printLog(f'on_data: {symbol} 最新开盘价close={data.open},收盘价close={data.close},最高价high={data.high},最低价low={data.low},last_data={last_data}')


    qmtUtil = QmtUtil(True)
    qmtUtil.register_callback(on_data)
    # (qmtUtil.register_pending_subscribe_stock(symbol)
    #  .register_pending_subscribe_stock(symbol1)
    #  .register_pending_subscribe_stock(symbol2)
    #  .start_subscribe())

    # num = qmtUtil.subscribe_quote(symbol, start_time='20251110')
    # CommonUtil.printLog(f'num1={num}')
    TimeUtil.sleep(2)

    # num = qmtUtil.subscribe_quote(symbol, period='1m', start_time='20251111093000', end_time='')
    # CommonUtil.printLog(f'\n\nnum2={num}')
    # TimeUtil.sleep(2)

    # num = qmtUtil.subscribe_whole_quote([symbol, symbol1])
    # num = qmtUtil.subscribe_whole_quote(['09868.HK', '01024.HK', '00700.SZ', '09988.HK', '02097.HK'])
    num = qmtUtil.subscribe_whole_quote(['09988.HK', '301200.SZ', '600580.SH'])
    # CommonUtil.printLog(f'\n\nnum3={num}')
    TimeUtil.sleep(5)
