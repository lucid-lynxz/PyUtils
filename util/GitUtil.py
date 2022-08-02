# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil
from util.TimeUtil import TimeUtil


class CommitInfo(object):
    """
    git某次提交的信息
    """

    def __init__(self, commitId: str = ''):
        # commit id
        self.id: str = commitId
        # 提交内容
        self.msg: str = ''

        # 完整的提交信息
        self.totalInfo: str = ''
        # 提交人员姓名
        self.author: str = ''
        # 提交人员邮箱
        self.authorEmail: str = ''
        # 提交日期, 格式: 2022-06-16 13:30:30
        self.date: str = ''
        # merge信息
        self.merge: str = ''


class BranchInfo(object):
    """
    分支信息汇总
    """

    def __init__(self):
        self.branchNameLocal: str = ''  # 本地分支名
        self.branchNameRemote: str = ''  # 对应的远程分支名
        self.srcBranchName: str = ''  # 源分支名称

        # 最近一次commitId
        self.headCommitInfo: CommitInfo = CommitInfo()

        # {srcBranchName} 存在时可获取分支首次提交记录
        # 假设已知是从 branchA checkout 出了 branchB, 当前分支为: branchB, 则获取本分支的特有提交记录如下, 找到最早的一次提交即可:
        # git log branchA..branchB
        # 分支第一次commitId
        self.firstCommitInfo: CommitInfo = CommitInfo()

        # 参与代码提价的author名称列表
        self.authorList: list = []


