# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import sys
from typing import Optional

from airtest.core.api import *

from util.NetUtil import NetUtil

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)
from wool_tasks.base_airtest_4_windows_impl import BaseAir4Windows
from wool_tasks.ths_trade.bean.stock_position import StockPosition

from util.CommonUtil import CommonUtil, catch_exceptions
from util.FileUtil import FileUtil
from util.TimeUtil import log_time_consume
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
            if CommonUtil.isNoneOrBlank(pos_str):
                continue
            # 将属性值按逗号分割并转换为元组
            pos_tuple = tuple(map(int, map(float, pos_str.split(','))))
            # 将元组赋值给对象对应的属性
            setattr(self, key, pos_tuple)

    def save_pos_info(self):
        """将已找到的各控件位置信息保存到缓存文件中"""
        with open(self.pos_cache_file, 'w') as file:
            for attr_name in dir(self):
                attr_value = getattr(self, attr_name)
                if isinstance(attr_value, tuple):
                    file.write(f"{attr_name}:{','.join(map(str, attr_value))}\n")

    @catch_exceptions(max_retries=1, retry_interval=5)
    def toggle_window_mode(self, mode: int = 3):
        """
        修改窗口模式
        :param mode: 窗口模式, 3代表最大化 2最小化
        """
        import ctypes
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow(int(self.uuid))  # 将其切换到前台
        user32.ShowWindow(int(self.uuid), mode)  # 最大/最小化窗口
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

    last_msg: str = ''

    @log_time_consume()
    def get_all_stock_position(self) -> list:
        """
        获取所有股票的持仓信息列表, 每隔元素表示一个股票对象

        可以使用以下方法将list转为dict, key值是股票代码
        result_dict = {objDict.code: objDict for objDict in stock_position_list}

        :return: 股票列表,元素是 StockPosition 对象
        """
        # 持仓信息列表头目前从左到右, 依次是: 证券代码 证券名称 股票余额 可用余额 冻结数量 成本价 市价 盈亏盈亏比(%) 当日盈亏 当日盈亏比(%) 市值 仓位占比(%) 当日买入 当日卖出 交易市场
        # 因此此处通过 '证券代码' 和 '仓位参比'  两个字符串的位置, 来确定持仓信息(含标题含)的左/上/右边界, 然后根据坐标, 按行提取股票持仓信息
        # 另外比如港股股票代码签名可能有其他表示信息, 因此左边界适当往左便宜一点
        CommonUtil.printLog(f'get_all_stock_position')
        self.key_press('F2')  # '卖出[F2]'
        self.key_press('F6')  # '持仓[F6]'
        self.toggle_window_mode(3)  # 最大化窗口

        if self.position_rect is None:
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

        # 转换数据类型
        for item in dictList:
            item['market_price'] = CommonUtil.parse_number(item['market_price'], float, 0)
            item['cost_price'] = CommonUtil.parse_number(item['cost_price'], float, 0)
            item['balance'] = CommonUtil.parse_number(item['balance'], int, 0)
            item['available_balance'] = CommonUtil.parse_number(item['available_balance'], int, 0)

        result = list()
        for i in range(len(dictList)):
            stock_position = StockPosition(**dictList[i])
            result.append(stock_position)
            # 由于解析区域可能包含了空白区域, 因此对于code或name为空的股票, 需要进行删除
            if stock_position.is_hk_stock:
                stock_position['code'] = stock_position['code'][1:]

            code = stock_position.code
            cache_position: StockPosition = self.position_dict.get(code)
            if cache_position is None:
                self.position_dict[code] = stock_position
            else:
                cache_position.copy_from(stock_position)

        for code, position in self.position_dict.items():
            if position.balance == 0:  # 股票余额是0, 表明无持仓, 可能是条件单加进来的, 更新最新价
                CommonUtil.printLog(f'{code}(${position.name})非持仓股,直接请求最新报价')
                latest_price = AkShareUtil.get_latest_price(code, position.is_hk_stock)  # 获取最新价格
                position.market_price = latest_price
        # self.position_dict = {objDict.code: objDict for objDict in result}

        # 提取最新价信息并推送机器人
        msg_list = [f"{info.name[:2]}: {float(info.market_price):6.2f}" for code, info in self.position_dict.items()]
        msg_str = "\n".join(msg_list)
        if THSTrader.last_msg != msg_str:
            CommonUtil.printLog(f'持仓StockPositionList: {result}')
            NetUtil.push_to_robot(msg_str)
            THSTrader.last_msg = msg_str
        return result

    def get_stock_position(self, code: str, refresh: bool = False) -> Optional[StockPosition]:
        """
        获取某只股票的持仓数据,若没有持仓则返回None
        :param code: 股票代码
        :param refresh: 是否刷新持仓信息, 默认为False, 表示优先从已有缓存中读取
        """
        if refresh or CommonUtil.isNoneOrBlank(self.position_dict):
            self.get_all_stock_position()

        for position in self.position_dict.values():
            if position.code == code:
                return position
        return None

    @catch_exceptions(max_retries=1)
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
            self.get_all_stock_position()

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
        img_name = f'{"买入" if buy else "卖出"}_{position.name}_{amount}股_{price}'
        self.saveImage(self.snapshot(), img_name, autoAppendDateInfo=True)
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
        _cache_path = FileUtil.create_cache_dir(None, __file__, clear=clear)
        FileUtil.delete_files_by_extensions(_cache_path, ['.png', '.jpg'])
        return _cache_path

