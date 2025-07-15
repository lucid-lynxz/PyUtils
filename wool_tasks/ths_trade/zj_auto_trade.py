# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import sys

from airtest.core.api import *

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)
from wool_tasks.base_airtest_4_android_impl import AbsBaseAir4Android

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil
from util.TimeUtil import log_time_consume
from util.AkShareUtil import AkShareUtil
from util.ConfigUtil import NewConfigParser


class ZJTrader(AbsBaseAir4Android):
    """
    基于尊嘉证券android端 下单 窗口,进行条件单监控(主要是港美股), 然后触发交易操作
    """

    def __init__(self, config_path: str = None, cacheDir: str = None):
        """
        :param config_path: 配置文件路径, 若为空,则会依次尝试使用 {cacheDir}/config.ini 或者 当前目录下的 config.ini 文件
        :param cacheDir: 缓存目录, 默认为当前目录下的 cache 目录
        """
        if CommonUtil.isNoneOrBlank(cacheDir):
            cacheDir = ZJTrader.create_cache_dir()

        # 配置文件解析器
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = f'{cacheDir}/config.ini' if CommonUtil.isNoneOrBlank(config_path) else config_path
        if not FileUtil.isFileExist(config_path):
            config_path = FileUtil.recookPath(f'{cur_dir}/config.ini')

        configParser = NewConfigParser(allow_no_value=True).initPath(config_path)
        zj_settings = configParser.getSectionItems('zunjia')
        deviceId: str = zj_settings.get('deviceId', '')  # 要运行的手机序列号
        self.deal_pwd: str = zj_settings.get('deal_pwd', '')   # 尊嘉交易密码,用于解锁交易
        CommonUtil.printLog(f'zhunjia deviceId={deviceId},pwd={self.deal_pwd}')

        pkgName = 'com.juniorchina.jcstock'  # 尊嘉app包名
        homeActPath = 'com.juniorchina.jcstock.SplashActivity'  # 启动页类名
        super().__init__(deviceId, pkgName=pkgName, homeActPath=homeActPath, appName='尊嘉证券', cacheDir=cacheDir)

        # 清空本设备的截图目录
        model = self.adbUtil.getDeviceInfo(deviceId).get('model', '')
        FileUtil.createFile(f'{cacheDir}/{model}_{deviceId}/', True)

        self.adbUtil.pointerLocation(1)
        is_zj_running = self.adbUtil.isAppRunning(pkgName, deviceId)  # app是否已在运行中
        self.startApp(forceRestart=False)  # 无需强制重启app

        # 刷新按钮坐标/持仓列表矩形框坐标
        self.bottom_deal_pos: tuple = None  # 底部 '交易' 页面按钮
        self.deal_icon_pos: tuple = None  # '交易' tab页面中的 '交易' 入口按钮
        self.position_code_pos: tuple = None  # '交易' tab页面中的 '我的持仓' 下方 '代码' 列名位置
        self.position_cost_pos: tuple = None  # '交易' tab页面中的 '我的持仓' 下方 '现价/成本' 列名位置
        self.search_edt_pos: tuple = None  # '交易' 搜索框坐标
        self.spinner_list_item0_pos: tuple = None  # '交易' 搜索框提示列表框中第一个元素坐标

        self.buy_pos: tuple = None  # 买入按钮
        self.sell_pos: tuple = None  # 卖出按钮
        self.price_pos: tuple = None  # 委托价输入框位置
        self.amount_pos: tuple = None  # 委托数量输入框位置
        self.can_deal_amount_pos: tuple = None  # 买入时 '现金可买' 文本位置, 卖出时, '持仓可卖' 位置
        # self.unlock_pos: tuple = None  # 解锁按钮位置 也是默认的 '确认买入' 按钮位置
        self.confirm_deal_pos: tuple = None  # 解锁成功后, 底部显示的 '确认买入' / '确认卖出' 按钮位置

        self.akshare_util: AkShareUtil = AkShareUtil()  # akshare 工具类
        self.available_balance_cash: float = -1  # 可用金额, 单位:元

        # 尝试从缓存文件中读取数据
        self.pos_cache_file = f'{cacheDir}/pos_cache_zj.txt'  # 缓存各按钮位置信息, 对于同一台设备, 不需要每次都重新获取
        line_list = FileUtil.readFile(self.pos_cache_file)
        self.need_find_pos: bool = len(line_list) <= 3  # 是否需要重新获取各坐标信息
        for line in line_list:
            if '__slots__:' in line:
                continue
            # 分离属性名和属性值
            key, pos_str = line.split(':')
            if CommonUtil.isNoneOrBlank(pos_str):
                self.need_find_pos = True
                continue
            # 将属性值按逗号分割并转换为元组
            pos_tuple = tuple(map(int, map(float, pos_str.split(','))))
            # 将元组赋值给对象对应的属性
            setattr(self, key, pos_tuple)

        if self.need_find_pos or not is_zj_running:  # 刚打开的app, 需要机型解锁操作
            self._find_bs_pos()

    @staticmethod
    def create_cache_dir() -> str:
        """
        在当前文件同级目录下创建一个缓存目录
        :return: 缓存目录路径
        """
        _cache_path = FileUtil.create_cache_dir(None, __file__, name='cache/')
        # FileUtil.delete_files(_cache_path, [r'.*\.png', r'.*.\.jpg'])
        return _cache_path

    def back_to_home(self) -> bool:
        """返回到首页"""
        return self.back_until(targetText='交易', prefixText='自选', subfixText='我')

    def back_to_deal(self):
        """
        返回到主页面中的 '交易' 页面
        """
        success = self.back_to_home()
        if success and self.bottom_deal_pos is not None:
            return self.tapByTuple(self.bottom_deal_pos, sleepSec=0.2)
        return False

    def save_pos_info(self):
        """将已找到的各控件位置信息保存到缓存文件中"""
        with open(self.pos_cache_file, 'w') as file:
            for attr_name in dir(self):
                attr_value = getattr(self, attr_name)
                if isinstance(attr_value, tuple):
                    file.write(f"{attr_name}:{','.join(map(str, attr_value))}\n")

    def _find_bs_pos(self):
        """
        主页面-'交易' tab 页面上各个按钮
        """
        input_delta = (0, 0)
        if not self.back_to_home():  # 返回到首页
            msg = '返回首页失败'
            self.saveImage(self.snapshot(), msg)
            raise f'{msg},请查看原因'

        pos, _, ocr_result = self.findTextByOCR('交易', prefixText='自选', subfixText='我', maxSwipeRetryCount=1)
        self.bottom_deal_pos = self.calcCenterPos(pos, input_delta, self.bottom_deal_pos)  # 首页底部 '交易' 按钮位置
        CommonUtil.printLog(f'首页底部交易按钮位置: {self.bottom_deal_pos}')
        self.tapByTuple(self.bottom_deal_pos)  # 点击交易按钮

        pos, ocrResStr, ocr_result = self.findTextByOCR('交易', prefixText=r'总市值|净资产',
                                                        subfixText=r'全部|我的持仓', maxSwipeRetryCount=1)
        self.deal_icon_pos = self.calcCenterPos(pos, input_delta, self.deal_icon_pos)
        CommonUtil.printLog(f'交易tab中的交易入口按钮位置: {self.deal_icon_pos}')

        pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '代码', prefixText='我的持仓',
                                                                subfixText='数量')
        self.position_code_pos = self.calcCenterPos(pos, input_delta, self.position_code_pos)  # 证券代码输入框位置
        CommonUtil.printLog(f'交易tab-我的持仓-代码 列名位置: {self.position_code_pos}')

        pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '现价', prefixText='代码',
                                                                subfixText='交易')
        self.position_cost_pos = self.calcCenterPos(pos, input_delta, self.position_cost_pos)  # 股票价格输入框
        CommonUtil.printLog(f'交易tab-我的持仓-现价/成本 列名位置: : {self.position_cost_pos}')
        if CommonUtil.isNoneOrBlank(self.position_cost_pos):
            CommonUtil.printLog(f'未找到 现价/成本 列名位置,ocrResStr={ocrResStr}')

        # 点击 '交易' 入口按钮, 跳转到交易页面
        self.tapByTuple(self.deal_icon_pos)
        pos, _, ocr_result = self.findTextByOCR('请输入', subfixText='自选', maxSwipeRetryCount=1)

        self.search_edt_pos = self.calcCenterPos(pos, input_delta, self.search_edt_pos)
        self.spinner_list_item0_pos = self.calcCenterPos(pos, (0, 140))
        CommonUtil.printLog(f'交易页面顶部搜索输入框位置: {self.search_edt_pos}')
        CommonUtil.printLog(f'交易搜索列表第一项位置: {self.spinner_list_item0_pos}')

        # 跳转到股票交易页面
        self.text('01810')  # 随便输入一个股票代码, 01810-小米集团-W
        self.sleep(1)
        self.touch(self.spinner_list_item0_pos)  # 点击下拉框中的第一个元素, 跳转到股票下个详情页面
        self.sleep(1)

        pos, ocrResStr, ocr_result = self.findTextByOCR('买入', prefixText=r'买盘|卖盘', subfixText=r'卖出|解锁',
                                                        maxSwipeRetryCount=1)
        self.buy_pos = self.calcCenterPos(pos, default_value=self.buy_pos)  # 买入按钮
        CommonUtil.printLog(f'交易页面的 买入 按钮: {self.buy_pos}')

        pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '卖出', prefixText='买入',
                                                                subfixText='委托|解锁')
        self.sell_pos = self.calcCenterPos(pos, default_value=self.sell_pos)  # 卖出 按钮
        CommonUtil.printLog(f'交易页面的 卖出 按钮: {self.sell_pos}')

        input_delta = (600, 0)
        pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '委托价', prefixText='买入',
                                                                subfixText='订单|解锁')
        self.price_pos = self.calcCenterPos(pos, input_delta, default_value=self.price_pos)  # 委托价 输入框
        CommonUtil.printLog(f'交易页面的 委托价 输入框: {self.price_pos}')

        pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '委托数量', prefixText='买入',
                                                                subfixText='订单|解锁')
        self.amount_pos = self.calcCenterPos(pos, input_delta, default_value=self.amount_pos)  # 委托数量 输入框
        CommonUtil.printLog(f'交易页面的 委托数量 输入框: {self.amount_pos}')

        pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '现金可买', prefixText='买入',
                                                                subfixText='订单|解锁')
        self.can_deal_amount_pos = self.calcCenterPos(pos, default_value=self.can_deal_amount_pos)
        CommonUtil.printLog(f'交易页面的 持仓可买/现金可买 文本框: {self.can_deal_amount_pos}')

        self.need_find_pos = (CommonUtil.isNoneOrBlank(self.bottom_deal_pos)
                              or CommonUtil.isNoneOrBlank(self.deal_icon_pos)
                              or CommonUtil.isNoneOrBlank(self.position_code_pos)
                              or CommonUtil.isNoneOrBlank(self.position_cost_pos)
                              or CommonUtil.isNoneOrBlank(self.search_edt_pos)
                              or CommonUtil.isNoneOrBlank(self.spinner_list_item0_pos)
                              or CommonUtil.isNoneOrBlank(self.buy_pos)
                              or CommonUtil.isNoneOrBlank(self.sell_pos)
                              or CommonUtil.isNoneOrBlank(self.price_pos)
                              or CommonUtil.isNoneOrBlank(self.amount_pos)
                              or CommonUtil.isNoneOrBlank(self.can_deal_amount_pos)
                              )
        CommonUtil.printLog(f'_find_bs_pos end, need_find_pos={self.need_find_pos} ')

        # 模拟正常输入委托数量后, '确认按钮' 的位置
        self.tapByTuple(self.amount_pos)  # '委托数量输入框'
        self.clear_text()  # 清空文本
        self.text('200')  # 输入数量
        self.sleep(1)

        self.unlock_deal()  # 进行交易解锁
        self.save_pos_info()  # 保存各控件位置信息
        self.back_to_deal()  # 返回到首页的交易入口tab页面

    def unlock_deal(self, ocr_result: list = None) -> bool:
        """
        界面上显示有 '解锁' 按钮时, 先解锁再进行交易
        见: '尊嘉证券_解锁交易_提示框.png'
        :param ocr_result: 界面OCR识别结果,若为空,则会重新进行截图识别
        """
        if ocr_result is None:
            pos, ocrResStr, ocrResList = self.findTextByOCR('解锁', prefixText=r'订单|委托数量',
                                                            imgPrefixName='find_bs_pos', maxSwipeRetryCount=1)
        else:
            pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '解锁', prefixText=r'订单|委托数量')
        unlock_pos = self.calcCenterPos(pos)  # 解锁 按钮
        CommonUtil.printLog(f'交易页面的 解锁 按钮: {unlock_pos}')  # 若为空表示不需要解锁

        # 点击 '解锁' 按钮, 弹出输入框
        if '解锁' in ocrResStr and self.tapByTuple(unlock_pos):
            # pos, ocrResStr, ocr_result = self.findTextByOCR('交易密码', prefixText='解锁', subfixText=r'解锁')
            # dialog_pwd_edt_pos = self.calcCenterPos(pos, (0, 100))  # 交易密码输入款
            self.text(self.deal_pwd)
            pos, ocrResStr, ocr_result = self.findTextByOCR('解锁', prefixText='交易密码', subfixText='指纹',
                                                            imgPrefixName='find_bs_pos_解锁', maxSwipeRetryCount=1)
            dialog_unlock_btn_pos = self.calcCenterPos(pos)  # 解锁按钮
            self.tapByTuple(dialog_unlock_btn_pos)  # 点击解锁按钮, 隐藏弹框

        CommonUtil.printLog(f'搜索交易页面的 确认买入 按钮位置')  # 若为空表示不需要解锁
        pos, ocrResStr, ocrResList = self.findTextByOCR('确认买入', prefixText=r'订单|委托数量',
                                                        imgPrefixName='find_bs_pos_确认买入', maxSwipeRetryCount=1)
        self.confirm_deal_pos = self.calcCenterPos(pos)
        CommonUtil.printLog(f'交易页面的 确认买入 按钮: {self.confirm_deal_pos}')  # 若为空表示不需要解锁
        return not CommonUtil.isNoneOrBlank(self.confirm_deal_pos)

    last_msg: str = ''

    @log_time_consume(separate=True)
    def deal(self, code: str, price: float, amount: float, name: str = '') -> bool:
        """
        买卖股票
        :param code: 股票代码
        :param price: 价格, 大于0有效, 若传入 <=0 的值, 则表示使用软件提供的买卖价进行交易, 一般卖出擦欧总时, 会使用买一价, 买入操作时,使用卖一价
        :param amount: 数量,单位:股,  正数表示买入, 负数表示卖出
        :param name: 股票名称
        """
        if not self.back_to_deal():  # 返回到首页的交易tab页面
            msg = 'deal_返回交易tab失败'
            self.saveImage(self.snapshot(), msg)
            raise f'{msg},请查看原因'

        if not self.tapByTuple(self.deal_icon_pos):  # 点击 '交易' 按钮, 进入交易搜索页
            msg = 'deal_点击交易icon失败'
            self.saveImage(self.snapshot(), msg)
            raise f'{msg},请查看原因'

        CommonUtil.printLog(f'zj deal({code},{price},{amount},{name})')
        buy = amount > 0  # true-买入 false-卖出
        amount = abs(amount)

        # 跳转到股票交易页面
        self.text(code)  # 输入股票代码
        self.sleep(1)
        self.touch(self.spinner_list_item0_pos)  # 点击下拉框中的第一个元素, 跳转到股票下个详情页面
        self.sleep(2)

        if buy:
            self.tapByTuple(self.buy_pos)  # '买入' 按钮
            # todo 补充判断最大可买量
            # self.findTextByOCR(r'\d+', prefixText='附加订单', subfixText='订单金额|解锁|确定',
            #                    fromX=0, fromY=self.can_deal_amount_pos[1] - 150, width=300, height=100)
            # if self.available_balance_cash >= 0 and price > 0:  # 获取到有效的可用金额
            #     amount = min(amount, int(self.available_balance_cash / price))
            #     amount = CommonUtil.round_down_to_hundred(amount)
            #     # 买入时, 不能超过当前可买数量
            #     if amount <= 0:
            #         CommonUtil.printLog(f'交易:{stock_name}({code}) 可买数量为0,买入失败')
            #         return False
        else:
            self.tapByTuple(self.sell_pos)  # '卖出' 按钮
            # todo 补充判断最大可卖量
            # if position is None and not buy:
            #     CommonUtil.printLog(f'{code} 不存在持仓信息,卖出失败')
            #     return False
            #
            # self.key_press('F2')  # '卖出[F2]'
            # amount = min(amount, int(position.available_balance))

            # # 卖出时, 不能超过当前可卖数量
            # if amount <= 0:
            #     CommonUtil.printLog(f'交易:{stock_name}({code}) 可卖数量为0,卖出失败')
            #     return False

        # 委托价格
        if price > 0:
            self.tapByTuple(self.price_pos)  # 委托价 输入框
            self.clear_text()  # 清空文本
            self.text(f'{price}')

        # 委托数量
        self.tapByTuple(self.amount_pos)  # '委托数量输入框'
        self.clear_text()  # 清空文本
        self.text(str(amount))  # 输入数量
        self.sleep(1)

        deal_tip = '买入' if buy else "卖出"
        deal_dir_path = FileUtil.recookPath(f'{self.cacheDir}/deal/')
        img_name = f'{deal_tip}_{code if CommonUtil.isNoneOrBlank(name) else name}_{amount}股'
        success: bool = False  # 是否交易成功
        for i in range(3):
            CommonUtil.printLog(f'{img_name}_index{i}')
            self.tapByTuple(self.confirm_deal_pos, printCmdInfo=True)  # 底部的 '确认买入/卖出'  按钮  也可能是 '解锁' 按钮

            # 验证是否已交易成功 耗时4s左右
            CommonUtil.printLog(f'截图并ocr检测是否 提交订单 成功')
            pos, ocrResStr, ocrResList = self.findTextByOCR('订单已提交', prefixText=r'我的持仓|委托数量',
                                                            maxSwipeRetryCount=1)
            success = pos is not None and len(pos) > 1  # 交易成功则无需继续测试
            if success:
                break

            # 检测是否有 '确认下单' 的提示框
            CommonUtil.printLog(f'截图并ocr检测是否有 确认下单 弹框')
            pos, ocrResStr, _ = self.findTextByCnOCRResult(ocrResList, '确认下单', prefixText='不再提示')
            confirm_pos = self.calcCenterPos(pos)

            # 检测是否是 '解锁交易' 提示框, 见: '尊嘉证券_解锁交易_提示框.png'   已有ocr结果, 重新检测文本, 耗时1ms左右
            CommonUtil.printLog(f'检测是否有 解锁交易 弹框, ocrResStr:{ocrResStr}')
            pos, ocrResStr, _ = self.findTextByCnOCRResult(ocrResList, '解锁', prefixText=r'交易密码',
                                                           subfixText='指纹')
            dialog_unlock_btn_pos = self.calcCenterPos(pos)

            # 检测是否有 '超过最大购买力' 提示框
            CommonUtil.printLog(f'检测是否有 超过最大购买力 弹框')
            pos, ocrResStr, _ = self.findTextByCnOCRResult(ocrResList, '取消', prefixText=r'最大购买力')
            purchasing_power_pos = self.calcCenterPos(pos)

            if not CommonUtil.isNoneOrBlank(confirm_pos):
                # 存在 '确认下单' 提示框则点击确定按钮进行提交
                CommonUtil.printLog(f'deal 关闭 确认下单 提示框')
                self.tapByTuple(confirm_pos)
            elif not CommonUtil.isNoneOrBlank(dialog_unlock_btn_pos):
                # 存在 '交易密码' 提示框,则输入密码进行确认, 然后重新尝试点击底部的 '确认买入/卖出' 按钮
                CommonUtil.printLog(f'deal 进行解锁后重试')
                self.text(self.deal_pwd)  # 输入交易密码
                self.tapByTuple(dialog_unlock_btn_pos)  # 点击解锁按钮, 隐藏弹框
                continue  # 重新点击底部的 '确认买入/卖出' 按钮
            elif not CommonUtil.isNoneOrBlank(purchasing_power_pos):
                CommonUtil.printLog(f'deal 超过最大购买力, 取消本次交易')
                self.tapByTuple(purchasing_power_pos)  # 点击 '取消' 按钮, 隐藏弹框
                success = False
                break  # 现金不够, 无需重新尝试提交订单呢

            # 验证是否已交易成功
            CommonUtil.printLog(f'deal 检测是否提交订单成功')
            pos, ocrResStr, ocrResList = self.findTextByOCR('订单已提交', prefixText=r'我的持仓|委托数量',
                                                            maxSwipeRetryCount=1)
            success = pos is not None and len(pos) > 1
            break

        img_name = f'{img_name}_{"成功" if success else "失败"}'
        CommonUtil.printLog(f'deal {img_name}')
        self.saveImage(self.snapshot_img, img_name, dirPath=deal_dir_path, auto_create_sub_dir=False)
        self.back_to_deal()  # 返回到交易入口页
        return success


# python your_script.py --condition_order_path /path/to/orders.csv
if __name__ == '__main__':
    ths_trader = ZJTrader()
    # ths_trader.deal('01810', 52.15, -100)
    ths_trader.deal('01810', 0, 200, '小米集团')
    # ths_trader.deal('600980', 22.05, -200)
    # time.sleep(3)
    #
    # ths_trader.deal('002731', 0, -200)
    # time.sleep(3)
    # # ths_trader.deal('000903', 3.55, 200)
    #
    # ths_trader.deal('600980', 22.05, 200)
    # time.sleep(3)
