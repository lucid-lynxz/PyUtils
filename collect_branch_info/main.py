# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
收集分支信息,包括首次提交时间, commitId,最新提交时间及commitId, commitAuthor列表等, 见 BranchInfo 类
具体以 config.ini 文件配置信息为准
"""
import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from collect_branch_info.CollectBranchInfoImpl import CollectBranchInfoImpl

if __name__ == "__main__":
    # 默认使用当前目录下的 config.ini 文件路径
    curDirPath = os.path.abspath(os.path.dirname(__file__))
    configPath = '%s/config.ini' % curDirPath
    CollectBranchInfoImpl(configPath, optFirst=True).run()
