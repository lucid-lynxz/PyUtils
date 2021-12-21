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
        pushSuccessPatternArr = [r'completed with \d+ local objects',
                                 r'Everything up-to-date',
                                 r'Merge Request #\d+ was created or updated']

        settings = self.configParser.getSectionItems('settings')
        codeReview = 'True' == settings['code_review']  # push时是否需要触发代码评审
        pushOptions = settings['code_review_opts']  # push命令额外的参数

        nothingCommitList = list()  # 本地与服务端代码一致, 无变更了,无需push
        failList = list()  # push失败或者本地有改动未commit导致无法push等情况
        successList = list()  # push成功的信息列表
        unknownList = list()  # push命令返回结果为空,无法判断是否正常
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
                        failList.append('%s %s' % (branch, repo))
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
                    failList.append('%s %s' % (branch, repo))
                    continue

                print('curBranch=%s,nothingToCommit=%s,aheadOfRemote=%s' % (curBranch, nothingToCommit, aheadOfRemote))
                if nothingToCommit and aheadOfRemote:  # 本地分支更新, 则需要push到远程仓库
                    print('push当前分支到远程: %s --> %s' % (branch, repo))
                    result = gitUtil.pushBranch(codeReview=codeReview, options=pushOptions)
                    if CommonUtil.isNoneOrBlank(result):
                        unknownList.append('%s %s' % (branch, repo))
                    else:
                        success = False
                        for pattern in pushSuccessPatternArr:
                            pushResult = re.search(pattern, result, re.I)  # 忽略大小写比较
                            if pushResult is not None:  # 匹配成功, 即push成功
                                successList.append('%s %s' % (branch, repo))
                                success = True
                                break
                        if not success:
                            failList.append('%s %s' % (branch, repo))
                elif not nothingToCommit:
                    nothingCommitList.append('%s %s' % (branch, repo))
                    print('当前分支有代码未commit,不自动push,请人工提交:%s' % curBranch)
                elif not aheadOfRemote:
                    nothingCommitList.append('%s %s' % (branch, repo))
                    print('当前分支无代码变更,无需push:%s' % curBranch)

        # 发送钉钉通知, 仅汇总失败的目录,提醒进行人工处理
        robotSection = self.configParser.getSectionItems('robot')
        content = "%s\n%s" % (robotSection['keyWord'], robotSection['extraInfo'])
        content += '\n已完成自动push流程'
        failInfo = '\n\t'.join(failList).strip()
        successInfo = '\n\t'.join(successList).strip()
        unknownInfo = '\n\t'.join(unknownList).strip()
        nothingCommitInfo = '\n\t'.join(nothingCommitList).strip()
        if not CommonUtil.isNoneOrBlank(failInfo):
            content += '\n失败的目录如下,请人工处理:\n\t%s' % failInfo
        if not CommonUtil.isNoneOrBlank(successInfo):
            content += '\n成功的目录如下:\n\t%s' % successInfo
        if not CommonUtil.isNoneOrBlank(unknownInfo):
            content += '\npush命令结果为空的目录如下, 请自行判断:\n\t%s' % unknownInfo
        if not CommonUtil.isNoneOrBlank(nothingCommitInfo):
            content += '\n代码无变更,无需push的目录如下:\n\t%s' % nothingCommitInfo
        print(content)

        token = robotSection['accessToken']
        if CommonUtil.isNoneOrBlank(token):
            print('accessToken为空, 无需发送通知')
        else:
            atPhoneList = robotSection['atPhone'].split(',')
            print(NetUtil.push_ding_talk_robot(content, token, False, atPhoneList))
        print('自动push代码结束')
