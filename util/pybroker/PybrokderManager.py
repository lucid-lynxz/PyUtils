import pybroker
from util.TimedStdout import TimedStdout
from util.pybroker.StrategyBrakout import StrategyBreakout
from util.pybroker.StrategyReversal import StrategyReversal
from util.pybroker.StrategyMACD import StrategyMACD
from util.pybroker.StrategyDMA import StrategyDMA

if __name__ == '__main__':
    TimedStdout.activate(True)

    init_cash: int = 100000  # 初始资金, 10w
    warmup: int = 15
    start_date = '20250101'
    end_date = '20251230'

    symbol1 = '000001.SZ'  # 平安银行  或者 000001.SZ
    symbol2 = '600000.SH'  # 浦发银行  或者 600000.SH
    symbol3 = '600580.SH'  # 卧龙电驱
    # symbol4 = '01024.HK'  # 快手-W 港股
    symbol = symbol3

    common_params = {
        'symbols': symbol,  # 股票代码, 默认为 '000001.SZ', 也可以传入多个股票代码, 如 ['000001.SZ', '000002.SZ']
        'initial_cash': init_cash,  # 初始资金
        'buy_shares': 1,  # 买入股数, 默认为0.5, 表示50%  >=1 时表示股数
        'stop_loss_pct': 0,  # 止损百分比, 10 表示 10%,大于0有效
        'stop_profit_pct': 0,  # 止盈百分比,大于0有效
        'stop_trailing_pct': 0,  # 移动止损, 最高市场价格下降N%时触发止损,大于0有效
        'start_date': start_date,  # 回测的起始日期
        'end_date': end_date  # 回测的结束日期
    }

    rate_dict: dict = {}
    # 突破策略收益率
    common_params['stop_loss_pct'] = 8
    common_params['stop_profit_pct'] = 25
    rateBreakout = (StrategyBreakout(days=11, **common_params)
                    .backtest(warmup=warmup)
                    .print_backtest_profit_info()
                    .plot_portfolio()
                    .backtest_info.profit_rate)
    rate_dict['rateBreakout'] = f'{rateBreakout * 100:.2f}%'

    # 高低点反转策略收益率
    common_params['stop_loss_pct'] = 8
    common_params['stop_profit_pct'] = 13
    rateReversal = (StrategyReversal(days=5, bounce_low=1.05, bounce_high=0.97, **common_params)
                    .backtest(warmup=warmup)
                    .print_backtest_profit_info()
                    .plot_portfolio()
                    .backtest_info.profit_rate)
    rate_dict['rateReversal'] = f'{rateReversal * 100:.2f}%'

    # MACD策略收益率
    rateMACD = (StrategyMACD(fastperiod=12, slowperiod=26, signalperiod=9, **common_params)
                .backtest(warmup=warmup)
                .print_backtest_profit_info()
                .plot_portfolio()
                .backtest_info.profit_rate)
    rate_dict['rateMACD'] = f'{rateMACD * 100:.2f}%'

    # 双均线DMA策略收益率
    rateDMA = (StrategyDMA(short_period=5, long_period=20, **common_params)
               .backtest(warmup=warmup)
               .print_backtest_profit_info()
               .plot_portfolio()
               .backtest_info.profit_rate)
    rate_dict['rateDMA'] = f'{rateDMA * 100:.2f}%'

    print(f'symbol={symbol}, 回测期间={start_date}~{end_date}, 初始资金={init_cash},收益率:\n{rate_dict}')
