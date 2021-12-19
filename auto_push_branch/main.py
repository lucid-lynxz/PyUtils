"""
自动push本地指定分支代码
具体以 config.ini 文件配置信息为准
"""
import getopt
import os
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_push_branch.PushImpl import PushImpl

if __name__ == "__main__":
    # 默认使用当前目录下的 config.ini 文件路径
    configPath = '%s/config.ini' % os.getcwd()

    # 触发更新
    PushImpl(configPath, optFirst=True).run()
