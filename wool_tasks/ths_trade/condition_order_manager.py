import argparse
import os
import traceback

from pywinauto import Desktop

from util.AkShareUtil import AkShareUtil
from util.CommonUtil import CommonUtil
from util.ConfigUtil import NewConfigParser
from util.FileUtil import FileUtil
from util.NetUtil import NetUtil
from util.SystemSleepPreventer import SystemSleepPreventer
from wool_tasks.scheduler_task_manager import SchedulerTaskManager
from wool_tasks.ths_trade.bean.condition_order import ConditionOrder
from wool_tasks.ths_trade.ths_auto_trade import THSTrader

# python your_script.py --condition_order_path /path/to/orders.csv
if __name__ == '__main__':
    _cache_dir = THSTrader.create_cache_dir()  # 缓存目录
    AkShareUtil.cache_dir = _cache_dir

    # 支持从条件单缓存文件中读取配置信息,优先使用 cache/ 目录下的配置文件, 若无,再从当前目录下寻找
    parser = argparse.ArgumentParser(description='处理CSV条件单文件')  # 创建参数解析器
    parser.add_argument('--condition_order_path', required=False,
                        default=f'{AkShareUtil.cache_dir}/condition_order.csv',
                        help='条件单文件')

    parser.add_argument('--config', required=False,
                        default=f'{AkShareUtil.cache_dir}/config.ini',
                        help='配置文件')

    args = parser.parse_args()  # 解析命令行参数
    condition_order_path = args.condition_order_path  # 条件单配置文件路径
    config_path = args.config  # 基础配置文件路径

    # 配置文件解析器
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = f'{cur_dir}/config.ini' if CommonUtil.isNoneOrBlank(config_path) else config_path
    condition_order_path = f'{cur_dir}/condition_order.csv' if CommonUtil.isNoneOrBlank(
        condition_order_path) else condition_order_path
    configParser = NewConfigParser(allow_no_value=True).initPath(config_path)
    NetUtil.robot_dict = configParser.getSectionItems('robot')  # 推送消息设置

    NetUtil.push_to_robot(f'condition_order_manager 开始工作', printLog=True)
    ths_trader = THSTrader(cacheDir=_cache_dir)
    ths_trader.setNotificationRobotDict(NetUtil.robot_dict)
    stock_position_list = ths_trader.get_all_stock_position()  # 获取持仓信息
    ConditionOrder.ths_trader = ths_trader

    # 读取CSV文件并转换为条件单对象列表
    conditionOrderList: list = FileUtil.read_csv_to_objects(condition_order_path, ConditionOrder, 0)
    for order in conditionOrderList:
        code = order.position.code  # 股票代码
        stock_position = ths_trader.get_stock_position(code)  # 该股票的持仓数据
        if stock_position is None:  # 未持仓
            ths_trader.position_dict[code] = order.position
            continue
        order.position = ths_trader.get_stock_position(code)  # 将数据更换为实际的持仓数据


    def prevent_lock_screen():
        """防止windows锁屏"""
        if CommonUtil.isWindows():
            CommonUtil.printLog(f'prevent_lock_screen')
            desktop = Desktop(backend="uia")
            desktop.mouse.move(coords=(100, 100))  # 模拟鼠标移动
            desktop.mouse.click(button='left')  # 模拟鼠标点击
            # desktop.keyboard.send_keys('a')  # 模拟键盘输入
            # time.sleep(60)  # 每隔60秒执行一次操作


    def task_condition_orders():
        """执行条件单"""
        # CommonUtil.printLog(f'task_condition_orders')
        for _order in conditionOrderList:
            if _order.active:
                try:
                    _order.run()
                except Exception as e:
                    _order.active = False
                    # traceback.print_exc()
                    tracebackMsg = traceback.format_exc()
                    NetUtil.push_to_robot(f'task_condition_orders 出错:{e}\n{_order.summary_info}\n{tracebackMsg}',
                                          printLog=True)


    # 等待到下一个交易日
    # AkShareUtil.wait_next_deal_time()

    # 每分钟触发一次条件单检测
    with SystemSleepPreventer():  # 防止系统休眠
        scheduler = SchedulerTaskManager()
        (scheduler
         .add_task("task_condition_orders", task_condition_orders, interval=1, unit='minutes', at_time=':00')
         .add_task("get_all_stock_position", ths_trader.get_all_stock_position, interval=1, unit='minutes',
                   at_time=':05')
         .stop_when_time_reaches('16:10:00')
         .start()  # 启动调度器
         .wait_exit_event()  # 等待按下q推出
         )

    NetUtil.push_to_robot(f'condition_order_manager 已退出', printLog=True)
