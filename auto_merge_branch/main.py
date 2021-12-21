"""
自动合并源分支代码到制定目标分支中, 如合并dev到release分支
具体以 config.ini 文件配置信息为准
"""
import os
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_merge_branch.MergeImpl import MergeImpl

if __name__ == "__main__":
    # 默认使用当前目录下的 config.ini 文件路径
    curDirPath = os.path.abspath(os.path.dirname(__file__))
    configPath = '%s/config.ini' % curDirPath

    # 触发更新
    MergeImpl(configPath, optFirst=True).run()
