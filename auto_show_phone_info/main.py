# !/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
将设备信息绘制在图片上,并在手机上显示
具体以 config.ini 文件配置信息为准
"""
import os
import sys

proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from auto_show_phone_info.show_phone_info import ShowPhoneInfoImpl

if __name__ == "__main__":
    # 默认使用当前目录下的 config.ini 文件路径
    curDirPath = os.path.abspath(os.path.dirname(__file__))
    configPath = '%s/config.ini' % curDirPath
    ShowPhoneInfoImpl(configPath, optFirst=True, delimiters='=').run()
