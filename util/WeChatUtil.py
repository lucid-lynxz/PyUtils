# !/usr/bin/env python3
# -*- coding:utf-8 -*-

""""
基于 uiautomation 实现微信消息监控工具, 主要用于学习, 见方法: start_monitor(..) 需要双击打开指定的聊天窗口
已有开源项目: https://github.com/cluic/wxauto 支持微信的消息监听, 发送消息等功能, 推荐使用

使用方法:
1. 安装 uiautomation 库: pip install uiautomation
2. 安装 wxauto 库:
    git clone https://github.com/cluic/wxauto.git --depth 1
    cd wxauto
    pip install .
3.使用wxauto库:
  监听信息: monitor(who,enable)
  发送信息: send_msg(who, msg)
  停止监听: stop()
"""

import threading

import uiautomation as uia
from uiautomation import UIAutomationInitializerInThread

from typing_extensions import Self
from collections import deque
from util.TimeUtil import TimeUtil
from util.CommonUtil import CommonUtil
from util.DelayedTaskManager import DelayedTaskManager

from wxauto import WeChat
from wxauto import Chat
from wxauto.msgs import FriendMessage, Message


class WeChatUtil:
    def __init__(self, msg_list_control_name: str = '消息', max_hist: int = 5):
        """
        微信消息监控工具
        :param msg_list_control_name: 微信消息列表控件名称,自测 '3.9.10.27' 版本的聊天列表控件名是:'消息'
        :param max_hist: 缓存最大历史消息数量, 与历史消息相同的消息不会打印
        """
        self.msg_list_control_name = msg_list_control_name
        self.max_hist = max_hist
        self.pending_stop: bool = False
        self.task_manager = DelayedTaskManager()

        self.wxauto_monitor_names = set()  # 使用wxauto监听的好友昵称列表
        self.wxauto = WeChat()  # 初始化微信实例
        # self.wxauto.KeepRunning()  # 保持程序运行

    def stop(self):
        CommonUtil.printLog(f'stop')
        self.pending_stop = True
        # if len(self.wxauto_monitor_names) > 0:
        #     n_set = self.wxauto_monitor_names.copy()
        #     for name in n_set:
        #         self.monitor(name, False)
        self.wxauto.StopListening()
        self.wxauto_monitor_names = set()

    def _start_monitor(self, windows_name: str):
        """
        :param windows_name: 微信聊天窗口名称, 双击某个好友,即可弹出独立窗口,窗口名称为好友昵称
        """
        # 在子线程函数的开头，创建 UIAutomationInitializerInThread 实例
        with UIAutomationInitializerInThread():
            msg_history = deque(maxlen=self.max_hist)
            uiaAPI = uia.WindowControl(Name=windows_name)
            uiaAPI.SwitchToThisWindow()
            uiaAPI.MoveToCenter()

            CommonUtil.printLog(f"开始监听 '{windows_name}' 信息,线程:{threading.current_thread().name}")
            while not self.pending_stop:
                # 获取会话列表
                sessionList = uiaAPI.ListControl(Name=self.msg_list_control_name)
                if not sessionList or not sessionList.Exists(0.1):
                    TimeUtil.sleep(0.5)
                    continue

                # 获取所有可见的消息项
                messages = []
                for item in sessionList.GetChildren():
                    nicknameBtn = item.ButtonControl()
                    if nicknameBtn and nicknameBtn.Exists(0.1):
                        message = f"{nicknameBtn.Name}:{item.Name}"
                        messages.append(message)

                # 检查新消息（从后往前处理)
                new_messages = []
                for msg in reversed(messages):
                    if msg not in msg_history:
                        new_messages.append(msg)
                        msg_history.append(msg)  # 自动丢弃l旧消息（deque 自动维护大小)
                    else:
                        break  # 遇到已处理的消息就停止

                # 打印新消息（按时间顺序)
                for msg in reversed(new_messages):
                    CommonUtil.printLog(msg)
                TimeUtil.sleep(0.5)
            CommonUtil.printLog(f"结束监听 '{windows_name}' 信息,线程:{threading.current_thread().name}")

    def start_monitor(self, windows_name: str):
        self.task_manager.addTask(0, self._start_monitor, windows_name)

    def send_msg(self, who: str, msg: str) -> Self:
        """
        发送消息
        :param who: 要发送的对象, 即好友昵称
        :param msg: 要发送的消息
        """
        self.wxauto.SendMsg(msg, who=who)
        return self

    def monitor(self, who: str, enable: bool) -> Self:
        """
        监听/取消监听指定好友的消息
        :param who: 要监控的好友昵称
        :param enable: 是否监听, True: 监听, False: 取消监听
        """
        CommonUtil.printLog(f'monitor({who}, {enable})')
        if enable:
            self.wxauto.AddListenChat(nickname=who, callback=WeChatUtil._on_message)
            self.wxauto_monitor_names.add(who)
        else:
            self.wxauto.RemoveListenChat(nickname=who)
            self.wxauto_monitor_names.remove(who)
        return self

    @staticmethod
    def _on_message(msg: Message, chat: Chat):

        # 示例1：将消息记录到本地文件
        msg_content = msg.content
        if msg_content == '以下为新消息':
            return

        CommonUtil.printLog(f'_on_message: {chat.who}: {msg_content}')
        # with open('msgs.txt', 'a', encoding='utf-8') as f:
        #     f.write(msg.content + '\n')

        # 示例2：自动下载图片和视频
        if msg.type in ('image', 'video'):
            CommonUtil.printLog(msg.download())

        # # 示例3：自动回复收到
        # if isinstance(msg, FriendMessage):
        #     msg.quote('收到')


if __name__ == '__main__':
    wechat = WeChatUtil()
    # wechat.start_monitor('Lynxz')
    # wechat.start_monitor('小佛爷')
    # TimeUtil.sleep(60)
    # wechat.stop()
    # TimeUtil.sleep(3)
    # test_main()

    # # 初始化微信实例
    # wx = WeChat()
    #
    # # 发送消息
    # wx.SendMsg("你好", who="Lynxz")
    #
    # # 获取当前聊天窗口消息
    # msgs = wx.GetAllMessage()
    # for msg in msgs:
    #     print(f"消息内容: {msg.content}, 消息类型: {msg.type}")

    # 监听消息
    wechat.send_msg('Lynxz', '测试12345')
    wechat.monitor('Lynxz', True)
    TimeUtil.sleep(30)
    wechat.stop()
