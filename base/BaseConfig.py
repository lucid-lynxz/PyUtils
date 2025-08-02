# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
自动更新指定目录及下一级目录下的git仓库代码
具体以 config.ini 文件配置信息为准
"""
import getopt
import os
import sys
from abc import abstractmethod

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from util.ConfigUtil import NewConfigParser
from util.CommonUtil import CommonUtil
from base.Interfaces import Runnable, TagGenerator
from util.FileUtil import FileUtil
from base.TaskManager import TaskManager, TaskParam, TaskLifeCycle
from extra_tasks.import_all import *  # 用于触发装饰器


class BaseConfig(Runnable, TagGenerator):
    """
    带配置文件的类
    可通过命令 --config 传入配置文件路径, 可以通过  --param sectionName.key=value 来动态修改/新增 参数
    子类可重写 [getPrintConfigSections] 返回一个 set() 来判断是否需要打印 config.ini 中指定 section 的内容
    子类需实现 [onRun] 方法,在里面实现具体功能
    """

    def __init__(self, configPath: str,
                 configLongOpt: str = 'config',
                 configShortOpt: str = 'c',
                 optFirst: bool = False,
                 configItemLongOpt: str = 'param',
                 configItemShortOpt: str = 'p',
                 splitFlag: str = '.',
                 delimiters=('=', ':')
                 ):
        """
        支持通过命令参数 --config 传入自定义的配置文件路径,也可以直接通过参数 configPath 传入
        支持通过命令参数 --param 传入配置参数, 优先级高于 config 文件
        :param configPath: 配置文件路径
        :param configLongOpt:由外部通过参数传入时的长参数名, 默认是 'config' 表示: --config
        :param configShortOpt:由外部通过参数传入时的短参数名, 默认是 'c' 表示: -c
        :param optFirst: True-优先使用通过命令参数获取的路径, False-优先使用 configPath 值
        :param configItemLongOpt: 长参数名, 用于替换 config.ini 中的数据, 默认为 'param'
                                    格式(不包括加号): --param sectionName+splitFlag+itmKey=itemValue
        :param configItemShortOpt: 短参数名, 默认为: 'p'
        :param splitFlag: 连接符,默认用点连接
        """
        CommonUtil.updateStdOutEncoding()  # 修改stdout为utf8编码
        # 优先提取外部传入的config.ini配置文件路径,若未设置,则使用当前目录下的默认值
        optPath: str = ''
        sectionItemValues = list()
        if not CommonUtil.isNoneOrBlank(configLongOpt):
            try:
                opts, args = getopt.getopt(sys.argv[1:], '%s:%s:' % (configShortOpt, configItemShortOpt),
                                           ['%s=' % configLongOpt, '%s=' % configItemLongOpt])
                if opts is None or len(opts) == 0:
                    print("opts is none, use default config path=%s" % configPath)
                else:
                    for name, value in opts:
                        if name in ['-%s' % configShortOpt, '--%s' % configLongOpt]:
                            optPath = value
                        elif name in ['-%s' % configItemShortOpt, '--%s' % configItemLongOpt]:
                            if splitFlag in value:
                                sectionItemValues.append(value)
            except getopt.GetoptError as e:
                print("getopt error %s" % e)

        if CommonUtil.isNoneOrBlank(optPath):
            optPath = configPath

        if CommonUtil.isNoneOrBlank(configPath):
            configPath = optPath

        self.configPath = optPath if optFirst else configPath

        print('\nconfigPath=%s' % configPath)
        print(''.join(FileUtil.readFile(self.configPath)))
        self.configParser = NewConfigParser(allow_no_value=True, delimiters=delimiters).initPath(self.configPath)

        # 更新 config.ini 属性值
        if len(sectionItemValues) > 0:
            for item in sectionItemValues:
                arr = item.split(splitFlag)
                if len(arr) < 2:  # 要求至少包含 sectionName 和 itemKey
                    continue
                sectionName = arr[0]
                kv = splitFlag.join(arr[1:])
                arr = kv.split('=')
                itemKey = arr[0]
                itemValue = '='.join(arr[1:]) if len(arr) >= 2 else ''
                self.configParser.updateSectonItem(sectionName, itemKey, itemValue)

        self.configParser.updateSectonItem(TaskParam.runtimeParamSectionName, "", "")
        self.taskParam = TaskParam()
        self.taskParam.configParser = self.configParser
        self.taskParam.implementationObj = self

        for task in TaskManager.getTaskList(self.getTag(), taskLifeCycle=TaskLifeCycle.afterConfigInit):
            task(self.taskParam)

        # 按需打印 config.ini 中的信息(注释以及key, value则是实际生效的值(即通过--param注入后的最新值))
        self._printConfigDetail()

    def update_delimiters(self, delimiters=('=')):
        # 修改config.ini使用的分隔符,改为使用 '=' 作为分隔符
        self.configParser = NewConfigParser(
            allow_no_value=True,
            delimiters=delimiters  # 关键：仅将 '=' 视为键值分隔符，忽略 ':'
        ).initPath(self.configPath)

        # 重建配置缓存（若 NewConfigParser 依赖 _cache 属性）
        self.configParser._cache = {}
        for sectionName in self.configParser.sections():
            self.configParser._cache[sectionName] = self.configParser.getSectionItems(sectionName)

    def run(self):
        print('\n')
        taskList = TaskManager.getTaskList(self.getTag(), taskLifeCycle=TaskLifeCycle.beforeRun)
        for task in taskList:
            task(self.taskParam)

        self.onRun()

        taskList = TaskManager.getTaskList(self.getTag(), taskLifeCycle=TaskLifeCycle.afterRun)
        for task in taskList:
            task(self.taskParam)

    def isTaskExist(self, taskLifeCycle: TaskLifeCycle) -> bool:
        """
        判断指定生命周期阶段是否有额外的task需要执行
        """
        taskList = TaskManager.getTaskList(self.getTag(), taskLifeCycle=TaskLifeCycle.afterRun)
        return taskList is not None and len(taskList) > 0

    @abstractmethod
    def onRun(self):
        """"
        子类实现该方法, 进行功能完成
        """
        pass

    def getTag(self) -> str:
        """
        实现类的唯一标识信息, 默认为实现类的类名
        """
        # print('getTag()=%s' %  type(self).__name__)
        return type(self).__name__

    def getPrintConfigSections(self) -> set:
        """
        要打印的 config.ini section信息列表
        :return: set 元素是str, 表示 config.ini 中Section名称
         - 返回 None 表示都不打印
         - 返回空list, 则打印全部内容
         - 返回非空list, 则只打印指定的section信息
        """
        return None

    def _printConfigDetail(self):
        allLines = FileUtil.readFile(self.configPath)
        if len(allLines) == 0:
            return

        printSectionSet = self.getPrintConfigSections()
        if printSectionSet is None:  # 返回 None 表示不打印
            return

        if len(printSectionSet) == 0:  # 返回空列表表示打印全部内容
            # print('all config content is:\n%s' % ''.join(allLines))
            printSectionSet = set(self.configParser.sections())

        shouldPrint = False  # 当前section西西里是否需要打印
        curSectionName = ''  # 当前section名称
        hashPrintKeySet = set()  # 已经打印的key信息,用于最后打印未在config.ini中设置,而是通过 --param 传入的新增参数
        lineCount = len(allLines)

        def _printOtherSectonKV():
            """
            打印当前section的其他信息(未在 config.ini 中定义, 而是由 --param 动态传入的新增参数)
            """
            lastSectonDict = self.configParser.getSectionItems(curSectionName)
            hasPrintTip = False
            for key in lastSectonDict:
                if key in hashPrintKeySet:
                    continue
                if not hasPrintTip:
                    print('\n# 其他动态新增的参数如下:')
                    hasPrintTip = True
                print('%s=%s' % (key, lastSectonDict.get(key, '')))
            if hasPrintTip:
                print('')

        for index in range(lineCount):
            line = ('%s' % allLines[index]).strip()
            # 检测当前行信息是 section
            curLineIsASectionName = line.startswith('[') and line.endswith(']') and len(line) > 3

            if shouldPrint and curLineIsASectionName:
                # 在打印下一个 section 信息前先把前一个section的其他参数一并打印出来
                _printOtherSectonKV()

            if curLineIsASectionName:
                curSectionName = line[1:-1]
                shouldPrint = curSectionName in printSectionSet
                hashPrintKeySet = set()

            if shouldPrint:
                # section行/空白行/注释行(#开头)则直接打印
                if curLineIsASectionName \
                        or CommonUtil.isNoneOrBlank(line) \
                        or line.startswith('#'):
                    print(line)
                else:  # key-value 行信息,则更新value值为最新值
                    arr = line.split('=')
                    key = arr[0].strip()
                    value = self.configParser.getSectionItems(curSectionName).get(key, '')
                    print('%s=%s' % (key, value))
                    hashPrintKeySet.add(key)

                # 当前已是最后一行,则打印动态传入本section的其他参数信息
                if index == lineCount - 1:
                    _printOtherSectonKV()