class GitUtil(object):
    """
    git操作封装
    切换分支: checkoutBranch(...)
    更新分支: updateBranch(...)
    合并分支: mergeBranch(...)
    获取当前分支名: getCurBranch()
    获取分支最新提交id: getHeadCommitId(...)
    获取当前分支diff信息: getDiffInfo(...)
    """

    def __init__(self, remotePath: str, localPath: str, branch: str = None, depth: int = 0, cloneOptions: str = None):
        """
        :param remotePath: 远程仓库地址,若为空,则尝试从 localPath 目录中提取 (git remote -v)
        :param localPath: 本地仓库目录地址, 要求非空
        :param branch: 目标分支名(本地分支与远程分支名保持一致,默认使用当前分支,若不存在再使用 'master')
        :param depth: git clone/fetch 深度,默认为0 表示不限制
        :param cloneOptions: 额外的clone参数, 如: --shallow-since="2021.4.1"
        """
        self._localRepositoryPath = localPath
        self._dotGitPath = None  # 代码仓库下 .git/ 目录路径
        self._gitDirWorkTreeInfo = None
        self._updateGitDirWorkTreeInfo()

        # 若未指定分支名, 则优先使用当前分支, 若不存在,则使用 'master'
        self.branch = branch
        self.branch = self.getCurBranch() if CommonUtil.isNoneOrBlank(self.branch) else self.branch
        self.branch = 'master' if CommonUtil.isNoneOrBlank(self.branch) else self.branch

        # 远程仓库名,默认为 origin
        gitCmd = 'git %s remote show' % self._gitDirWorkTreeInfo
        cmdResult = CommonUtil.exeCmd(gitCmd)
        self._remoteRepositoryName = 'origin' if CommonUtil.isNoneOrBlank(cmdResult) else cmdResult.splitlines()[0]

        # 若未给出远程仓库地址, 则尝试从本地获取, 命令如下:
        # git remote -v
        # origin  https://github.com/lucid-lynxz/PyUtils.git (fetch)
        # origin  https://github.com/lucid-lynxz/PyUtils.git (push)
        self.remoteRepositoryUrl = remotePath
        if CommonUtil.isNoneOrBlank(self.remoteRepositoryUrl):
            gitCmd = 'git %s remote -v' % self._gitDirWorkTreeInfo
            cmdResult = CommonUtil.exeCmd(gitCmd)
            if not CommonUtil.isNoneOrBlank(cmdResult):
                self.remoteRepositoryUrl = cmdResult.split('(fetch)')[0].replace(self.remoteRepositoryName, "").strip()

        self._depth = depth  # git clone/fetch 深度,默认为30

        # clone仓库,并checkout到指定分支
        self.checkoutBranch(self.branch, False, cloneOptions)

    @property
    def remoteRepositoryName(self):
        """
        远程仓库名称, 通常是 origin
        """
        return self._remoteRepositoryName

    @property
    def localRepositoryPath(self) -> str:
        """
        获取本地仓库目录路径
        """
        return self._localRepositoryPath

    @localRepositoryPath.setter
    def localRepositoryPath(self, value: str):
        """
        设置本地仓库路径
        """
        self._localRepositoryPath = value
        self._updateGitDirWorkTreeInfo()

    def _updateGitDirWorkTreeInfo(self):
        """
        更新git工作目录路径,避免通过 cd xxx 来切换目录
        每次更改 localRepositoryPath 后都需要重新设置
        :return: self
        """
        # 代码仓库下 .git/ 目录路径
        self._dotGitPath = "%s/.git/" % self.localRepositoryPath
        self._dotGitPath = self._dotGitPath.replace("\\", "/").replace("//", "/")
        self._gitDirWorkTreeInfo = "--git-dir=%s --work-tree=%s" % (self._dotGitPath, self.localRepositoryPath)
        return self

    def setDepth(self, depth: int):
        """
        设置git操作深度,避免clone及fetch太多历史快照
        :param depth: >=1 有效, 其他值表示不限制
        :return: self
        """
        self._depth = depth
        return self

    def _getDepthOption(self) -> str:
        return '--depth=%s' % self._depth if self._depth >= 1 else ''

    def getCommitId(self, branch: str = '', remote: bool = False, opts: str = '') -> str:
        """
        获取指定分支的commitId, 使用命令:  git rev-parse [origin/]{branch} [opts]
        :param branch: 分支名, 如: master,若放空,则默认使用当前分支名
        :param remote: 是否是远程分支
        :param opts: 其他参数
        return: commitId
        """
        if CommonUtil.isNoneOrBlank(branch):
            branch = self.getCurBranch() if remote else 'HEAD'

        remoteRepoOpt = '%s/' % self.remoteRepositoryName if remote else ''
        gitCmd = 'git %s rev-parse %s%s %s' % (self._gitDirWorkTreeInfo, remoteRepoOpt, branch, opts)
        return CommonUtil.exeCmd(gitCmd).strip()

    def getCommitInfo(self, commitId: str = 'HEAD') -> CommitInfo:
        """
        获取仓库中某次commit的信息
        :param commitId: 获取指定的commitId提交信息, 若为空,则返回最新的提交记录
        :return: CommitBean
        """
        commitIdOpt = '' if CommonUtil.isNoneOrBlank(commitId) else commitId
        gitCmd = "git %s log %s -1" % (self._gitDirWorkTreeInfo, commitIdOpt)
        cmdResult = CommonUtil.exeCmd(gitCmd)

        commitInfo = CommitInfo(commitId)
        commitInfo.totalInfo = cmdResult

        if CommonUtil.isNoneOrBlank(cmdResult):
            return commitInfo

        infoLinesArr = cmdResult.split("\n")
        commitMsg = []
        for line in infoLinesArr:
            lineTrim = line.strip()
            if CommonUtil.isNoneOrBlank(lineTrim):
                continue

            if line.startswith('Author:'):
                commitInfo.author = line[len('Author:'):].strip()
            elif line.startswith('Date:'):
                commitInfo.date = line[len('Date:'):].strip()
            elif line.startswith('Merge:'):
                commitInfo.merge = line[len('Merge:'):].strip()
            elif line.startswith('commit '):
                commitInfo.id = line[len('commit '):].strip()
            else:
                commitMsg.append(lineTrim)
        commitInfo.msg = "\n".join(commitMsg)
        return commitInfo

    def getBranch(self, options: str = '') -> str:
        """
        通过 git branch [options] 命令获取分支信息
        :return: 字符串
        """
        return CommonUtil.exeCmd('git %s branch %s' % (self._gitDirWorkTreeInfo, options))

    def getBranchList(self, options: str = '') -> list:
        """
        通过 git branch [options] 命令获取分支信息
        :param options: 额外的参数,如: -r --sort=-committerdate 表示按提交顺序列出远程分支
        :return: 分支名列表, 若是远程分支, 则分支名会带有 origin/ 前缀, 自行剔除
        """
        print('--> getBranchList options=%s' % options)

        def removeStar(name: str) -> str:
            """
            当前分支名前方会带有星号, 此处进行移除, 并进行前后空白删除
            :param name:
            :return:
            """
            if CommonUtil.isNoneOrBlank(name):
                return name
            name = name.strip()
            if name[0] == '*':
                name = name[1:]
            if ' ' in name:  # 过滤掉: origin/HEAD -> origin/master
                name = ''
            return name.strip()

        def isValidBranch(branchName: str) -> bool:
            return not CommonUtil.isNoneOrBlank(branchName)

        return list(filter(isValidBranch, list(map(removeStar, self.getBranch(options).splitlines()))))

    def getCurBranch(self) -> str:
        """
        获取当前分支名, 要求本地已有仓库存在
        也可以使用命令: git rev-parse --abbrev-ref HEAD
        踩坑:
        1. 使用rebase合并发生冲突后, 分支处于rebasing, 导致 git branch 得到的结果为:  * (no branch, rebasing login_branch_demo)
        2. 使用merge合并发生冲突后, 通过 git branch 得到的分支名是正常的, 此时若触发 git status,则得到如下:
            On branch xxx
            You have unmerged paths.
            (fix conflicts and run "git commit")
            (use "git merge --abort" to abort the merge)
        :return: 分支名str
        """
        branchInfo = self.getBranch()
        branchList = list(map(lambda name: name.strip(), branchInfo.splitlines()))
        for bName in branchList:  # 当前分支不一定是首个分支名
            if bName[0] == '*':
                bName = bName[1:].strip()
                if 'no branch' in bName:
                    return ''
                return bName
        return ''

    def getRemoteBranchName(self, targetBranch: str = '') -> str:
        """
        查看指定分支对应的远程分支,若不存在,则返回 ''
        使用命令: git branch -vv , 得到如下列表, 提取星号开头的行,带方括号表示有远程分支
          local_branchX 20812344c [origin/remote_branchX]
        * local_branchA 20812345c [origin/remote_branchA: ahead xx]
          local_branchB 20812346c [origin/remote_branchB: ahead xx]
          local_branchC 20812347c XXXXX
        返回 'remote_branchA'
        偶尔会出现, 远程分支前方多了个 'remotes/' :
        * local_branchA  f6bca93c1 [remotes/origin/remote_branchA]
          local_branchB 20812346c [origin/remote_branchB: ahead xx]

        另外, 远程分支可能命名为: origin/branchC, 则通过 git branch -vv 得到的可能就是如下结果:
        origin/local_branchC    285e076cb [origin/origin/local_branchC]

        :param targetBranch: 本地目标分支名, 若传空, 则表示当前分支
        """
        if not CommonUtil.isNoneOrBlank(targetBranch):
            self.checkoutBranch(targetBranch)

        curBranch = self.getCurBranch()
        gitCmd = 'git %s branch -vv' % self._gitDirWorkTreeInfo
        cmdResult = CommonUtil.exeCmd(gitCmd)
        # print('cmdResult=%s' % cmdResult)
        lines = cmdResult.split('\n')
        for line in lines:
            if '* %s' % curBranch in line:
                remotePrefix = '[remotes/%s/' % self._remoteRepositoryName
                if remotePrefix in line:
                    line = line.replace(remotePrefix, '[%s/' % self._remoteRepositoryName)

                if '[%s/' % self._remoteRepositoryName in line:
                    return line.split('[')[1] \
                        .split(']')[0] \
                        .split(':')[0] \
                        .replace('%s/' % self.remoteRepositoryName, '', 1)  # 只替换第一个 origin/ 即可
                break
        return ''

    def checkoutBranch(self, targetBranch: str = None, forceClone: bool = False, cloneOptions: str = None):
        """
        按需进行仓库clone, 分支切换, 仅本地分支不存在,首次创建时才会拉取最新代码
        :param targetBranch 要切换的分支名,默认为 self.branch
        :param forceClone 是否要强制clone, true-若本地目录存在,删除后重新clone
        :param cloneOptions clone时使用的其他信息
        :return: self
        """
        # 强制重新clone
        if forceClone:
            FileUtil.deleteFile(self.localRepositoryPath)

        if CommonUtil.isNoneOrBlank(targetBranch):
            targetBranch = self.branch

        print('--> checkoutBranch targetBranch=%s' % targetBranch)
        # 若对应git仓库目录已存在,则直接进行分支切换,代码pull
        if FileUtil.isDirFile("%s" % self._dotGitPath):
            # 查看本地现有分支,按需切换拉取远程指定分支代码
            gitCmd = "git %s branch" % self._gitDirWorkTreeInfo
            cmdResult = CommonUtil.exeCmd(gitCmd)

            if targetBranch not in cmdResult:  # 本地分支不包含目标分支,则进行创建, 此处不会切换分支
                gitCmd = "git %s fetch %s %s:%s" % (
                    self._gitDirWorkTreeInfo, self._remoteRepositoryName, targetBranch, targetBranch)
                CommonUtil.exeCmd(gitCmd)

            if self.getCurBranch() != targetBranch:  # 当前分支不是目标分支,需切换
                gitCmd = "git %s checkout %s" % (self._gitDirWorkTreeInfo, targetBranch)
                cmdResult = CommonUtil.exeCmd(gitCmd)
                print('--> checkout targetBranch=%scurBranchName=%s,cmdResult=%s' % (
                    targetBranch, self.getCurBranch(), cmdResult))

            if self.getCurBranch() != targetBranch:
                raise Exception('checkoutBranch失败cur=%s,target=%s' % (self.getCurBranch(), targetBranch))

            # 查看当前分支对应的远程分支,若不存在,则进行指定\
            if CommonUtil.isNoneOrBlank(self.getRemoteBranchName()):
                print('当前分支的远程分支为空,进行设置')
                gitCmd = 'git %s branch --set-upstream-to=%s/%s' % (
                    self._gitDirWorkTreeInfo, self._remoteRepositoryName, targetBranch)
                CommonUtil.exeCmd(gitCmd)

            # gitCmd = 'git %s branch -vv' % self._gitDirWorkTreeInfo
            # cmdResult = CommonUtil.exeCmd(gitCmd)
            # # print('cmdResult=%s' % cmdResult)
            # lines = cmdResult.split('\n')
            # for line in lines:
            #     if '* %s' % targetBranch in line:
            #         if '[%s/%s' % (self._remoteRepositoryName, targetBranch) not in line:
            #             gitCmd = 'git %s branch --set-upstream-to=%s/%s' % (
            #                 self._gitDirWorkTreeInfo, self._remoteRepositoryName, targetBranch)
            #             CommonUtil.exeCmd(gitCmd)
            #         break

            # if "* %s" % targetBranch in cmdResult:  # 当前分支就是目标分支,无需切换
            #     gitCmd = ""
            # elif targetBranch in cmdResult:  # 当前已有相应的branch,需要切换
            #     gitCmd = "git %s checkout %s" % (self._gitDirWorkTreeInfo, targetBranch)
            # else:  # 当前并无目标分支,需要创建新分支,并拉取远程代码
            #     gitCmd = 'git %s fetch --depth=%s origin %s:%s' % (
            #         self._gitDirWorkTreeInfo, self._depth, targetBranch, targetBranch)
            #     CommonUtil.exeCmd(gitCmd)  # 建立远程分支和本地分支的联系,执行过后本地已有对应分支
            #
            #     # 切换到对应分支
            #     gitCmd = "git %s checkout -b %s origin/%s" % (self._gitDirWorkTreeInfo, targetBranch, targetBranch)
            #     # gitCmd = "git %s checkout -b %s origin/%s" % (self._gitDirWorkTreeInfo, targetBranch, targetBranch)
            #
            # # 分支切换
            # if not CommonUtil.isNoneOrBlank(gitCmd):
            #     print("执行git分支切换")
            #     CommonUtil.exeCmd(gitCmd)
            #     # gitCmd = "git %s branch --set-upstream-to=origin:%s" % (self._gitDirWorkTreeInfo, targetBranch)
            #     # print("执行git set-upstream-to:%s" % gitCmd)
            #     # CommonUtil.exeCmd(gitCmd)
            #
            # # 拉取分支代码
            # gitCmd = 'git %s fetch origin %s' % (self._gitDirWorkTreeInfo, targetBranch)
            # cmdResult = CommonUtil.exeCmd(gitCmd)
            #
            # gitCmd = 'git %s rebase origin/%s' % (self._gitDirWorkTreeInfo, targetBranch)
            # cmdResult = CommonUtil.exeCmd(gitCmd)
            # print("执行git rebase更新分支代码结束: %s" % cmdResult)
        else:  # clone 仓库指定分支代码,目前首次clone耗时较长,4min+
            _cloneOptions = '' if CommonUtil.isNoneOrBlank(cloneOptions) else cloneOptions
            gitCmd = "git clone -b %s %s %s %s %s --recurse-submodules" % (
                targetBranch, self._getDepthOption(), self.remoteRepositoryUrl, self.localRepositoryPath, _cloneOptions)
            print("%s 准备clone源码,请耐心等候" % TimeUtil.getTimeStr())
            CommonUtil.exeCmd(gitCmd)
            print("%s git clone完成" % TimeUtil.getTimeStr())
            gitCmd = 'git %s config remote.%s.fetch +refs/heads/*:refs/remotes/%s/*' % (
                self._gitDirWorkTreeInfo, self._remoteRepositoryName, self._remoteRepositoryName)
            CommonUtil.exeCmd(gitCmd)
            # print('首次clone, 准备 fetch origin, 耗时可能较长, 请耐心等待....')
            # CommonUtil.exeCmd('git %s fetch origin' % self._gitDirWorkTreeInfo)
            # print('fetch origin结束')
        print('%s checkoutBranch finish, curBranch=%s, targetBranch=%s' % (TimeUtil.getTimeStr(), self.getCurBranch(),
                                                                           targetBranch))
        return self

    def fetch(self, options: str = ''):
        """
        执行 fetch origin [options]
        """
        gitCmd = 'git %s fetch %s %s' % (
            self._gitDirWorkTreeInfo, self._remoteRepositoryName, options)
        CommonUtil.exeCmd(gitCmd)
        return self

    def updateBranch(self, branch: str = None, byRebase: bool = False, fetchOptions: str = None):
        """
        更新分支代码, 要求对应的远程分支存在
        :param branch: 分支名, 默认使用当前分支, 要求对应的远程分支存在
        :param byRebase: True-使用 pull --rebase 更新本地分支  False-仅使用pull更新本地分支
        :param fetchOptions: fetch时额外增加的属性, 比如: --shallow-since={date} , --unshallow 等
        :return: self
        """
        if CommonUtil.isNoneOrBlank(branch):  # 目标分支名不存在, 使用当前分支名
            branch = self.getCurBranch()
        else:
            self.checkoutBranch(branch)  # 指定了目标分支,则进行切换到

        if CommonUtil.isNoneOrBlank(branch):
            print('updateBranch error as target branch name is empty')
            return self

        print('--> updateBranch branch=%s,byRebase=%s' % (branch, byRebase))
        # 拉取分支代码
        _fetchOptions = '' if CommonUtil.isNoneOrBlank(fetchOptions) else fetchOptions
        gitCmd = 'git %s fetch %s %s %s' % (
            self._gitDirWorkTreeInfo, self._remoteRepositoryName, branch, _fetchOptions)
        CommonUtil.exeCmd(gitCmd)

        gitCmd = 'git %s %s %s %s' % (
            self._gitDirWorkTreeInfo, 'pull --rebase' if byRebase else 'pull', self._remoteRepositoryName, branch)
        CommonUtil.exeCmd(gitCmd)
        return self

    def pushBranch(self, localBranch: str = None, remoteBranch: str = None,
                   codeReview: bool = False, options: str = '') -> str:
        """
        推送代码到远程仓库的指定分支
        :param localBranch: 本地分支名,若为空,则使用当前分支,否则会先切换到目标分支
        :param remoteBranch: 远程目标分支
        :param codeReview: 是否需要触发代码评审, True-git push origin HEAD:refs/for/{remoteBranch}
        :param options: 额外的参数信息,如: -o reviewer=lynxz
        return: push命令执行结果, 成功则:  Everything up-to-date 或者:
            Counting objects: 4, done.
            Delta compression using up to 8 threads.
            Compressing objects: 100% (4/4), done.
            Writing objects: 100% (4/4), 877 bytes | 877.00 KiB/s, done.
            Total 4 (delta 3), reused 0 (delta 0)
            remote: Resolving deltas: 100% (3/3), completed with 3 local objects.
            To https://github.com/lucid-lynxz/PyUtils.git
             * [new branch]      HEAD -> refs/for/master
        """
        if not CommonUtil.isNoneOrBlank(localBranch):
            self.checkoutBranch(localBranch)
        localBranch = self.getCurBranch()

        if CommonUtil.isNoneOrBlank(remoteBranch):
            remoteBranch = localBranch

        remoteBranchInfo = 'refs/for/%s' % remoteBranch if codeReview else remoteBranch
        gitCmd = 'git %s push %s HEAD:%s %s' % (
            self._gitDirWorkTreeInfo, self._remoteRepositoryName, remoteBranchInfo, options)
        return CommonUtil.exeCmd(gitCmd)

    def updateAllSubmodule(self, subModuleBranch: str = 'master'):
        """
        更新所有子模块
        :param subModuleBranch: 子模块对应的远程分支名
        :return: self
        """
        gitCmd = "git %s submodule foreach 'git pull %s %s'" % (
            self._gitDirWorkTreeInfo, self._remoteRepositoryName, subModuleBranch)
        CommonUtil.exeCmd(gitCmd)
        return self

    def getStatus(self) -> str:
        """
        获取当前分支的 git status 状态
        :return: str
        """
        gitCmd = 'git %s status' % self._gitDirWorkTreeInfo
        return CommonUtil.exeCmd(gitCmd)

    def reset(self, mode: str = 'hard', commitId: str = 'HEAD') -> str:
        """
        还原代码到指定commitId, 默认为 --hard 模式
        :param mode: 模式,默认为: hard
        :param commitId: 回退的代码点, 默认为: HEAD
        return: str, reset命令执行结果
        """
        modeOpt = '--%s' % mode
        if CommonUtil.isNoneOrBlank(mode):
            modeOpt = ''
        gitCmd = 'git %s reset %s %s' % (self._gitDirWorkTreeInfo, modeOpt, commitId)
        return CommonUtil.exeCmd(gitCmd)

    def mergeBranch(self, fromBranch: str,
                    targetBranch: str = None,
                    byRebase: bool = False,
                    strategyOption: str = ''):
        """
        将源分支代码合入目标分支中，默认使用 merge 命令进行合并
        若合并失败,则默认进行回退: git reset --hard HEAD, 并抛出 Exception
        :param fromBranch: 源分支名
        :param targetBranch: 目标分支名, 默认使用当前分支
        :param byRebase: True-使用 rebase 命令进行合入, False-使用 merge 命令进行合入
        :param strategyOption: 合并发生冲突时的处理方式,默认空
                theirs->以fromBranch分支代码为准
                ours->以targetBranch分支代码为准
        :return:  self
        """
        if CommonUtil.isNoneOrBlank(targetBranch):
            targetBranch = self.getCurBranch()
        else:
            self.checkoutBranch(targetBranch)
        headIdBefore = self.getCommitId()  # 合并前的commitId

        print('-->%s mergeBranch fromBranch=%s,targetBranch=%s,byRebase=%s' % (
            TimeUtil.getTimeStr(), fromBranch, targetBranch, byRebase))

        if CommonUtil.isNoneOrBlank(targetBranch):
            raise Exception('targetBranch 参数无效,mergeBranch失败')

        strategyCmdOpt = '--strategy-option=%s' % strategyOption
        if CommonUtil.isNoneOrBlank(strategyOption):
            strategyCmdOpt = ''

        mergeCmd = 'rebase' if byRebase else 'merge'
        gitCmd = 'git %s %s %s %s' % (self._gitDirWorkTreeInfo, mergeCmd, strategyCmdOpt, fromBranch)
        mergeResult = CommonUtil.exeCmd(gitCmd)

        # 合并失败的提示语关键字, 任意一个命中就表示合并失败
        failKW = ['Merge conflict', 'merge failed']
        for kw in failKW:
            if kw in mergeResult:  # 合并失败
                print('merge into %s fail, will abort and reset... %s' % (targetBranch, mergeResult))
                CommonUtil.exeCmd('git %s %s --abort' % (self._gitDirWorkTreeInfo, mergeCmd))  # 终止合并
                self.reset('hard', 'HEAD')  # 还原代码到合并前
                raise Exception('mergeBranch into %s 失败,存在未处理的冲突,请人工处理' % targetBranch)

        tempCurBranchName = self.getCurBranch()
        maxWaitSec = 60  # 最长等待时间,单位: s
        waitSec = 0  # 已等待时长,单位:s
        deltaSec = 5  # 每次等待时长,单位:s
        while tempCurBranchName != targetBranch:
            TimeUtil.sleep(deltaSec)
            tempCurBranchName = self.getCurBranch()
            waitSec += deltaSec
            print('---> %s tempCurBranchName=%s 与预期分支名%s不符, 继续等待' % (
                TimeUtil.getTimeStr(), tempCurBranchName, targetBranch))

            if waitSec >= maxWaitSec:
                print('---> 退出等待循环')
                break

        # 记录下当前git状态(若处于rebasing中,如有冲突了,则会有报错)
        statusMsg = self.getStatus()
        print('merge into %s, cur statusMsg=%s' % (targetBranch, statusMsg))

        headIdAfter = self.getCommitId()  # 合并后的commitId
        # 确认是否合并完成
        if tempCurBranchName != targetBranch:
            raise Exception('mergeBranch失败,分支名与预期%s不符,请确认是否尚未合并完成 %s' % (tempCurBranchName, targetBranch))
        else:
            print('%s mergeBranch(%s)结束 headIdBefore=%s,headIdAfter=%s' % (
                TimeUtil.getTimeStr(), targetBranch, headIdBefore, headIdAfter))
        return self

    def getDiffInfo(self, oldCommitId: str, newCommitId: str = None, options: str = '--name-only') -> str:
        """
        比较两次commit之间的文件变更信息, 默认仅获取变更文件名
        :param oldCommitId: 旧commitId
        :param newCommitId: 新commitId,若为None,则使用当前分支的最新commitId
        :param options: git diff 额外参数, 默认为: --name-only
        :return: 文件变更列表字符串,若无变更,则返回 '', 可通过 result.splitlines() 转换为列表
        """
        if CommonUtil.isNoneOrBlank(newCommitId):
            newCommitId = self.getCommitId()

        print('--> getDiffInfo oldCommitId=%s,newCommitId=%s,options=%s' % (oldCommitId, newCommitId, options))
        gitCmd = "git %s diff %s %s %s" % (
            self._gitDirWorkTreeInfo, oldCommitId, newCommitId, options)
        cmdResult = CommonUtil.exeCmd(gitCmd)
        return cmdResult

    def exeGitCmd(self, cmd: str, printCmdInfo: bool = True) -> str:
        """
        执行其他git方法
        :param cmd: 命令内容, 无需输入 'git'
        """
        if cmd.startswith('git'):
            cmd = cmd[3:]
        gitCmd = "git %s %s" % (
            self._gitDirWorkTreeInfo, cmd)
        cmdResult = CommonUtil.exeCmd(gitCmd, printCmdInfo)
        return cmdResult

    def config(self, key: str, value: str, option: str = ''):
        """
        在当前仓库中执行config命令, 比如调整时间戳: key=log.date  value=format:'%Y-%m-%d %H:%M:%S'
        """
        # gitCmd = "git %s config log.date format:'%Y-%m-%d %H:%M:%S'"
        gitCmd = "git %s config %s %s %s" % (self._gitDirWorkTreeInfo, key, value, option)
        cmdResult = CommonUtil.exeCmd(gitCmd)
        return cmdResult

    def formatLogDate(self, dateFormat: str = '%Y-%m-%d %H:%M:%S'):
        """
        格式化 git log 日期格式
        :param dateFormat: 日期格式:
            %y 两位数的年份表示（00-99）
            %Y 四位数的年份表示（000-9999）
            %m 月份（01-12）
            %d 月内中的一天（0-31）
            %H 24小时制小时数（0-23）
            %I 12小时制小时数（01-12）
            %M 分钟数（00=59）
            %S 秒（00-59）
        :return self
        """
        self.config('log.date', 'format:%s' % dateFormat, '--replace-all')
        return self

    def deleteDotGitFile(self, relPath: str):
        """
        删除 .git/ 目录下的某个文件
        :param relPath: 文件相对路径, 如: "index.lock" 表示要删除: '.git/index.lock' 文件
        """
        absPath = '%s%s' % (self._dotGitPath, relPath)
        return CommonUtil.exeCmd('rm -rf %s' % absPath)

    def getFirstCommitId(self, srcBranch: str, targetBranch: str = None) -> str:
        """
        获取指定分支的第一次提交信息
        假设当前是branchB ,且是从branchA checkout出的 branchB
        则通过本方法得到首次提交的commitId, 实际是执行:  git log branchA..branchB --oneline
        :param srcBranch: {targetBranch} 对应的源分支名
        :param targetBranch: 目标分支名, 即上面的提到的 'branchB'
        :return  commitId 或者空 ''
        """
        if CommonUtil.isNoneOrBlank(srcBranch):
            return ''

        if CommonUtil.isNoneOrBlank(targetBranch):
            targetBranch = self.getCurBranch()
        else:
            self.checkoutBranch(targetBranch)

        # 确保本地已有 srcBranch 分支信息
        self.checkoutBranch(srcBranch).updateBranch().checkoutBranch(targetBranch)

        # 获取最早一次提交
        cmdResult = self.exeGitCmd('log %s..%s --oneline' % (srcBranch, targetBranch))
        if cmdResult.startswith('fatal'):
            print('getFirstCommitId fail ascmdResult=%s' % cmdResult)
            return ''
        lines = cmdResult.splitlines()
        n = len(lines)
        if n <= 0:
            return ''
        commitId = lines[n - 1].split(' ')[0]
        print('getFirstCommitId(src=%s,target=%s)=%s' % (srcBranch, targetBranch, commitId))
        return commitId

    def getFirstCommitInfoByReflog(self) -> CommitInfo:
        """
        根据 reflog 命令获取分支首次提交信息
        命令: git reflog show --date=iso master
        输出:
        46d5029 (HEAD -> master, origin/master) master@{2022-06-27 21:49:04 +0800}: reset: moving to 46d5029f52abf0f09923dba6b38059ea638bb326
        66c0a6a master@{2022-06-27 21:47:37 +0800}: rebase -i (finish): refs/heads/master onto 284e96a3df6049b047e7211f40de8a36e816237c
        e042715 master@{2022-06-27 21:40:47 +0800}: rebase (continue) (finish): refs/heads/master onto 284e96a3df6049b047e7211f40de8a36e816237c
        74649e7 master@{2022-06-27 21:33:02 +0800}: commit (amend): test3
        172f81d master@{2022-06-27 21:32:41 +0800}: commit (amend): test3
        883c1c0 master@{2022-06-27 21:32:33 +0800}: commit (amend): test3
        b826bac master@{2022-06-27 21:32:02 +0800}: commit (amend): test3
        3240275 master@{2019-10-24 22:14:16 +0800}: commit (merge): 添加手机识别信息
        ad89575 master@{2019-10-19 11:14:27 +0800}: commit (amend): 更新gradle,修改初始化参数
        63e2fc5 master@{2019-10-17 22:23:56 +0800}: commit: 更新包名
        71a62c9 master@{2019-10-17 22:15:16 +0800}: commit (initial): init
        ee4e912 master@{2022-06-15 20:45:31 +0800}: branch: Created from HEAD

        命令: git reflog show --date=iso master2222
        输出: fatal: ambiguous argument 'master2222': unknown revision or path not in the working tree.
        Use '--' to separate paths from revisions, like this:
        'git <command> [<revision>...] -- [<file>...]
        """
        commitInfo = CommitInfo()
        curBarnchName = self.getCurBranch()
        cmdResult = self.exeGitCmd('reflog show --date=iso %s' % curBarnchName)
        if cmdResult.startswith('fatal'):
            print('getFirstCommitInfoByReflog fail as cmdResult=%s' % cmdResult)
            commitInfo.totalInfo = cmdResult
            return commitInfo

        lines = cmdResult.splitlines()
        cnt = len(lines)
        firstIdShort = ''
        for index in range(start=cnt - 1, stop=0, step=-1):
            line = lines[index]
            arr = line.split(' ')
            action = ' '.join(arr[1:]).split('}:')[1].split(':')[0]
            if 'commit' in action:
                firstIdShort = arr[0]
                break
        return self.getCommitInfo(firstIdShort)

    def getAllAuthorName(self, allBranch: bool = False, since: str = '', until: str = '') -> list:
        """
        获取所有author姓名
        命令: git log --all --format='%aN' --since=xxxx  --unity=xxxx | sort -u
        windows cmd中 sort -u 报错, 此处自行去重
        :param allBranch: 是否提取所有分支的commit作者, 默认False,只提取当前分支
        :param since: 起始日期(不包括), 格式与当前仓库的 git config log.date相符,可先触发 formatLogDate() 方法进行指定
        :param until: 截止日期(包括)
        :return: 作者名列表
        """
        # 由于windows下执行后中文有乱码存在, 未解决, 此处将结果重定向到文件中
        curDirPath = os.path.abspath(os.path.dirname(__file__))
        tempResultFile = '%s/tempAllAuthorName.txt' % curDirPath
        FileUtil.deleteFile(tempResultFile)

        allBranchOpt = '--all' if allBranch else ''
        sinceOpt = '' if CommonUtil.isNoneOrBlank(since) else '--since %s' % since
        untilOpt = '' if CommonUtil.isNoneOrBlank(until) else '--until %s' % until
        gitCmd = "log --format=%s %s %s %s > %s" % ('%aN', allBranchOpt, sinceOpt, untilOpt, tempResultFile)
        self.exeGitCmd(gitCmd, False)
        allAutoNameLines = FileUtil.readFile(tempResultFile)
        FileUtil.deleteFile(tempResultFile)  # 删除无用的临时文件
        nameDict: dict = {}
        resultList: list = []
        if len(allAutoNameLines) > 0:
            for line in allAutoNameLines:
                line = line.strip().replace('\'', '')
                nameDict[line] = ''
            for key in nameDict:
                resultList.append(key)
        return resultList
