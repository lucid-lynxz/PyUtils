# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
自动更新指定目录及下一级目录下的git仓库代码
具体以 config.ini 文件配置信息为准
"""
import os
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util.ConfigUtil import NewConfigParser
from util.GitUtil import GitUtil
from util.CommonUtil import CommonUtil
from util.NetUtil import push_ding_talk_robot
from util import FileUtil

if __name__ == '__main__':
    configPath = '%s/config.ini' % os.getcwd()
    configParser = NewConfigParser().initPath(configPath)
    repository = configParser.getSectionItems('repository')
    local_dir_str = repository['local']

    # 检测仓库配置文件信息符合要求
    if CommonUtil.isNoneOrBlank(local_dir_str):  # `local` 本地仓库路径
        raise Exception('invalid local_dir path,please check %s' % configPath)

    # 获取 `local` 路径目录及其下一级目录
    local_dirs = [x.strip() for x in local_dir_str.split(",")]  # 待更新的根目录列表
    update_dirs = []  # 更新过的目录
    for lDir in local_dirs:
        target_dirs = FileUtil.listAllFilePath(lDir)
        target_dirs.append(lDir)

        # 遍历所有目录¡路径，若是git仓库，则进行更新
        for tDir in target_dirs:
            if FileUtil.isDirFileExist("%s/.git/" % tDir):  # 是个仓库
                print('正在更新目录: %s' % tDir)
                GitUtil(remotePath='', localPath=tDir).updateBranch()
                update_dirs.append(tDir)

    # 钉钉通知审核人员进行合并
    robotSection = configParser.getSectionItems('robot')
    token = robotSection['accessToken']
    if not CommonUtil.isNoneOrBlank(token):
        content = robotSection['keyWord']
        atPhoneList = robotSection['atPhone'].split(',')
        content += '\n已触发过更新的目录:\n%s' % '\n'.join(update_dirs)
        print(push_ding_talk_robot(content, token, False, atPhoneList))
    print('自动更新代码结束')
