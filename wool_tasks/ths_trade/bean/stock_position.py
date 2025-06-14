# !/usr/bin/env python3
# -*- coding:utf-8 -*-

from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class StockPosition:
    """股票持仓信息数据类"""

    # 基础信息
    code: str = ''  # 股票代码
    name: str = ''  # 股票名称

    # 数量信息
    balance: str = '0'  # 股票余额 int 表示多少股
    available_balance: str = '0'  # 可用余额 int 表示多少股

    # 价格信息
    cost_price: str = '0.0'  # 成本价 float
    market_price: str = '0.0'  # 市价 float
    market: str = ''  # 交易市场
    # 以上数据是来自于同花顺的持仓数据截图ocr结果

    # 以下涨跌停价等信息是从akshare获取的数据
    limit_up_price: float = 0.0  # 涨停价
    limit_down_price: float = 0.0  # 跌停价
    cur_price: float = 0.0  # 当前价格

    # 相关字段在 同花顺 持仓列表中的名称及对应于本类的字段名, 若value为空,表示本类不包含该信息, 无需存储
    # 默认顺序: 证券代码  证券名称  股票余额  可用余额  冻结数量  成本价  市价  盈亏  盈亏比(%)  当日盈亏  当日盈亏比(%)  市值  仓位占比(%)  当日买入  当日卖出  交易市场 持股天数
    # 可用右键标题行, 隐藏不必要的列, 比如我只保留以下字段, 隐藏呢: 冻结数量/当日盈亏/当日盈亏比(%)/当日买入/当日卖出
    # 证券代码  证券名称  股票余额  可用余额  成本价  市价  盈亏  盈亏比(%)  市值  仓位占比(%)  交易市场 持股天数
    # 请使用python3.7以上的版本, 保证是按顺序存储的, 第一个元素和最后一个元素用于确定列表区域, 一遍从 snapshot 全屏截图中裁切出列表区域子截图
    title_key_dict = {
        '证券代码': 'code',
        '证券名称': 'name',
        '股票余额': 'balance',
        '可用余额': 'available_balance',
        # '冻结数量': None,
        '成本价': 'cost_price',
        '市价': 'market_price',
        # '盈亏': None,
        # '盈亏比': None,
        # '当日盈亏': None,
        # '当日盈亏比': None,
        # '市值': None,
        # '仓位占比': None,
        # '当日买入': None,
        # '当日卖出': None,
        '交易市场': "market"
    }

    @property
    def is_hk_stock(self) -> bool:
        """是否是港股"""
        return '港股通' in self.market or '沪HK' in self.market or '深HK' in self.market or '香港' in self.market

    # 计算属性
    @property
    def profit_loss(self) -> float:
        """计算盈亏金额"""
        return (float(self.market_price) - float(self.cost_price)) * int(self.balance)

    @property
    def profit_loss_ratio(self) -> float:
        """计算盈亏比例（百分比）"""
        if self.cost_price == 0:
            return 0.0
        return (float(self.market_price) - float(self.cost_price)) / float(self.cost_price) * 100

    @property
    def market_value(self) -> float:
        """计算市值"""
        return float(self.market_price) * int(self.balance)

    # 显示方法
    def __str__(self) -> str:
        """格式化显示持仓信息"""
        return (
            f"股票: {self.name}({self.code})\n"
            f"余额: {self.balance}, 可用: {self.available_balance}\n"
            f"成本价: {self.cost_price}, 市价: {self.market_price}\n"
            f"盈亏: {self.profit_loss:.2f}, 盈亏比: {self.profit_loss_ratio:.2f}%\n"
            f"市值: {self.market_value:.2f}, 港股: {self.is_hk_stock}"
        )

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)


# 使用示例
if __name__ == "__main__":
    position = StockPosition(
        code="000001",
        name="平安银行",
        balance=1000,
        available_balance=800,
        frozen_quantity=200,
        cost_price=15.25,
        market_price=16.80
    )

    print(position)
