# !/usr/bin/env python3
# -*- coding:utf-8 -*-


import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from enum import Enum


class TaskLifeCycle(Enum):
    """
    可注入的生命周期信息
    """
    # config.ini 组装结束后回调
    afterConfigInit = 0

    # onRun() 方法执行前回调
    beforeRun = 1

    # onRun() 方法执后回调
    afterRun = 2

    # 自定义生命周期, 各脚本依据tag按需触发
    custom = 3


def taskWrapper(tag: str, taskLifeCycle: TaskLifeCycle):
    """
    装饰器,用于将自定义的额外处理方法加入 TaskManager 中
    :param tag: 唯一标识信息,默认为 BaseConfig 子类的类名
    :param taskLifeCycle: func执行阶段, 参考枚举: TaskLifeCycle
    """

    def deco_fun(func):
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)

        TaskManager.addTask(tag, taskLifeCycle, func)
        # print('taskWrapper run %s' % func)
        return wrapper

    return deco_fun


class TaskParam(object):
    """
    传递给task函数的参数
    """

    #  运行过程中添加参数到 configParser 中该section, 方便 extra_tasks 获取
    runtimeParamSectionName = "runtimeSectionParam"

    def __init__(self):
        from base.BaseConfig import NewConfigParser
        self.configParser: NewConfigParser = None  # 配置参数对象
        self.implementationObj = None  # 对应的实现脚本对象, 通常是 BaseConfig 子类
        self.files = list()  # 文件路径信息,可能有多条, 元素是字符串, 表示路径
        self.params = dict()


class TaskManager(object):
    tasks: dict = dict()  # key-模块标记tag+lifeCycle value-list() list元素为 func 对象

    @staticmethod
    def __generateTaskId(tag: str, taskLifeCycle: TaskLifeCycle) -> str:
        return '%s_%s' % (tag, taskLifeCycle.value)

    @staticmethod
    def getTaskList(tag: str, taskLifeCycle: TaskLifeCycle) -> list:
        """
        获取指定tag和生命周期阶段的task函数列表
        :param tag: 模块的 getTag() 返回值
        :param taskLifeCycle: 要注入的生命周期, 参考枚举类: TaskLifeCycle
        :return: list, 元素是待注入该生命周期的函数
        """
        taskId = TaskManager.__generateTaskId(tag, taskLifeCycle)
        # print('getTaskList %s' % taskId)
        tagTasks = TaskManager.tasks.get(taskId, list())
        TaskManager.tasks[taskId] = tagTasks
        return tagTasks

    @staticmethod
    def addTask(tag: str, taskLifeCycle: TaskLifeCycle, taskFunc):
        """
        添加函数到指定模块的生命周期中
        """
        TaskManager.getTaskList(tag, taskLifeCycle).append(taskFunc)
