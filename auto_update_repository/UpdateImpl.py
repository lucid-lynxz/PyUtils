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

from util.GitUtil import GitUtil
from util.CommonUtil import CommonUtil
from util.NetUtil import NetUtil
from util.FileUtil import FileUtil

from base.BaseConfig import BaseConfig

"""
自动更新指定目录及下一级目录下的git仓库代码
具体以 config.ini 文件配置信息为准
"""


class UpdateImpl(BaseConfig):

    def onRun(self):
        repository = self.configParser.getSectionItems('repository')
        local_dir_str = repository['local']

        # 检测仓库配置文件信息符合要求
        if CommonUtil.isNoneOrBlank(local_dir_str):  # `local` 本地仓库路径
            raise Exception('invalid local_dir path,please check %s' % self.configPath)

        # 获取 `local` 路径目录及其下一级目录
        local_dirs = [x.strip() for x in local_dir_str.split(",")]  # 待更新的根目录列表
        update_dirs = []  # 更新过的目录
        for lDir in local_dirs:
            target_dirs = FileUtil.listAllFilePath(lDir)
            target_dirs.append(lDir)

            # 遍历所有目录路径，若是git仓库，则进行更新
            for tDir in target_dirs:
                if FileUtil.isDirFile("%s/.git/" % tDir):  # 是个仓库
                    print('正在更新目录: %s' % tDir)
                    gitUtil = GitUtil(remotePath='', localPath=tDir)
                    status = gitUtil.getStatus()
                    nothingToCommit = 'nothing to commit' in status  # 是否已全部提交
                    if nothingToCommit:  # 切换到目标分支
                        print('当前分支代码已全部提交, 执行pull操作...')
                        gitUtil.updateBranch()
                        update_dirs.append(tDir)
                    else:
                        print('当前分支有代码未commit, 等待人工处理, 脚本跳过...')
                        continue

        # 钉钉通知审核人员进行合并
        robotSection = self.configParser.getSectionItems('robot')
        token = robotSection['accessToken']
        content = "%s\n%s" % (robotSection['keyWord'], robotSection['extraInfo'])
        content = content.strip()
        content += '\n已触发过更新的目录:\n%s' % '\n'.join(update_dirs)
        print(content)
        if CommonUtil.isNoneOrBlank(token):
            print('accessToken为空, 无需发送通知')
        else:
            atPhoneList = robotSection['atPhone'].split(',')
            print(NetUtil.push_ding_talk_robot(content, token, False, atPhoneList))
        print('自动更新代码结束')
