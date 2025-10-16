import pybroker
from pybroker import ExecContext

from util.pybroker.base_strategy import BaseStrategy


class StrategyScore(BaseStrategy):
    """
    单因子策略: 根据指定的单因子排序,买入前n名
    """

    def __init__(self, score_property: str = 'pe', score_threshold: float = 100, larger: bool = True, **kwargs):
        super().__init__(**kwargs)
        pybroker.register_columns(score_property)
        self.score_property: str = score_property  # 单因子名称
        self.score_threshold: float = score_threshold  # 单因子阈值, 大于等于该值的才执行交易
        self.larger: bool = larger  # 单因子是否为大因子, 大因子: 大于等于阈值的买入, 小因子: 小于等于阈值的买入
        self.description = f'{score_property}单因子排序策略'

    def buy_func(self, ctx: ExecContext) -> None:
        pos = ctx.long_pos()  # 获取当前的长期持有的股票

        # 使用 getattr 动态获取属性，而不是使用下标
        score_property_value = getattr(ctx, self.score_property, None)
        if score_property_value is None:
            raise ValueError(f"Property '{self.score_property}' not found in ExecContext")

        score = score_property_value[-1]
        valid = score >= self.score_threshold if self.larger else score <= self.score_threshold
        if not pos and valid:  # 因子值符合阈值条件时买入
            self.update_buy_shares(ctx)
            self.update_stop_info(ctx)