# # python your_script.py --condition_order_path /path/to/orders.csv
# if __name__ == '__main__':
#     while not AkShareUtil.is_trading_day():
#         now = TimeUtil.getTimeStr(n=0)
#         next_day = TimeUtil.getTimeStr('%Y-%m-%d', 1)
#         diff = TimeUtil.calc_sec_diff(now, f'{next_day} 09:30:00', '%Y-%m-%d %H:%M:%S')
#         CommonUtil.printLog(f'当前不是交易日, 等待到 {next_day} 09:30:00 后再执行, 修复 {diff}秒')
#         TimeUtil.sleep(diff)
#
#     now = TimeUtil.getTimeStr(f="%H:%M:%S", n=0)
#     diff = TimeUtil.calc_sec_diff(now, f'09:30:00', '%H:%M:%S')
#     if diff < 0:
#         CommonUtil.printLog(f'当前尚未达到9:30,休眠等待 {diff} 秒')
#         TimeUtil.sleep(abs(diff))
#
#     _cache_dir = THSTrader.create_cache_dir()  # 缓存目录
#     AkShareUtil.cache_dir = _cache_dir
#
#     # 支持从条件单缓存文件中读取配置信息
#     parser = argparse.ArgumentParser(description='处理CSV条件单文件')  # 创建参数解析器
#     parser.add_argument('--condition_order_path', required=True,
#                         default=f'{AkShareUtil.cache_dir}/condition_order.csv',
#                         help='条件单文件')
#
#     parser.add_argument('--config', required=True,
#                         default=f'{AkShareUtil.cache_dir}/config.ini',
#                         help='基础配置文件')
#
#     args = parser.parse_args()  # 解析命令行参数
#     condition_order_csv_path = args.csv_order_path  # 条件单配置文件路径
#     _config_path = args.config_path  # 基础配置文件路径
#
#     ths_trader = THSTrader(cacheDir=_cache_dir, config_path=_config_path)
#     stock_position_list = ths_trader.get_all_stock_position()  # 获取持仓信息
#
#     ConditionOrder.ths_trader = ths_trader
#     ConditionOrder.robot_dict = ths_trader.configParser.getSectionItems('robot')
#
#     # 读取CSV文件并转换为条件单对象列表
#     conditionOrderList: list = FileUtil.read_csv_to_objects(condition_order_csv_path, ConditionOrder, 1)
#     for order in conditionOrderList:
#         stock_position = ths_trader.get_stock_position(order.code)  # 该股票的持仓数据
#         if stock_position is None:  # 未持仓
#             ths_trader.position_dict[order.code] = order.position
#             continue
#         order.position = ths_trader.get_stock_position(order.code)  # 将数据更换为实际的持仓数据
#
#
#     def task_condition_orders():
#         """执行条件单"""
#         for _order in conditionOrderList:
#             if _order.active:
#                 _order.run()
#
#
#     # 每分钟触发一次条件单检测
#     if AkShareUtil.is_trading_day():
#         (SchedulerTaskManager()
#          .add_task("task_condition_orders", task_condition_orders, interval=60)
#          .add_task("task_condition_orders", ths_trader.get_all_stock_position, interval=5, unit='minutes')
#          .start()
#          )
