# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
自动合并分支代码
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

from base.BaseConfig import BaseConfig


class MergeResult(object):
    """
    合并处理结果
    """

    def __init__(self, branchName: str):
        self.branch: str = branchName  # 分支名
        self.oriCommitId: str = ''  # merge前的commitId
        self.curCommitId: str = ''  # merge 后最新的 commitId
        self.isChanged: bool = False  # merge 前后文件内容是否有变更
        self.mergeSuccess: bool = True  # merge 时是否发生成功


class MergeImpl(BaseConfig):

    def onRun(self):
        repository = self.configParser.getSectionItems('repository')
        gitUtil = GitUtil(remotePath=repository['remote'], localPath=repository['local'],
                          branch=repository['initBranch'])

        resultDict = dict()

        settings = self.configParser.getSectionItems('settings')
        shouldCodeReview: bool = settings['code_review'] == 'True'
        codeReviewOpts: str = settings['code_review_opts']
        stargeOpt: str = settings['strategyOpt']
        shouldPush: bool = settings['push'] == 'True'
        updateByRebase = 'True' == settings['update_branch_by_rebase']  # 是否使用 rebase 更新代码

        branches = self.configParser.getSectionItems('branch')
        for targetBranch, srcBranch in branches.items():
            print("targetBranch=%s,srcBranch=%s" % (targetBranch, srcBranch))

            mergeResult = MergeResult(targetBranch)
            try:
                # oriCommitId为远程分支的最新commitId
                mergeResult.oriCommitId = gitUtil.checkoutBranch(srcBranch).updateBranch(byRebase=updateByRebase) \
                    .checkoutBranch(targetBranch).updateBranch(byRebase=updateByRebase).getCommitId(remote=True)
                # curCommitId为本地merge代码后的最新commitId
                mergeResult.curCommitId = gitUtil.mergeBranch(srcBranch, strategyOption=stargeOpt).getCommitId()

                diffFiles = gitUtil.getDiffInfo(mergeResult.oriCommitId, mergeResult.curCommitId).splitlines()
                print("diffFiles=%s" % diffFiles)
                mergeResult.isChanged = len(diffFiles) != 0
                if mergeResult.isChanged:  # 文件有变更, 提交代码评审
                    if shouldPush:
                        gitUtil.pushBranch(codeReview=shouldCodeReview, options=codeReviewOpts)
                    else:
                        print('合并完成,并且有新增变动,但无需push')
            except Exception as e:
                mergeResult.mergeSuccess = False
                print('merge fail: %s' % e)
            resultDict[targetBranch] = mergeResult

        # 钉钉通知审核人员进行合并
        robotSection = self.configParser.getSectionItems('robot')
        token = robotSection['accessToken']
        pendingReviewBranch = ''  # merge成功并有变更待评审的分支信息
        mergeFailBranch = ''  # 合并失败的分支
        sendDingDing = False  # 是否需要通知钉钉
        for branchName in resultDict.keys():
            result = resultDict[branchName]
            print('===> branch=%s,result=%s' % (branchName, result.__dict__))
            if result.mergeSuccess:
                if result.isChanged:
                    pendingReviewBranch += '\n\t%s,' % result.branch
                    sendDingDing = True
            else:
                mergeFailBranch += '\n\t%s,' % result.branch
                sendDingDing = True

        if sendDingDing:
            content = "%s\n%s" % (robotSection['keyWord'], robotSection['extraInfo'])
            content = content.strip()
            if not CommonUtil.isNoneOrBlank(pendingReviewBranch):
                content += '\n待评审分支:%s' % pendingReviewBranch[:-1]  # 删除结尾的逗号
                content += "\n评审地址:%s\n请及时处理,若已合入请忽略" % settings['codeReviewUrl']
            if not CommonUtil.isNoneOrBlank(mergeFailBranch):
                content += '\n\n合并失败的分支如下,请人工处理:%s' % mergeFailBranch
            print(content)

            if CommonUtil.isNoneOrBlank(token):
                print('accessToken为空, 无需发送通知')
            else:
                atPhoneList = robotSection['atPhone'].split(',')
                print(NetUtil.push_ding_talk_robot(content, token, False, atPhoneList))
        else:
            print('merge结束,无异常, 也无需进行代码合并')
