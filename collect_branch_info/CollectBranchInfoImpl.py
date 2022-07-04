# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
收集分支信息,包括首次提交时间, commitId,最新提交时间及commitId, commitAuthor列表等, 见 BranchInfo 类
具体以 config.ini 文件配置信息为准
"""
import os
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util.GitUtil import GitUtil, BranchInfo, CommitInfo
from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil
from util.TimeUtil import TimeUtil

from base.BaseConfig import BaseConfig


class CollectBranchInfoImpl(BaseConfig):

    def run(self):
        repository = self.configParser.getSectionItems('repository')
        setting = self.configParser.getSectionItems('setting')
        srcBranchInfo = self.configParser.getSectionItems('srcBranchInfo')

        outputFile: str = setting['outputResultFile']
        sinceDate: str = setting['sinceDate']
        untilDate: str = setting['untilDate']
        gitLogDateFormat = '%Y-%m-%d'  # git log和日期比较时使用的格式
        outputDateFormat: str = setting['outputDateFormat']  # 输出结果日期时使用的格式
        onlyCollectSrcBranchInfo = setting['onlyCollectSrcBranchInfo'] == 'True'
        maxBranchCount = 0 if onlyCollectSrcBranchInfo else int(setting['maxBranchCount'])  # 最多提取的分支数

        # 不做提取的分支名
        excludeBranchDict: dict = {}
        excludeBranch: str = setting['excludeBranch']
        for eBranch in excludeBranch.split(','):
            excludeBranchDict[eBranch.strip()] = ''
        FileUtil.write2File(outputFile, '分支名,创建日期,commitId,最近提交日期,commitId,源分支,总提交数,参与提交的人员')

        gitUtil = GitUtil(repository['remote'],
                          repository['local'],
                          repository['initBranch']).updateBranch().formatLogDate(dateFormat=gitLogDateFormat)

        # 若未指定分支信息,则统计所有分支
        validBranchCount = 0  # 已提取有效信息的分支数
        if len(srcBranchInfo.items()) == 0 or not onlyCollectSrcBranchInfo:
            # 所有远程分支列表, 按commit时间降序
            rBranchList = gitUtil.getBranchList('-r --sort=-committerdate')
            print("---> all remote branches: %s" % len(rBranchList))
            print(rBranchList)
            # 删除 'origin/' 前缀后, 加入到分支dict中, 源分支默认为空
            tBranchInfoDict: dict = {}
            for rBranch in rBranchList:
                if rBranch in excludeBranchDict or CommonUtil.isNoneOrBlank(rBranch):
                    print('不统计该分支: %s' % rBranch)
                    continue

                if 0 < maxBranchCount <= validBranchCount:
                    break
                validBranchCount += 1

                tBranchName = rBranch[(len(gitUtil.remoteRepositoryName) + 1):]
                tSrcBranch = srcBranchInfo.get(tBranchName, '')
                tBranchInfoDict[tBranchName] = tSrcBranch
            srcBranchInfo = tBranchInfoDict  # 只保留符合条件的分支信息

        progress = 0
        total = len(srcBranchInfo.items())
        for targetBranch, srcBranch in srcBranchInfo.items():
            progress += 1
            print('当前进度: %s/%s branch=%s' % (progress, total, targetBranch))

            if targetBranch in excludeBranchDict or CommonUtil.isNoneOrBlank(targetBranch):
                print('不统计该分支: %s' % targetBranch)
                continue

            branchInfo = BranchInfo()
            branchInfo.branchNameLocal = targetBranch  # 本地分支名
            branchInfo.branchNameRemote = gitUtil.getRemoteBranchName(targetBranch)
            branchInfo.authorList = gitUtil.getAllAuthorName(since=sinceDate, until=untilDate)

            # 获取最新提交信息
            branchInfo.headCommitInfo = gitUtil.getCommitInfo(targetBranch)

            # 获取分支首次提交信息, 要求源分支信息非空
            if not CommonUtil.isNoneOrBlank(srcBranch):
                branchInfo.srcBranchName = srcBranch
                firstCommitId = gitUtil.getFirstCommitId(srcBranch, targetBranch)
                branchInfo.firstCommitInfo = gitUtil.getCommitInfo(firstCommitId)

            # 根据指定的日期区间, 计算commit总数
            if CommonUtil.isNoneOrBlank(sinceDate):
                sinceDate = branchInfo.firstCommitInfo.date
            elif TimeUtil.dateDiff(sinceDate, branchInfo.firstCommitInfo.date, dateFormat=gitLogDateFormat) < 0:
                sinceDate = branchInfo.firstCommitInfo.date

            sinceDateOpt = '' if CommonUtil.isNoneOrBlank(sinceDate) else '--since=%s' % sinceDate
            untilDateOpt = '' if CommonUtil.isNoneOrBlank(untilDate) else '--until=%s' % untilDate
            gitCmd = 'log %s %s --oneline' % (sinceDateOpt, untilDateOpt)
            cmdResult = gitUtil.checkoutBranch(targetBranch).exeGitCmd(gitCmd)
            commitLines = cmdResult.splitlines()
            commitCount = len(commitLines)

            # 用户指定了起始日期, 则重新计算第一次提交信息
            if not CommonUtil.isNoneOrBlank(sinceDate):
                if commitCount == 0:
                    branchInfo.firstCommitInfo = CommitInfo()
                else:
                    firstCommitId = commitLines[-1].split(" ")[0]
                    branchInfo.firstCommitInfo = gitUtil.getCommitInfo(firstCommitId)

            # 用户指定了截止期间, 则重新计算最后一次提交信息
            if not CommonUtil.isNoneOrBlank(untilDate):
                if commitCount == 0:
                    branchInfo.firstCommitInfo = CommitInfo()
                else:
                    headCommitId = commitLines[0].split(" ")[0]
                    branchInfo.headCommitInfo = gitUtil.getCommitInfo(headCommitId)

            # 记录分支信息
            # '分支名,创建日期,commitId,最近提交日期,commitId,源分支,总提交数'
            FileUtil.append2File(outputFile, '%s,%s,%s,%s,%s,%s,%s,%s' % (
                branchInfo.branchNameRemote,
                TimeUtil.convertFormat(branchInfo.firstCommitInfo.date, gitLogDateFormat, outputDateFormat),
                branchInfo.firstCommitInfo.id,
                TimeUtil.convertFormat(branchInfo.headCommitInfo.date, gitLogDateFormat, outputDateFormat),
                branchInfo.headCommitInfo.id,
                branchInfo.srcBranchName,
                commitCount, " ".join(branchInfo.authorList)
            ))
