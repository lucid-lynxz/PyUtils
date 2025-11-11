from dataclasses import dataclass
from typing import List, Dict


@dataclass
class MarketData:
    """
    接口文档: https://dict.thinktrader.net/nativeApi/xtdata.html#%E8%AE%A2%E9%98%85%E5%8D%95%E8%82%A1%E8%A1%8C%E6%83%85
    字段文档: https://dict.thinktrader.net/nativeApi/xtdata.html#_1m-5m-1d-k%E7%BA%BF%E6%95%B0%E6%8D%AE
    """
    time: int  # 时间戳,单位:毫秒
    open: float  # 开盘价
    high: float  # 最高价
    low: float  # 最低价
    close: float  # 收盘价
    volume: int  # 成交量
    amount: float  # 成交额
    settlement_price: float = 0.0  # 今结算
    open_interest: int = 0  # 持仓量
    dr: float = 0.0
    total_dr: float = 0.0
    pre_close: float = 0.0  # 前收价
    suspend_flag: int = 0  # 停牌标记 0 - 正常 1 - 停牌 -1 - 当日起复牌

    @classmethod
    def from_dict(cls, data: dict) -> 'MarketData':
        """Create a MarketData instance from a dictionary."""
        return cls(
            time=data['time'],
            open=round(data['open'], 2),
            high=round(data['high'], 2),
            low=round(data['low'], 2),
            close=round(data.get('close') or data.get('lastPrice'), 2),
            volume=data['volume'],
            amount=data['amount'],
            settlement_price=data['settlementPrice'],
            open_interest=data.get('openInterest', 0),  # 持仓量  subscribe_whole_quote() 没有该字段
            dr=data.get('dr', 0),  # 涨跌额  subscribe_whole_quote() 没有该字段
            total_dr=data.get('totaldr', 0),  # 累计涨跌额  subscribe_whole_quote() 没有该字段
            pre_close=data.get('preClose') or data.get('lastClose'),
            suspend_flag=data.get('suspendFlag', 0)  # 停牌标记  subscribe_whole_quote() 没有该字段
        )


@dataclass
class StockData:
    """
    Container for stock market data with stock symbol as key.
    xtdata.subscribe_quote() 或者 xtdata.subscribe_whole_quote() 返回的数据格式对象
    """
    data: Dict[str, List[MarketData]]

    @staticmethod
    def from_dict(data: dict) -> 'StockData':
        """Create a StockData instance from a dictionary."""
        converted_data = {}
        for symbol, market_data_list in data.items():
            converted_data[symbol] = [MarketData.from_dict(market_data) for market_data in market_data_list]
        result = StockData(data=converted_data)
        return result
