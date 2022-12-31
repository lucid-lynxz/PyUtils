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
from util.NetUtil import NetUtil

from base.BaseConfig import BaseConfig


class PushImpl(BaseConfig):

    def _addRepoPathInfo(self, targetList: list, branchName: str,
                         repoPath: str, ignorePath: bool,
                         prefix: str = '\t'):
        """
        用于汇总push结果时,是否需要显示分支对应的仓库路径
        若该分支只对应一个仓库,则可不显示仓库路径
        """
        tRepoPath = '' if ignorePath else '%s%s' % (prefix, repoPath)
        length = len(targetList)
        if length == 0:
            targetList.append('%s%s' % (branchName, '' if CommonUtil.isNoneOrBlank(tRepoPath) else '\n%s' % tRepoPath))
        else:
            lastItem = targetList[-1]
            lastBranch = lastItem.split()[0]
            if branchName == lastBranch:  # 与上一条记录的分支名相同,则仅记录仓库路径即可
                targetList.append(tRepoPath)
            else:
                targetList.append('%s%s' % (branchName, tRepoPath))

    def onRun(self):
        # push成功的字符串匹配模板
        pushSuccessPatternArr = [r'completed with \d+ local objects',
                                 r'Everything up-to-date',
                                 r'Merge Request #\d+ was created or updated']

        settings = self.configParser.getSectionItems('settings')
        codeReview = 'True' == settings['code_review']  # push时是否需要触发代码评审
        pushOptions = settings['code_review_opts']  # push命令额外的参数
        updateByRebase = 'True' == settings['update_branch_by_rebase']  # 是否使用 rebase 更新代码
        pushOnlyFileChange = 'True' == settings['push_only_file_change']  # 与远程分支间存在文件变更时才可push

        cannotPushList = list()  # 有代码未commit,无法push
        nothingCommitList = list()  # 本地与服务端代码一致, 无变更,无需push
        failList = list()  # push失败或者本地有改动未commit导致无法push等情况
        successList = list()  # push成功的信息列表
        unknownList = list()  # push命令返回结果为空,无法判断是否正常
        branches = self.configParser.getSectionItems('repository')
        for branch, localRepoPath in branches.items():
            print("targetBranch=%s,repoPath=%s" % (branch, localRepoPath))
            repoArr = localRepoPath.split(',')  # 可能多个本地仓库目录待提交分支名相同
            hasMultiRepo = len(repoArr) > 1  # 是否有多个仓库对应同一个分支名

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
                        self._addRepoPathInfo(cannotPushList, branch, repo, not hasMultiRepo)
                        continue

                nothingToCommit = 'nothing to commit' in status  # 是否已全部提交
                aheadOfRemote = 'Your branch is ahead of' in status  # 是否比远程仓库代码更新
                print('curBranch=%s,nothingToCommit=%s,aheadOfRemote=%s' % (curBranch, nothingToCommit, aheadOfRemote))

                if nothingToCommit:  # 本地分支已全部commit, 则拉取最新代码,并获取status信息
                    status = gitUtil.updateBranch(byRebase=updateByRebase).getStatus()  # 更新代码, 提取最新的status信息
                    nothingToCommit = 'nothing to commit' in status  # 是否已全部提交
                    aheadOfRemote = 'Your branch is ahead of' in status  # 是否比远程仓库代码更新
                else:  # 本地有代码未提交, 则不作处理, 等待人工提交
                    print('当前分支有代码未commit,不自动push,请人工提交')
                    self._addRepoPathInfo(cannotPushList, branch, repo, not hasMultiRepo)
                    continue

                # 判断是否有实际的文件变更,有再发起提交
                localCommitId = gitUtil.getCommitId(curBranch)
                remoteCommitId = gitUtil.getCommitId(gitUtil.getRemoteBranchName(curBranch), remote=True)
                diffFiles = gitUtil.getDiffInfo(localCommitId, remoteCommitId)
                same = CommonUtil.isNoneOrBlank(diffFiles)

                print('curBranch=%s,nothingToCommit=%s,aheadOfRemote=%s,same=%s,diffFiles=%s' % (
                    curBranch, nothingToCommit, aheadOfRemote, same, diffFiles))

                if aheadOfRemote and (not pushOnlyFileChange or not same):  # 本地分支更新, 则需要push到远程仓库
                    print('push当前分支到远程: %s --> %s' % (branch, repo))
                    result = gitUtil.pushBranch(codeReview=codeReview, options=pushOptions)
                    print('push result:%s' % result)
                    if CommonUtil.isNoneOrBlank(result):  # push命令无输出信息,无法判断是否成功
                        self._addRepoPathInfo(unknownList, branch, repo, not hasMultiRepo)
                    else:
                        success = False
                        for pattern in pushSuccessPatternArr:
                            pushResult = re.search(pattern, result, re.I)  # 忽略大小写比较
                            if pushResult is not None:  # 匹配成功, 即push成功
                                self._addRepoPathInfo(successList, branch, repo, not hasMultiRepo)
                                success = True
                                break
                        if not success:
                            self._addRepoPathInfo(failList, branch, repo, not hasMultiRepo)
                else:
                    self._addRepoPathInfo(nothingCommitList, branch, repo, not hasMultiRepo)
                    print('当前分支无代码变更,无需push:%s' % curBranch)

        # 发送钉钉通知, 仅汇总失败的目录,提醒进行人工处理
        robotSection = self.configParser.getSectionItems('robot')
        content = "%s\n%s" % (robotSection['keyWord'], robotSection['extraInfo'])
        content = content.strip()
        content += '\n已完成自动push流程'
        failInfo = '\n '.join(failList).strip()
        cannotPushInfo = '\n '.join(cannotPushList).strip()
        successInfo = '\n '.join(successList).strip()
        unknownInfo = '\n '.join(unknownList).strip()
        nothingCommitInfo = '\n '.join(nothingCommitList).strip()
        if not CommonUtil.isNoneOrBlank(successInfo):
            content += '\np成功的分支 %s 个:\n %s' % (len(successList), successInfo)
        if not CommonUtil.isNoneOrBlank(nothingCommitInfo):
            content += '\n代码无变更,无需push的分支 %s 个' % len(nothingCommitList)
            # content += '\n代码无变更,无需push的分支 %s 个:\n %s' % (len(nothingCommitList), nothingCommitInfo)
        if not CommonUtil.isNoneOrBlank(cannotPushInfo):
            content += '\n未commit的分支 %s 个,请处理后重试:\n %s' % (len(cannotPushList), cannotPushInfo)
        if not CommonUtil.isNoneOrBlank(failInfo):
            content += '\n失败的分支 %s 个,请人工处理:\n %s' % (len(failList), failInfo)
        if not CommonUtil.isNoneOrBlank(unknownInfo):
            content += '\npush结果为空的分支 %s 个, 请自行判断:\n %s' % (len(unknownList), unknownInfo)
        if not CommonUtil.isNoneOrBlank(settings['codeReviewUrl']):
            content += '\n代码评审地址:\n%s' % settings['codeReviewUrl']
        print(content)

        token = robotSection['accessToken']
        if CommonUtil.isNoneOrBlank(token):
            print('accessToken为空, 无需发送通知')
        else:
            atPhoneList = robotSection['atPhone'].split(',')
            print(NetUtil.push_ding_talk_robot(content, token, False, atPhoneList))
        print('自动push代码结束')
