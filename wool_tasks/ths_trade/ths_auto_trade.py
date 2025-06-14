# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import sys

from airtest.core.api import *

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)
from wool_tasks.base_airtest_4_windows_impl import BaseAir4Windows
from wool_tasks.ths_trade.stock_position import StockPosition
from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil
from util.TimeUtil import TimeUtil, log_time_consume
from util.AkShareUtil import AkShareUtil


class THSTrader(BaseAir4Windows):
    """
    基于同花顺的 下单 窗口, 进行持仓股票价格监控, 进行条件单设置(主要是港股通股票)
    同花顺常用快捷键:
        买入: F1
        卖出: F2
        撤单: F3
        查询: F4
        持仓: F6
        成交: F7
        委托: F8
    """

    def __init__(self, cacheDir: str = ''):
        """
        :param cacheDir: 缓存目录, 默认为当前目录下的 cache 目录
        """
        cacheDir = THSTrader.create_cache_dir() if CommonUtil.isNoneOrBlank(cacheDir) else cacheDir
        FileUtil.delete_files_by_extensions(cacheDir, ['.png', '.jpg'])
        AkShareUtil.cache_dir = cacheDir  # akShare的缓存目录
        super().__init__(window_title='网上股票交易系统', cacheDir=cacheDir)

        self.position_dict: dict = dict()  # 持仓信息字典, key值是股票代码, value值是 StockPosition 对象, 通过 get_stock_position() 方法获取

        # 刷新按钮坐标/持仓列表矩形框坐标
        self.refresh_pos: tuple = None  # 刷新按钮中心点坐标
        self.position_rect: tuple = None  # 持仓列表矩形框坐标(含标题行),依次是: 左边界x, 上边界y, 右边界x, 下边界y

        # 买入/卖出 输入框坐标
        self.bs_code_pos: tuple = None  # 买入/卖出 界面中的 '股票代码' 中心点坐标偏移得到的输入框坐标
        self.bs_price_pos: tuple = None  # 买入/卖出 界面中的 '价格' 中心点坐标偏移得到的输入框坐标
        self.bs_amount_pos: tuple = None  # 买入/卖出 界面中的 '数量' 中心点坐标偏移得到的输入框坐标
        self.bs_rest_btn: tuple = None  # 买入/卖出 界面中的 '重填' 按钮中心点坐标
        self.bs_confirm_btn: tuple = None  # 买入/卖出 界面中的 '买入/卖出' 确定按钮中心点坐标
        self.akshare_util: AkShareUtil = AkShareUtil()  # akshare 工具类

        # 尝试从缓存文件中读取数据
        self.pos_cache_file = f'{cacheDir}/pos_cache.txt'  # 缓存各按钮位置信息, 对于同一台设备, 不需要每次都重新获取
        line_list = FileUtil.readFile(self.pos_cache_file)
        for line in line_list:
            # 分离属性名和属性值
            key, pos_str = line.split(':')
            # 将属性值按逗号分割并转换为元组
            pos_tuple = tuple(map(int, pos_str.split(',')))
            # 将元组赋值给对象对应的属性
            setattr(self, key, pos_tuple)

    def save_pos_info(self):
        """将已找到的各控件位置信息保存到缓存文件中"""
        with open(self.pos_cache_file, 'w') as file:
            for attr_name in dir(self):
                attr_value = getattr(self, attr_name)
                if isinstance(attr_value, tuple):
                    file.write(f"{attr_name}:{','.join(map(str, attr_value))}\n")

    def toggle_window_mode(self, mode: int = 3):
        """
        修改窗口模式
        :param mode: 窗口模式, 3代表最大化 2最小化
        """
        import ctypes
        user32 = ctypes.windll.user32
        user32.ShowWindow(int(self.uuid), mode)
        sleep(0.5)

    def _find_bs_pos(self, ocr_result: list):
        """
        查找买入/卖出界面的各输入框坐标
        :param ocr_result: 之前全屏ocr结果对象
        """

        input_delta = (100, 0)
        pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '证券代码', prefixText='卖出股票',
                                                                subfixText='重填')
        self.bs_code_pos = self.calcCenterPos(pos, input_delta)  # 证券代码输入框位置
        CommonUtil.printLog(f'证券代码输入框位置: {self.bs_code_pos}')

        pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '卖出价格', prefixText='卖出股票',
                                                                subfixText='重填')
        self.bs_price_pos = self.calcCenterPos(pos, input_delta)  # 股票价格输入框
        CommonUtil.printLog(f'股票价格输入框: {self.bs_price_pos}')

        pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '卖出数量', prefixText='可用余额',
                                                                subfixText='重填')
        self.bs_amount_pos = self.calcCenterPos(pos, input_delta)  # 股票数量价格输入框, 单位: 股
        CommonUtil.printLog(f'股票数量价格输入框: {self.bs_amount_pos}')

        pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '重填', prefixText='卖出数量',
                                                                subfixText='卖出')
        self.bs_rest_btn = self.calcCenterPos(pos)  # 重填按钮
        CommonUtil.printLog(f'重填按钮: {self.bs_rest_btn}')

        pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '卖出', prefixText='重填',
                                                                subfixText='涨停|持仓|股票余额')
        self.bs_confirm_btn = self.calcCenterPos(pos)  # 确定 买入/卖出 按钮
        CommonUtil.printLog(f'买入/卖出 按钮: {self.bs_confirm_btn}')

    @log_time_consume()
    def get_stock_position(self) -> list:
        """
        获取所有股票的持仓信息列表, 每隔元素表示一个股票对象

        可以使用以下方法将list转为dict, key值是股票代码
        result_dict = {objDict.code: objDict for objDict in stock_position_list}

        :return: 股票列表,元素是 StockPosition 对象
        """
        # 持仓信息列表头目前从左到右, 依次是: 证券代码 证券名称 股票余额 可用余额 冻结数量 成本价 市价 盈亏盈亏比(%) 当日盈亏 当日盈亏比(%) 市值 仓位占比(%) 当日买入 当日卖出 交易市场
        # 因此此处通过 '证券代码' 和 '仓位参比'  两个字符串的位置, 来确定持仓信息(含标题含)的左/上/右边界, 然后根据坐标, 按行提取股票持仓信息
        # 另外比如港股股票代码签名可能有其他表示信息, 因此左边界适当往左便宜一点
        if self.position_rect is None:
            self.key_press('F2')  # '卖出[F2]'
            self.key_press('F6')  # '持仓[F6]'
            self.toggle_window_mode(3)  # 最大化窗口
            self.saveImage(self.snapshot(), "持仓信息总览", autoAppendDateInfo=True)

            pos, ocrResStr, ocrResList = self.findTextByOCR('证券代码', img=self.snapshot_img, prefixText='持仓',
                                                            subfixText='可用余额')
            CommonUtil.printLog(f'证券代码中心点坐标: {self.calcCenterPos(pos)}')
            # CommonUtil.printLog(f'\n\nocrResStr: {ocrResStr}')

            pos_left = pos[0][0] - 20  # 左边界往左偏移20像素
            pos_top = pos[0][1]  # 左上角y值,向下偏移一点

            pos, _, _ = self.findTextByCnOCRResult(ocrResList, '交易市场', prefixText='成本价')
            pos_right = pos[1][0] + 20  # 右边界往右偏移20像素
            w, h = self.getWH()
            pos_bottom = h - 70
            self.position_rect = pos_left, pos_top, pos_right, pos_bottom

            # 查找 买入/卖出 输入框的位置
            self._find_bs_pos(ocrResList)

            # 将位置信息缓存到文件中
            self.save_pos_info()
        else:
            self.refresh()  # 刷新数据
            self.snapshot()  # 重新截图

        full_img = self.crop_img(self.snapshot_img, fromX=self.position_rect[0], fromY=self.position_rect[1],
                                 toX=self.position_rect[2], toY=self.position_rect[3])
        dictList = self.ocr_grid_view(full_img, StockPosition.title_key_dict, True)

        # 同花顺港股代码前面会有个图形,可能会被识别为:  营/雪 等字体, 需要删除
        del_index_list = list()
        for i in range(len(dictList)):
            objDict = dictList[i]
            if CommonUtil.isNoneOrBlank(objDict.get('code', '')) or CommonUtil.isNoneOrBlank(objDict.get('name', '')):
                del_index_list.append(i)
                continue

        for index in reversed(del_index_list):
            del dictList[index]

        result = list()
        for i in range(len(dictList)):
            stock_position = StockPosition(**dictList[i])
            result.append(stock_position)
            # 由于解析区域可能包含了空白区域, 因此对于code或name为空的股票, 需要进行删除
            if stock_position.is_hk_stock:
                stock_position['code'] = stock_position['code'][1:]
        CommonUtil.printLog(f'持仓StockPositionList: {result}')
        self.position_dict = {objDict.code: objDict for objDict in result}
        return result

    def refresh(self):
        """
        刷新当前界面
        """
        if self.refresh_pos is None:
            pos, ocrResStr, ocrResList = self.findTextByOCR('刷新', prefixText='登录', subfixText='系统', width=500,
                                                            height=200, saveAllImages=True, imgPrefixName='refresh')
            # CommonUtil.printLog(f'刷新pos:{pos}')
            # CommonUtil.printLog(f'刷新ocrResList:{ocrResList}')
            self.refresh_pos = self.calcCenterPos(pos)
        touch(self.refresh_pos)
        sleep(0.5)

    @log_time_consume(separate=True)
    def deal(self, code: str, price: float, amount: float) -> bool:
        """
        买卖股票
        :param code: 股票代码
        :param price: 价格
        :param amount: 数量,单位:股,  正数表示买入, 负数表示卖出
        """
        buy = amount > 0  # true-买入 false-卖出
        if CommonUtil.isNoneOrBlank(self.position_dict):
            self.get_stock_position()

        position: StockPosition = self.position_dict[code]
        if position is None:
            CommonUtil.printLog(f'股票代码:{code} 不存在持仓信息,买卖失败')
            return False

        # 卖出时, 不能超过当前可卖数量
        # todo 买入时,不能超过当前可买最大数量
        if buy:
            self.key_press('F1')  # '买入[F1]'
            pass
        else:
            self.key_press('F2')  # '卖出[F2]'
            amount = min(amount, int(position.available_balance))

        if amount <= 0:
            CommonUtil.printLog(f'交易股票:{position.name}({code}) 可买卖数量为0,交易失败')
            return False

        touch(self.bs_rest_btn)  # 重填按钮
        touch(self.bs_code_pos)  # 证券代码输入框
        text(code)  # 输入股票代码

        # todo 价格不能超过涨跌停价, 建议找其他接口直接获取而不是截图进行ocr势必诶
        touch(self.bs_price_pos)  # 买入/卖出价格输入框 会选择小数部分
        # keyevent("A", modifiers=["CTRL"])  # 全选无效
        self.key_press('BACKSPACE', 6)  # 通过回退键来清除
        text(str(price))  # 输入卖出价格

        touch(self.bs_amount_pos)  # 买入/卖出数量输入框
        text(str(amount))  # 输入数量

        # 点击 买入/卖出 按钮后, 默认会有个确认弹框, 建议在设置中禁止二次确认
        touch(self.bs_confirm_btn)  # 确定 买入/卖出 按钮
        # win.find_element("窗口标题", "Button", "按钮名称").click()
        # win.find_element(None, "Button", None, "btn_id").click()
        CommonUtil.printLog(f'交易股票:{position.name}({code}) 价格:{price} 数量:{amount}')
        return True

    def cancel_order(self, code: str):
        """
        撤单
        :param code: 股票代码
        """
        self.key_press('F2')  # '卖出[F2]'
        self.key_press('F8')  # '委托[F8]'
        # todo ocr委托页面数据, 找到要撤单的单子, 然后双击进行撤单

    @staticmethod
    def create_cache_dir(clear: bool = False) -> str:
        """
        在当前文件同级目录下创建一个缓存目录
        :param 是否每次都清空目录
        :return: 缓存目录路径
        """
        return FileUtil.create_cache_dir(None, __file__, clear=clear)


