# !/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
根据指定的服务器信息, 批量上传/下载目录文件
具体以 config.ini 文件配置信息为准
"""
import os
import sys

from auto_up_down_load.UpDownloadImpl import UpDownloadImpl

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

if __name__ == "__main__":
    # 默认使用当前目录下的 config.ini 文件路径
    curDirPath = os.path.abspath(os.path.dirname(__file__))
    configPath = '%s/config.ini' % curDirPath

    # 触发更新
    UpDownloadImpl(configPath, optFirst=True).run()
