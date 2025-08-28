# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import sys
import os

from airtest.core.api import *

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)
from wool_tasks.base_airtest_4_android_impl import AbsBaseAir4Android

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil
from util.TimeUtil import log_time_consume, TimeUtil
from util.AkShareUtil import AkShareUtil
from util.ConfigUtil import NewConfigParser


class PositionSet:
    """位置集容器，统一管理单市场（港股/美股）的所有界面元素坐标"""

    def __init__(self):
        self.bottom_deal_pos: tuple = None  # 底部 '交易' 页面按钮
        self.deal_icon_pos: tuple = None  # '交易' tab页面中的 '交易' 入口按钮
        self.position_code_pos: tuple = None  # '我的持仓' 下方 '代码' 列名位置
        self.position_cost_pos: tuple = None  # '我的持仓' 下方 '现价/成本' 列名位置
        self.search_edt_pos: tuple = None  # '交易' 搜索框坐标
        self.spinner_list_item0_pos: tuple = None  # 搜索框提示列表第一个元素坐标
        self.buy_pos: tuple = None  # 买入按钮
        self.sell_pos: tuple = None  # '卖出' 按钮
        self.price_pos: tuple = None  # 委托价输入框位置
        self.amount_pos: tuple = None  # 委托数量输入框位置
        self.can_deal_amount_pos: tuple = None  # '现金可买'/'持仓可卖' 文本位置
        self.confirm_deal_pos: tuple = None  # '确认买入'/'确认卖出' 按钮位置


