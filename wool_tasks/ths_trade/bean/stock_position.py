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
    balance: float = 0  # 股票余额 int 表示多少股
    available_balance: float = 0  # 可用余额 int 表示多少股

    # 价格信息
    cost_price: float = 0.0  # 成本价 float
    market_price: float = 0.0  # 市价 float
    market: str = ''  # 交易市场, 若希望使用非同花顺软件进行交易,请在market信息中包含对应软件名 比如: '长桥'  '尊嘉' 等
    # 以上数据是来自于同花顺的持仓数据截图ocr结果

    # 以下涨跌停价等信息是从akshare获取的数据
    prev_close: float = 0.0  # 昨收价,用作第一次条件单触发时的基准价判断
    open_price: float = 0.0  # 今日开盘价
    cur_price: float = 0.0  # 当前价格
    high_price: float = 0.0  # 最高价
    low_price: float = 0.0  # 最低价
    limit_up_price: float = 0.0  # 涨停价
    limit_down_price: float = 0.0  # 跌停价
    lot_size: int = 0  # 最小交易单位, 比如 100股, 1手等, 0表示未知, 主要用于港美股

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

    # 列模式识别时,各列的做优偏移量,具体请根据 wool_tasks\ths_trade\cache\*_ocr_grid_view_{列名}.png 效果进行微调
    title_expend_dict = {
        'code': {
            'right': 0
        },
        'name': {
            'left': 18,
            'right': 8
        },
        'balance': {
            'left': 0,
            'right': 4
        },
        'available_balance': {
            'left': 0,
            'right': 6
        },
        # 'cost_price': {
        #     'left': 0,
        #     'right': 0
        # },
        'market_price': {
            'left': 12,
            'right': 24
        },
        'market': {
            'left': 9,
            'right': 9
        }
    }

    def has_balance(self) -> bool:
        """是否有持仓"""
        return self.balance > 0

    @property
    def is_hk_stock(self) -> bool:
        """是否是港股"""
        return '港股' in self.market or 'HK' in self.market or '香港' in self.market

    # 计算属性
    @property
    def profit_loss(self) -> float:
        """计算盈亏金额"""
        return (self.market_price - self.cost_price) * self.balance

    @property
    def profit_loss_ratio(self) -> float:
        """计算盈亏比例（百分比）"""
        if self.cost_price == 0:
            return 0.0
        return (self.market_price - self.cost_price) / self.cost_price * 100

    @property
    def market_value(self) -> float:
        """计算市值"""
        return self.market_price * self.balance

    @staticmethod
    def has_valid_suffix(symbol: str) -> bool:
        """检测股票代码是否已包含市场前后缀"""
        _prefix_list = ['SH', 'SZ', 'BJ', 'HK', 'US']
        for prefix in _prefix_list:
            if symbol.startswith(prefix) or symbol.endswith(f'.{prefix}'):
                return True
        return False

    @property
    def symbol(self):
        if StockPosition.has_valid_suffix(self.code):
            return self.code
        if self.is_hk_stock:
            return f'{self.code}.HK'
        elif '上海' in self.market:
            return f'{self.code}.SH'
        elif '深圳' in self.market:
            return f'{self.code}.SZ'
        elif 'US' in self.market:
            return f'{self.code}.US'
        return self.code

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

    def copy_from(self, source):
        """复制源对象的属性值"""
        for field in source.__dataclass_fields__:
            if hasattr(self, field):
                # name/code/cur_price/market_price 已在外部进行校正和更新, 无需从持仓界面获取, ocr可能不够准确
                if (field in ['name', 'code', 'market']) and getattr(self, field) != '':
                    continue
                # if field in ['market_price', 'cur_price'] and getattr(self, field) != 0.0:
                #     continue
                setattr(self, field, getattr(source, field))
        return self
