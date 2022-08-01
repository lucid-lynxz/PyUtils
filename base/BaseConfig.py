# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
自动更新指定目录及下一级目录下的git仓库代码
具体以 config.ini 文件配置信息为准
"""
import getopt
import os
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util.ConfigUtil import NewConfigParser
from util.CommonUtil import CommonUtil
from base.Runnable import Runnable
from util.FileUtil import FileUtil


class BaseConfig(Runnable):
    """
    带配置文件的类
    """

    def __init__(self, configPath: str,
                 configLongOpt: str = 'config',
                 configShortOpt: str = 'c',
                 optFirst: bool = False,
                 configItemLongOpt: str = 'param',
                 configItemShortOpt: str = 'p',
                 splitFlag: str = '.'
                 ):
        f"""
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

        print('BaseConfig configPath=%s' % configPath)
        print('content is:\n%s' % ''.join(FileUtil.readFile(self.configPath)))
        self.configParser = NewConfigParser(allow_no_value=True).initPath(self.configPath)

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
                itemValue = splitFlag.join(arr[1:]) if len(arr) >= 2 else ''
                self.configParser.updateSectonItem(sectionName, itemKey, itemValue)
