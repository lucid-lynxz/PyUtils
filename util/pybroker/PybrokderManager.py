import concurrent.futures
import os
import subprocess
import sys
from typing import Dict, List, Tuple, Type, Any, Optional

import matplotlib.pyplot as plt
from typing_extensions import Self

from util.FileUtil import FileUtil
from util.ImageUtil import ImageUtil
from util.TimedStdout import TimedStdout
from util.pybroker.StrategyBrakout import StrategyBreakout
from util.pybroker.StrategyDMA import StrategyDMA
from util.pybroker.StrategyMACD import StrategyMACD
from util.pybroker.StrategyReversal import StrategyReversal
from util.pybroker.base_strategy import BackTestInfo


class StrategyManager:
    """
    策略管理器，用于并行执行多个交易策略并收集结果
    """

    def __init__(self, init_cash: int = 100000,  # 初始资金
                 buy_shares: float = -1,  # 每只股票妈单次买入股数, 默认-1会根据传入的股票数均分, 比如共2只股票回测,则每只份额0.5, 表示50%  >=1 时表示股数
                 stop_loss_pct: float = 0,  # 止损百分比, 10 表示 10%,大于0有效
                 stop_profit_pct: float = 0,  # 止盈百分比,大于0有效
                 stop_trailing_pct: float = 0,  # 移动止损, 最高市场价格下降N%时触发止损,大于0有效
                 warmup: int = 15,
                 enable_plot: bool = True,  # 是否允许绘制回测结果
                 start_date: str = '20250101',  # 回测的起始日期
                 end_date: str = '20251230'  # 回测的结束日期
                 ):
        """
        初始化策略管理器
        :param init_cash: 初始资金
        :param warmup: 预热期
        :param start_date: 回测开始日期
        :param end_date: 回测结束日期
        """
        TimedStdout.activate(True)
        self.init_cash = init_cash
        self.warmup = warmup
        self.start_date = start_date
        self.end_date = end_date
        self.enable_plot = enable_plot
        self.common_params = {
            'initial_cash': init_cash,
            'buy_shares': buy_shares,
            'stop_loss_pct': stop_loss_pct,
            'stop_profit_pct': stop_profit_pct,
            'stop_trailing_pct': stop_trailing_pct,
            'start_date': start_date,
            'end_date': end_date
        }

        self.strategies: List[Tuple[Type, Dict[str, Any]]] = []
        self.results: Dict[str, Optional[BackTestInfo]] = {}
        self._all_completed = False  # 添加完成标志

        self._plot_figures = []  # 保存所有图形对象
        # 设置非交互式后端
        plt.switch_backend('Agg')

    def _show_plot(self, fig):
        """在主线程中显示图形"""
        self._plot_figures.append(fig)
        # plt.show()

    def add_strategy(self, strategy_class: Type, **kwargs) -> Self:
        """
        添加策略到执行列表
        :param strategy_class: 策略类
        :param kwargs: 策略参数, 其中必传 'symbols' 表示要回测的股票代码, 支持列表或者单个字符串
        """
        symbols = kwargs.get('symbols')
        if not symbols:
            raise ValueError("Symbols must be provided for the strategy.")
        if isinstance(symbols, str):
            symbols = [symbols]

        if self.common_params['buy_shares'] <= 0:
            self.common_params['buy_shares'] = 1 / len(symbols)

        params = {**self.common_params, **kwargs}
        self.strategies.append((strategy_class, params))
        print(f"add_strategy: {strategy_class.__name__} with symbols: {symbols}, params: {params}")
        return self

    def _run_strategy(self, strategy_class: Type, params: Dict[str, Any]) -> Optional[BackTestInfo]:
        """
        执行单个策略
        :param strategy_class: 策略类
        :param params: 策略参数
        :return: 策略收益率等信息
        """
        strategy_instance = strategy_class(**params)
        result = (strategy_instance
                  .backtest(warmup=self.warmup)
                  .print_backtest_profit_info()
                  .plot_portfolio(condition=self.enable_plot)
                  .backtest_info)

        # 保存图形文件路径
        if hasattr(strategy_instance, 'plot_figure'):
            self._plot_figures.append(strategy_instance.plot_figure)
        return result

    def run_all_strategies(self, max_workers: int = 4) -> Dict[str, Optional[BackTestInfo]]:
        """
        并行执行所有策略
        :param max_workers: 最大线程数
        :return: 策略结果字典
        """
        self.results.clear()  # 清空之前的结果
        self._all_completed = False  # 重置完成标志
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_strategy = {
                executor.submit(self._run_strategy, strategy_class, params): strategy_class.__name__
                for strategy_class, params in self.strategies
            }

            for future in concurrent.futures.as_completed(future_to_strategy):
                strategy_name = future_to_strategy[future]
                try:
                    result = future.result()
                    self.results[f'{strategy_name}'] = result
                except Exception as exc:
                    print(f'{strategy_name} generated an exception: {exc}')
        self._all_completed = True  # 设置完成标志
        return self.results

    def print_results(self) -> Self:
        """
        打印策略执行结果
        """
        if not self._all_completed:
            print("Warning: Not all strategies have completed execution!")
            return self

        print(f'{self.results}')
        return self

    def wait_for_completion(self) -> Self:
        """
        等待所有策略执行完成
        """
        while not self._all_completed:
            continue
        return self

    def show_all_plots(self) -> Self:
        """使用系统默认程序打开所有图形文件"""
        cache_path = FileUtil.create_cache_dir(None, __file__, True, f'plots_temp')
        cnt = len(self._plot_figures)
        for plot_file in self._plot_figures:
            full_name, _, _ = FileUtil.getFileName(plot_file)
            FileUtil.copy(plot_file, f'{cache_path}/{full_name}')

        cols: int = 1 if cnt <= 1 else 2
        rows: int = 1 if cnt <= 1 else int(cnt / 2)
        image = ImageUtil.merge_images(cache_path, rows=rows, cols=cols)
        FileUtil.createFile(cache_path, True)
        image_path = FileUtil.recookPath(f'{cache_path}/merged_image.jpg')
        ImageUtil.save_img(image_path, image)

        if os.path.exists(image_path):
            os_name = os.name
            if os_name == 'nt':  # Windows
                os.startfile(image_path)
            elif os_name == 'posix':  # macOS/Linux
                subprocess.run(['open', image_path] if sys.platform == 'darwin' else ['xdg-open', image_path])
        return self


