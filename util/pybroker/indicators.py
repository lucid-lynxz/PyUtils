import pybroker
import talib
from pybroker.indicator import highest, lowest, Indicator
from typing import Union, Tuple


def generate_sma_indicator(timeperiod: int, name: str = None) -> pybroker.indicator:
    """
    生成指定时间周期的均线指标
    :param timeperiod: 时间周期,比如5, 表示5日均线
    :param name: 指标名称, 默认为 sma{timeperiod}
    :return: 均线指标
    """
    name = name or f'sma{timeperiod}'
    return pybroker.indicator(name, lambda data: talib.SMA(data.close, timeperiod=timeperiod))


def generate_macd_indicator(fastperiod: int = 12, slowperiod: int = 26, signalperiod: int = 9) -> Tuple[pybroker.indicator, pybroker.indicator]:
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

    def _calc_macd(data):
        return talib.MACD(data.close, fastperiod=fastperiod, slowperiod=slowperiod, signalperiod=signalperiod)

    dif = pybroker.indicator('dif', lambda data: _calc_macd(data)[0])  # 快线
    dea = pybroker.indicator('dea', lambda data: _calc_macd(data)[1])  # 慢线
    return dif, dea


def generate_highest_lowest_indicator(period: int) -> Tuple[pybroker.indicator, pybroker.indicator]:
    """
    计算指定周期内的最高价和最低价
    :param period: 时间周期,比如5, 表示5日
    :return: 最高价和最低价指标, 名称分别为: high_5day, low_5day
    """
    return highest(f'high_{period}day', 'high', period), lowest(f'low_{period}day', 'low', period)


# 均线指标
sma5 = generate_sma_indicator(5)
sma10 = generate_sma_indicator(10)
sma20 = generate_sma_indicator(20)
sma60 = generate_sma_indicator(60)

# macd 快线dif 和 慢线dea
dif, dea = generate_macd_indicator()