class ZJTrader(AbsBaseAir4Android):
    """
    基于尊嘉证券android端 下单窗口,支持港美股条件单监控与交易操作
    """

    def __init__(self, config_path: str = None, cacheDir: str = None):
        """
        :param config_path: 配置文件路径, 若为空则使用缓存目录或当前目录下的config.ini
        :param cacheDir: 缓存目录, 默认为当前目录下的cache目录
        """
        if CommonUtil.isNoneOrBlank(cacheDir):
            cacheDir = ZJTrader.create_cache_dir()

        # 配置文件解析
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = f'{cacheDir}/config.ini' if CommonUtil.isNoneOrBlank(config_path) else config_path
        if not FileUtil.isFileExist(config_path):
            config_path = FileUtil.recookPath(f'{cur_dir}/config.ini')

        configParser = NewConfigParser(allow_no_value=True).initPath(config_path)
        zj_settings = configParser.getSectionItems('zunjia')
        deviceId: str = zj_settings.get('deviceId', '')  # 手机序列号
        self.deal_pwd: str = zj_settings.get('deal_pwd', '')  # 交易密码
        CommonUtil.printLog(f'尊嘉配置: deviceId={deviceId}, pwd={self.deal_pwd}')

        # 初始化父类(Android自动化基础类)
        pkgName = 'com.juniorchina.jcstock'  # 尊嘉app包名
        homeActPath = 'com.juniorchina.jcstock.SplashActivity'  # 启动页
        super().__init__(deviceId, pkgName=pkgName, homeActPath=homeActPath, appName='尊嘉证券', cacheDir=cacheDir)

        # 设备截图目录初始化
        model = self.adbUtil.getDeviceInfo(deviceId).get('model', '')
        FileUtil.createFile(f'{cacheDir}/{model}_{deviceId}/', True)

        # APP状态初始化
        self.adbUtil.pointerLocation(1)  # 显示指针位置(调试用)
        is_zj_running = self.adbUtil.isAppRunning(pkgName, deviceId)
        self.startApp(forceRestart=False)  # 非强制重启

        # 多市场位置集初始化(港股/美股)
        self.hk_pos = PositionSet()  # 港股界面坐标集
        self.us_pos = PositionSet()  # 美股界面坐标集
        self.current_pos = self.hk_pos  # 当前活跃市场坐标(默认港股)

        # 其他属性初始化
        self.akshare_util: AkShareUtil = AkShareUtil()
        self.available_balance_cash: float = -1  # 可用资金
        self.last_unlock_ts: int = 0  # 上次解锁时间戳, 每5min检测一次

        # 位置缓存加载
        self.pos_cache_file = f'{cacheDir}/pos_cache_zj.txt'  # 坐标缓存文件
        line_list = FileUtil.readFile(self.pos_cache_file)
        self.need_find_pos: dict = {'hk': True, 'us': True}  # 标记是否需要重新定位
        self._load_pos_cache(line_list)  # 从缓存文件加载坐标

        # 首次运行或缓存缺失时执行界面定位
        if self.need_find_pos['hk']:
            self._find_bs_pos(market='hk')  # 定位港股界面
        # 美股定位可在首次交易前触发
        if self.need_find_pos['us']:
            self._find_bs_pos(market='us')  # 定位美股界面
        self.unlock_deal()  # 尝试解锁一次

    def _load_pos_cache(self, line_list: list):
        """从缓存文件加载多市场坐标数据"""
        for line in line_list:
            if '__slots__:' in line or ':' not in line:
                continue
            key, pos_str = line.split(':', 1)
            if CommonUtil.isNoneOrBlank(pos_str):
                continue
            # 解析格式: market_attr: x,y (如 hk_bottom_deal_pos:100,200)
            if '_' in key:
                market, attr = key.split('_', 1)
                target_pos = self.hk_pos if market == 'hk' else self.us_pos
                if market in ['hk', 'us'] and hasattr(target_pos, attr):
                    # 转换坐标元组并赋值给对应市场的位置集
                    pos_tuple = tuple(map(int, map(float, pos_str.split(','))))
                    setattr(target_pos, attr, pos_tuple)

        self.need_find_pos['hk'] = not self._are_all_pos_attributes_set(self.hk_pos)  # 标记缓存有效
        self.need_find_pos['us'] = not self._are_all_pos_attributes_set(self.us_pos)  # 标记缓存有效

    def _are_all_pos_attributes_set(self, pos_set: PositionSet) -> bool:
        """检查 PositionSet 实例的所有 _pos 属性是否均非空"""
        for attr in dir(pos_set):
            # 只检查以 _pos 结尾且非特殊属性（如 __init__）的属性
            if attr.endswith('_pos') and not attr.startswith('__'):
                attr_value = getattr(pos_set, attr)
                if CommonUtil.isNoneOrBlank(attr_value):
                    CommonUtil.printLog(f"坐标属性 {attr} 为空，需要重新定位")
                    return False
        return True

    @staticmethod
    def create_cache_dir() -> str:
        """创建缓存目录"""
        return FileUtil.create_cache_dir(None, __file__, name='cache/')

    def back_to_home(self) -> bool:
        """返回到APP首页"""
        return self.back_until(targetText='交易', prefixText='自选', subfixText='我')

    def back_to_deal(self):
        """返回到交易tab页面"""
        success = self.back_to_home()
        if success and self.current_pos.bottom_deal_pos:
            return self.tapByTuple(self.current_pos.bottom_deal_pos, sleepSec=0.2)
        return False

    def save_pos_info(self):
        """保存多市场坐标到缓存文件"""
        with open(self.pos_cache_file, 'w') as file:
            # 保存港股坐标(前缀hk_)
            for attr in dir(self.hk_pos):
                if not attr.endswith('_pos') or attr.startswith('__'):
                    continue
                pos_tuple = getattr(self.hk_pos, attr)
                if pos_tuple:
                    file.write(f"hk_{attr}:{','.join(map(str, pos_tuple))}\n")
            # 保存美股坐标(前缀us_)
            for attr in dir(self.us_pos):
                if not attr.endswith('_pos') or attr.startswith('__'):
                    continue
                pos_tuple = getattr(self.us_pos, attr)
                if pos_tuple:
                    file.write(f"us_{attr}:{','.join(map(str, pos_tuple))}\n")

    def _find_bs_pos(self, market: str = 'hk'):
        """
        定位指定市场的界面元素坐标
        :param market: 市场类型, 'hk'(港股)或'us'(美股)
        """
        target_pos = self.hk_pos if market == 'hk' else self.us_pos  # 目标市场坐标集
        input_delta = (0, 0)  # 坐标微调值
        CommonUtil.printLog(f'开始{market}市场界面定位...')

        # 1. 返回首页并定位底部交易按钮
        if not self.back_to_home():
            msg = f'{market}市场-返回首页失败'
            self.saveImage(self.snapshot(), msg)
            raise RuntimeError(f'{msg}, 请检查APP状态')

        pos, _, ocr_result = self.findTextByOCR('交易', prefixText='自选', subfixText='我', maxSwipeRetryCount=1)
        target_pos.bottom_deal_pos = self.calcCenterPos(pos, input_delta, target_pos.bottom_deal_pos)
        CommonUtil.printLog(f'{market}市场-底部交易按钮: {target_pos.bottom_deal_pos}')
        self.tapByTuple(target_pos.bottom_deal_pos)  # 点击进入交易tab

        # 2. 定位交易入口按钮(交易tab内)
        pos, ocrResStr, ocr_result = self.findTextByOCR('交易', prefixText=r'总市值|净资产',
                                                        subfixText=r'全部|我的持仓', maxSwipeRetryCount=1)
        target_pos.deal_icon_pos = self.calcCenterPos(pos, input_delta, target_pos.deal_icon_pos)
        CommonUtil.printLog(f'{market}市场-交易入口按钮: {target_pos.deal_icon_pos}')

        # 3. 定位持仓列表列名(代码/现价)
        pos, _, ocrResList = self.findTextByCnOCRResult(ocr_result, '代码', prefixText='我的持仓', subfixText='数量')
        target_pos.position_code_pos = self.calcCenterPos(pos, input_delta, target_pos.position_code_pos)
        CommonUtil.printLog(f'{market}市场-代码位置: {target_pos.position_code_pos}')

        pos, _, ocrResList = self.findTextByCnOCRResult(ocr_result, '现价', prefixText='代码', subfixText='交易')
        target_pos.position_cost_pos = self.calcCenterPos(pos, input_delta, target_pos.position_cost_pos)
        CommonUtil.printLog(f'{market}市场-现价位置: {target_pos.position_cost_pos}')

        # 4. 进入交易搜索页面并定位搜索框
        self.tapByTuple(target_pos.deal_icon_pos)  # 点击交易入口
        pos, _, ocr_result = self.findTextByOCR('请输入', subfixText='自选', maxSwipeRetryCount=1)
        target_pos.search_edt_pos = self.calcCenterPos(pos, input_delta, target_pos.search_edt_pos)
        target_pos.spinner_list_item0_pos = self.calcCenterPos(pos, (0, 140))  # 搜索下拉第一项
        CommonUtil.printLog(f'{market}市场-搜索框位置: {target_pos.search_edt_pos}')

        # 5. 进入股票详情页(使用市场代表性代码)
        test_code = '01810' if market == 'hk' else 'TME'  # 港股测试代码01810小米集团/美股测试代码TME腾讯音乐
        self.text(test_code)  # 输入代码
        self.sleep(1)
        self.touch(target_pos.spinner_list_item0_pos)  # 选择下拉第一项
        self.sleep(2)

        # 6. 定位买卖按钮
        pos, ocrResStr, ocr_result = self.findTextByOCR('买入', prefixText=r'买盘|卖盘', subfixText=r'卖出|解锁', maxSwipeRetryCount=1)
        target_pos.buy_pos = self.calcCenterPos(pos, default_value=target_pos.buy_pos)
        CommonUtil.printLog(f'{market}市场-买入按钮: {target_pos.buy_pos}')

        pos, _, ocrResList = self.findTextByCnOCRResult(ocr_result, '卖出', prefixText='买入', subfixText='委托|解锁')
        target_pos.sell_pos = self.calcCenterPos(pos, default_value=target_pos.sell_pos)
        CommonUtil.printLog(f'{market}市场-卖出按钮: {target_pos.sell_pos}')

        # 7. 定位委托价/数量输入框(偏移x=600,适应输入框位置)
        input_delta = (600, 0)
        pos, _, ocrResList = self.findTextByCnOCRResult(ocr_result, '委托价', prefixText='买入', subfixText='订单|解锁')
        target_pos.price_pos = self.calcCenterPos(pos, input_delta, default_value=target_pos.price_pos)
        CommonUtil.printLog(f'{market}市场-委托价输入框: {target_pos.price_pos}')

        pos, _, ocrResList = self.findTextByCnOCRResult(ocr_result, '委托数量', prefixText='买入', subfixText='订单|解锁')
        target_pos.amount_pos = self.calcCenterPos(pos, input_delta, default_value=target_pos.amount_pos)
        CommonUtil.printLog(f'{market}市场-委托数量输入框: {target_pos.amount_pos}')

        # 8. 定位可交易数量文本(现金可买/持仓可卖)
        pos, _, ocrResList = self.findTextByCnOCRResult(ocr_result, '现金可买|持仓可卖', prefixText='买入', subfixText='订单|解锁|确认买入')
        target_pos.can_deal_amount_pos = self.calcCenterPos(pos, default_value=target_pos.can_deal_amount_pos)
        CommonUtil.printLog(f'{market}市场-可交易数量文本: {target_pos.can_deal_amount_pos}')

        # 9. 检查坐标完整性
        self.need_find_pos[market] = self._are_all_pos_attributes_set(target_pos)
        CommonUtil.printLog(f'{market}市场坐标完整性: need_find_pos={self.need_find_pos[market]},target_pos={target_pos}')

        # 10. 定位确认交易按钮(模拟输入数量后)
        self.tapByTuple(target_pos.amount_pos)  # 点击数量输入框
        self.clear_text()  # 清空
        self.text('200')  # 输入测试数量
        self.sleep(1)
        self.unlock_deal(market=market)  # 解锁并定位确认按钮

        # 11. 保存坐标缓存并返回
        self.save_pos_info()
        self.back_to_deal()

    def unlock_deal(self, market: str = 'hk', ocr_result: list = None) -> bool:
        """1
        解锁交易并定位确认按钮
        :param market: 市场类型(hk/us)
        :param ocr_result: 预识别的OCR结果(可选)
        """

        cur_ts = TimeUtil.currentTimeMillis()
        if cur_ts - self.last_unlock_ts <= 5 * 60 * 1000:
            return True

        is_hk_market = market == 'hk'
        target_pos = self.hk_pos if is_hk_market else self.us_pos
        # 1. 查找解锁按钮
        if ocr_result is None:
            pos, ocrResStr, ocrResList = self.findTextByOCR('解锁', prefixText=r'订单|委托数量',
                                                            imgPrefixName=f'{market}_unlock', maxSwipeRetryCount=1)
        else:
            pos, ocrResStr, ocrResList = self.findTextByCnOCRResult(ocr_result, '解锁', prefixText=r'订单|委托数量')
        unlock_pos = self.calcCenterPos(pos)
        CommonUtil.printLog(f'{market}市场-解锁按钮位置: {unlock_pos}')

        # 2. 输入密码并解锁
        if '解锁' in ocrResStr and self.tapByTuple(unlock_pos):
            self.text(self.deal_pwd)  # 输入交易密码
            pos, ocrResStr, ocr_result = self.findTextByOCR('解锁', prefixText='交易密码|解锁交易', subfixText='指纹|忘记密码|解锁',
                                                            imgPrefixName=f'{market}_unlock_confirm', maxSwipeRetryCount=1)
            dialog_unlock_btn_pos = self.calcCenterPos(pos)
            if not self.tapByTuple(dialog_unlock_btn_pos):  # 确认解锁
                CommonUtil.printLog(f'确认解锁失败, dialog_unlock_btn_pos={dialog_unlock_btn_pos},ocrResStr={ocrResStr}')

        # 3. 定位确认交易按钮
        pos, _, _ = self.findTextByOCR('确认买入', prefixText=r'订单|委托数量',
                                       imgPrefixName=f'{market}_confirm_deal', maxSwipeRetryCount=1)
        target_pos.confirm_deal_pos = self.calcCenterPos(pos)
        CommonUtil.printLog(f'{market}市场-确认交易按钮: {target_pos.confirm_deal_pos}')
        success = not CommonUtil.isNoneOrBlank(target_pos.confirm_deal_pos)
        if success:
            self.last_unlock_ts = cur_ts
        return success

    def _detect_market(self, code: str) -> str:
        """根据股票代码判断市场类型"""
        if code.isdigit():  # 港股代码为数字(如01810)
            return 'hk'
        elif code.isalpha():  # 美股代码为字母(如TME)
            return 'us'
        return 'hk'  # 默认港股

    @log_time_consume(separate=True)
    def deal(self, code: str, price: float, amount: float, name: str = '') -> bool:
        """
        执行买卖交易
        :param code: 股票代码(港股数字/美股字母)
        :param price: 委托价格(>0有效)
        :param amount: 委托数量(正数买入/负数卖出)
        :param name: 股票名称(可选)
        :return: 交易是否成功
        """
        # 1. 自动切换市场坐标集
        market = self._detect_market(code)
        self.current_pos = self.hk_pos if market == 'hk' else self.us_pos
        CommonUtil.printLog(f'交易开始: {market}市场, 代码={code}, 价格={price}, 数量={amount}')

        # 2. 回到交易页面
        if not self.back_to_deal():
            msg = f'{market}市场-返回交易页面失败'
            self.saveImage(self.snapshot(), msg)
            raise RuntimeError(msg)

        # 3. 进入交易搜索页面
        if not self.tapByTuple(self.current_pos.deal_icon_pos):
            msg = f'{market}市场-点击交易入口失败'
            self.saveImage(self.snapshot(), msg)
            raise RuntimeError(msg)

        # 4. 输入股票代码并进入详情页
        self.text(code)  # 输入代码
        self.sleep(1)
        self.touch(self.current_pos.spinner_list_item0_pos)  # 选择搜索结果第一项
        self.sleep(1)

        # 5. 点击买卖按钮
        buy = amount > 0
        amount_abs = abs(amount)
        if buy:
            self.tapByTuple(self.current_pos.buy_pos)  # 买入
        else:
            self.tapByTuple(self.current_pos.sell_pos)  # 卖出

        # 6. 输入委托价格(若指定)
        if price > 0:
            self.tapByTuple(self.current_pos.price_pos)
            self.clear_text()
            self.text(f'{price}')
            self.sleep(0.5)

        # 7. 输入委托数量
        self.tapByTuple(self.current_pos.amount_pos)
        self.clear_text()
        self.text(str(amount_abs))
        self.sleep(1)

        self.unlock_deal(market)  # 尝试解锁

        # 8. 尝试提交订单(最多3次重试)
        deal_tip = '买入' if buy else '卖出'
        deal_dir = FileUtil.recookPath(f'{self.cacheDir}/deal/')
        img_name = f'{deal_tip}_{code}_{name}_{amount_abs}股'
        success = False

        for i in range(3):
            CommonUtil.printLog(f'{img_name}-第{i + 1}次提交')
            self.tapByTuple(self.current_pos.confirm_deal_pos, printCmdInfo=True)  # 点击确认按钮

            # 验证订单提交结果
            pos, ocrResStr, ocrResList = self.findTextByOCR('订单已提交', prefixText=r'我的持仓|委托数量', maxSwipeRetryCount=1)
            success = pos is not None and len(pos) > 1
            if success:
                break

            # 处理弹窗(确认下单/解锁/购买力不足)
            confirm_pos = self._find_dialog_pos(ocrResList, '确认下单', '不再提示')
            unlock_pos = self._find_dialog_pos(ocrResList, '解锁', '交易密码')
            power_pos = self._find_dialog_pos(ocrResList, '取消', '最大购买力')

            if confirm_pos:
                self.tapByTuple(confirm_pos)  # 确认下单
            elif unlock_pos:
                self.text(self.deal_pwd)  # 输入密码解锁
                self.tapByTuple(unlock_pos)
            elif power_pos:
                self.tapByTuple(power_pos)  # 购买力不足,取消
                success = False
                break

        # 9. 保存交易结果截图
        img_name = f'{img_name}_{"成功" if success else "失败"}'
        self.saveImage(self.snapshot_img, img_name, dirPath=deal_dir, auto_create_sub_dir=False)
        self.back_to_deal()
        CommonUtil.printLog(f'交易结束: {img_name}')
        return success

    def _find_dialog_pos(self, ocr_res_list: list, keyword: str, prefix: str = '') -> tuple:
        """查找弹窗按钮位置"""
        pos, _, _ = self.findTextByCnOCRResult(ocr_res_list, keyword, prefixText=prefix)
        return self.calcCenterPos(pos) if pos else None


if __name__ == '__main__':
    trader = ZJTrader()
    # 测试港股交易(数字代码)
    # trader.deal('01810', 52.5, -100, '小米集团-W')
    # 测试美股交易(字母代码)
    trader.deal('TME', 18, 1, '腾讯音乐')
