# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
自动push本地指定分支代码
具体以 config.ini 文件配置信息为准
"""

import os
import re
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util.GitUtil import GitUtil
from util.CommonUtil import CommonUtil
from util import NetUtil

from base.BaseConfig import BaseConfig


class PushImpl(BaseConfig):

    def run(self):
        # push成功的字符串匹配模板
        pushSuccessPatternArr = [r'completed with \d+ local objects', r'Everything up-to-date']

        settings = self.configParser.getSectionItems('settings')
        codeReview = 'True' == settings['code_review']  # push时是否需要触发代码评审
        pushOptions = settings['code_review_opts']  # push命令额外的参数

        failDict = list()
        branches = self.configParser.getSectionItems('repository')
        for branch, localRepoPath in branches.items():
            print("targetBranch=%s,repoPath=%s" % (branch, localRepoPath))
            repoArr = localRepoPath.split(',')  # 可能多个本地仓库目录待提交分支名相同
            for repo in repoArr:
                gitUtil = GitUtil(remotePath='', localPath=repo, branch=None)
                status = gitUtil.getStatus()
                curBranch = gitUtil.getCurBranch()

                if branch != curBranch:  # 分支不一致,可能有代码未提交
                    nothingToCommit = 'nothing to commit' in status  # 是否已全部提交
                    print('当前分支%s并非目标分支%s,nothingToCommit=%s' % (curBranch, branch, nothingToCommit))
                    if nothingToCommit:  # 切换到目标分支
                        print('当前分支代码已全部提交, 切换到目标分支...')
                        gitUtil.checkoutBranch(branch)
                        status = gitUtil.getStatus()
                        curBranch = gitUtil.getCurBranch()
                    else:
                        print('当前分支有代码未commit, 等待人工处理, 脚本跳过...')
                        failDict.append(repo)
                        continue

                nothingToCommit = 'nothing to commit' in status  # 是否已全部提交
                aheadOfRemote = 'Your branch is ahead of' in status  # 是否比远程仓库代码更新
                print('curBranch=%s,nothingToCommit=%s,aheadOfRemote=%s' % (curBranch, nothingToCommit, aheadOfRemote))

                if nothingToCommit:  # 本地分支已全部commit, 则拉取最新代码,并获取status信息
                    status = gitUtil.updateBranch().getStatus()  # 更新代码, 提取最新的status信息
                    nothingToCommit = 'nothing to commit' in status  # 是否已全部提交
                    aheadOfRemote = 'Your branch is ahead of' in status  # 是否比远程仓库代码更新
                else:  # 本地有代码未提交, 则不作处理, 等待人工提交
                    print('当前分支有代码未commit,不自动push,请人工提交')
                    failDict.append(repo)
                    continue

                print('curBranch=%s,nothingToCommit=%s,aheadOfRemote=%s' % (curBranch, nothingToCommit, aheadOfRemote))
                if nothingToCommit and aheadOfRemote:  # 本地分支更新, 则需要push到远程仓库
                    print('push当前分支到远程: %s --> %s' % (branch, repo))
                    result = gitUtil.pushBranch(codeReview=codeReview, options=pushOptions)
                    for pattern in pushSuccessPatternArr:
                        pushResult = re.search(pattern, result, re.I)  # 忽略大小写比较
                        if pushResult is not None:  # 匹配成功, 即push成功
                            break
                elif not nothingToCommit:
                    print('当前分支有代码未commit,不自动push,请人工提交')
                elif not aheadOfRemote:
                    print('当前分支无代码变更,无需push')

        # 发送钉钉通知, 仅汇总失败的目录,提醒进行人工处理
        robotSection = self.configParser.getSectionItems('robot')
        token = robotSection['accessToken']
        if not CommonUtil.isNoneOrBlank(token):
            content = robotSection['keyWord']
            atPhoneList = robotSection['atPhone'].split(',')
            content += '\n已完成自动push流程'
            failInfo = '\n\t'.join(failDict).strip()
            if not CommonUtil.isNoneOrBlank(failInfo):
                content += '\n失败的目录如下,请人工处理:\n\t%s' % failInfo
            print(NetUtil.push_ding_talk_robot(content, token, False, atPhoneList))
        print('自动push代码结束')