if __name__ == '__main__':
    # TimedStdout.activate(True)

    init_cash: int = 100000  # 初始资金, 10w
    warmup: int = 15
    start_date = '20250101'
    end_date = '20251230'

    symbol1 = '000001.SZ'  # 平安银行  或者 000001.SZ
    symbol2 = '600000.SH'  # 浦发银行  或者 600000.SH
    symbol3 = '600580.SH'  # 卧龙电驱
    # symbol4 = '01024.HK'  # 快手-W 港股
    symbol = symbol3

    # 创建策略管理器实例
    manager = StrategyManager(init_cash=100000, warmup=15,
                              start_date=start_date, end_date=end_date)

    # 添加策略
    manager.add_strategy(StrategyBreakout, symbols=symbol, days=11, stop_loss_pct=8, stop_profit_pct=25)
    manager.add_strategy(StrategyReversal, symbols=symbol, days=5, bounce_low=1.05, bounce_high=0.97, stop_loss_pct=8, stop_profit_pct=13)
    manager.add_strategy(StrategyMACD, symbols=symbol, fastperiod=12, slowperiod=26, signalperiod=9)
    manager.add_strategy(StrategyDMA, symbols=symbol, short_period=5, long_period=20)

    # 执行所有策略
    manager.run_all_strategies()

    # 打印结果并显示图形
    manager.print_results().show_all_plots()

    # common_params = {
    #     'symbols': symbol,  # 股票代码, 默认为 '000001.SZ', 也可以传入多个股票代码, 如 ['000001.SZ', '000002.SZ']
    #     'initial_cash': init_cash,  # 初始资金
    #     'buy_shares': 1,  # 买入股数, 默认为0.5, 表示50%  >=1 时表示股数
    #     'stop_loss_pct': 0,  # 止损百分比, 10 表示 10%,大于0有效
    #     'stop_profit_pct': 0,  # 止盈百分比,大于0有效
    #     'stop_trailing_pct': 0,  # 移动止损, 最高市场价格下降N%时触发止损,大于0有效
    #     'start_date': start_date,  # 回测的起始日期
    #     'end_date': end_date  # 回测的结束日期
    # }
    #
    # rate_dict: dict = {}
    # # 突破策略收益率
    # common_params['stop_loss_pct'] = 8
    # common_params['stop_profit_pct'] = 25
    # rateBreakout = (StrategyBreakout(days=11, **common_params)
    #                 .backtest(warmup=warmup)
    #                 .print_backtest_profit_info()
    #                 .plot_portfolio()
    #                 .backtest_info.profit_rate)
    # rate_dict['rateBreakout'] = f'{rateBreakout * 100:.2f}%'
    #
    # # 高低点反转策略收益率
    # common_params['stop_loss_pct'] = 8
    # common_params['stop_profit_pct'] = 13
    # rateReversal = (StrategyReversal(days=5, bounce_low=1.05, bounce_high=0.97, **common_params)
    #                 .backtest(warmup=warmup)
    #                 .print_backtest_profit_info()
    #                 .plot_portfolio()
    #                 .backtest_info.profit_rate)
    # rate_dict['rateReversal'] = f'{rateReversal * 100:.2f}%'
    #
    # # MACD策略收益率
    # rateMACD = (StrategyMACD(fastperiod=12, slowperiod=26, signalperiod=9, **common_params)
    #             .backtest(warmup=warmup)
    #             .print_backtest_profit_info()
    #             .plot_portfolio()
    #             .backtest_info.profit_rate)
    # rate_dict['rateMACD'] = f'{rateMACD * 100:.2f}%'
    #
    # # 双均线DMA策略收益率
    # rateDMA = (StrategyDMA(short_period=5, long_period=20, **common_params)
    #            .backtest(warmup=warmup)
    #            .print_backtest_profit_info()
    #            .plot_portfolio()
    #            .backtest_info.profit_rate)
    # rate_dict['rateDMA'] = f'{rateDMA * 100:.2f}%'
    #
    # print(f'symbol={symbol}, 回测期间={start_date}~{end_date}, 初始资金={init_cash},收益率:\n{rate_dict}')
