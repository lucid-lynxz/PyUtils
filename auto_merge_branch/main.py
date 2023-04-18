# !/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
自动合并源分支代码到制定目标分支中, 如合并dev到release分支
具体以 config.ini 文件配置信息为准
"""
import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from auto_merge_branch.MergeImpl import MergeImpl

if __name__ == "__main__":
    # 默认使用当前目录下的 config.ini 文件路径
    curDirPath = os.path.abspath(os.path.dirname(__file__))
    configPath = '%s/config.ini' % curDirPath

    # 触发更新
    MergeImpl(configPath, optFirst=True).run()
