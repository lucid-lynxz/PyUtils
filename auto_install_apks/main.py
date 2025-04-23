# !/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
自动对多设备安装多个apk,并执行特定的命令
具体以 config.ini 文件配置信息为准
"""
import os
import sys

from auto_install_apks.AutoInstallApksImpl import AutoInstallApksImpl

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

if __name__ == "__main__":
    # 默认使用当前目录下的 config.ini 文件路径
    curDirPath = os.path.abspath(os.path.dirname(__file__))
    configPath = '%s/config.ini' % curDirPath

    # 触发实际操作
    AutoInstallApksImpl(configPath, optFirst=True).run()
