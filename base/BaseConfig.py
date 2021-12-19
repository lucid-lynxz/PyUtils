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


class BaseConfig(Runnable):
    """
    带配置文件的类
    """

    def __init__(self, configPath: str,
                 configLongOpts: str = 'config',
                 optFirst: bool = False):
        """
        支持通过命令参数 --config 传入自定义的配置文件路径
        也可以直接通过沟通方法传入
        :param configPath: 配置文件路径
        :param configLongOpts:由外部通过参数传入时的参数名, 默认是 'config' 表示: --config
        :param optFirst: True-优先使用通过命令参数获取的路径, False-优先使用 configPath 值
        """

        # 优先提取外部传入的config.ini配置文件路径,若未设置,则使用当前目录下的默认值
        optPath: str = ''
        if not CommonUtil.isNoneOrBlank(configLongOpts):
            try:
                opts, args = getopt.getopt(sys.argv[1:], '', [configLongOpts])
                if opts is None or len(opts) == 0:
                    print("opts is none, use default config path=%s" % configPath)
                else:
                    for name, value in opts:
                        if name in ['--config']:
                            optPath = value
                            break
            except getopt.GetoptError as e:
                print("getopt error %s" % e)

        if CommonUtil.isNoneOrBlank(optPath):
            optPath = configPath

        if CommonUtil.isNoneOrBlank(configPath):
            configPath = optPath

        self.configPath = optPath if optFirst else configPath

        print('BaseConfig configPath=%s' % configPath)
        self.configParser = NewConfigParser().initPath(configPath)