if __name__ == '__main__':
    AkShareUtil.cache_dir = THSTrader.create_cache_dir()  # 缓存目录
    stock_code = '000001'  # 股票代码
    name = AkShareUtil.get_stock_name(stock_code)
    print(f'股票代码{stock_code}对应的名称是:{name}')

    # 测试获取股票信息
    stock_summary = AkShareUtil.get_stock_summary(stock_code)
    print(stock_summary)

    full_code = AkShareUtil.get_full_stock_code(stock_code)
    print(f'\nfull_code={full_code}')

    price = AkShareUtil.get_latest_price(stock_code)
    print(f'股票最新价格:{price}')

    price = AkShareUtil.get_latest_price('09988', True)
    print(f'港股09988(阿里巴巴)最新价格:{price}')

    # df = AkShareUtil.get_stock_summary(stock_code)
    # print(f'\nstock_summary1:{df}')
    #
    # df = AkShareUtil.get_stock_summary(stock_code)
    # # print(f'\nstock_summary2:{df}')
    #
    # print(f"\n涨停:{df[df['item'] == '涨停']['value'].iloc[0]}")
    # print(f"\n跌停:{df[df['item'] == '跌停']['value'].iloc[0]}")
    #
    # print(f'今日是否可交易:{AkShareUtil.is_today_can_trade()}')

    # trader = THSTrader()
    # stock_position_list = trader.get_stock_position()
    # #
    # stock = trader.position_dict.get('09988', None)
    # CommonUtil.printLog(f'09988阿里巴巴-W持仓信息持仓信息:{stock}', prefix='\n')
    #
    # stock = trader.position_dict.get('603333', None)
    # CommonUtil.printLog(f'603333尚纬股份持仓信息:{stock}', prefix='\n')
    #
    # trader.deal('600536', 48.0, -100)  # 卖出
    # trader.saveImage(trader.snapshot(), "卖出股票", autoAppendDateInfo=True)

    # trader.deal('603333', 3.0, 100)  # 买入100股
    # trader.saveImage(trader.snapshot(), "买入股票", autoAppendDateInfo=True)
