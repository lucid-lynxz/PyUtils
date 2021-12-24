# !/usr/bin/env python3
# -*- coding:utf-8 -*-
from util import FileUtil
from util.CommonUtil import CommonUtil
from util.TimeUtil import TimeUtil


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

    def __init__(self, remotePath: str, localPath: str, branch: str = None):
        """
        :param remotePath: 远程仓库地址,若为空,则尝试从 localPath 目录中提取 (git remote -v)
        :param localPath: 本地仓库目录地址, 要求非空
        :param branch: 目标分支名(本地分支与远程分支名保持一致,默认使用当前分支,若不存在再使用 'master')
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

        self._depth = 30  # git clone/fetch 深度,默认为30

        # clone仓库,并checkout到指定分支
        self.checkoutBranch(self.branch, False)

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
        :param depth: >=1 有效
        :return: self
        """
        if depth >= 1:
            self._depth = depth
        return self

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

    def getHeadCommitInfo(self) -> dict:
        """
        获取仓库中最新一次commit的信息
        :return: 字典dict, 包含commit的信息:
                    key-value 如下:
                        totalInfo  对应 git log -1 得到的完整日志信息
                        commitId   当前commitId
                        message    commit提交信息
                        Author     当前commit创建者
                        Date       commit时间
        """
        print('--> getHeadCommitInfo')
        gitCmd = "git %s log -1" % self._gitDirWorkTreeInfo
        cmdResult = CommonUtil.exeCmd(gitCmd)
        print("获取仓库中最新一次commit的信息: %s" % cmdResult)

        infoMap = {'totalInfo': cmdResult}
        if CommonUtil.isNoneOrBlank(cmdResult):
            return infoMap

        infoLinesArr = cmdResult.split("\n")
        commitMsg = []

        for line in infoLinesArr:
            lineTrim = line.strip()
            if CommonUtil.isNoneOrBlank(lineTrim):
                continue

            if line.startswith('Author:'):
                infoMap['Author'] = line[len('Author:'):].strip()
            elif line.startswith('Date:'):
                infoMap['Date'] = line[len('Date:'):].strip()
            elif line.startswith('Merge:'):
                infoMap['Merge'] = line[len('Merge:'):].strip()
            elif line.startswith('commit '):
                infoMap['commitId'] = line[len('commit '):].strip()
            else:
                commitMsg.append(lineTrim)

        infoMap['message'] = "\n".join(commitMsg)
        return infoMap

    def getBranch(self, options: str = '') -> str:
        """
        通过 git branch [options] 命令获取分支信息
        :return: 字符串
        """
        return CommonUtil.exeCmd('git %s branch %s' % (self._gitDirWorkTreeInfo, options))

    def getBranchList(self, options: str = '') -> list:
        """
        通过 git branch [options] 命令获取分支信息
        :return: 分支名列表
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
            return name.strip()

        return list(map(removeStar, self.getBranch(options).splitlines()))

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

    def getRemoteBranchName(self) -> str:
        """
        查看当前分支对应的远程分支,若不存在,则返回 ''
        使用命令: git branch -vv , 得到如下列表, 提取星号开头的行,带方括号表示有远程分支
          local_branchX 20812344d [origin/remote_branchX]
        * local_branchA 20812345d [origin/remote_branchA: ahead xx]
          local_branchB 20812346d [origin/remote_branchB: ahead xx]
          local_branchC 20812347d XXXXX
        """
        curBranch = self.getCurBranch()

        gitCmd = 'git %s branch -vv' % self._gitDirWorkTreeInfo
        cmdResult = CommonUtil.exeCmd(gitCmd)
        # print('cmdResult=%s' % cmdResult)
        lines = cmdResult.split('\n')
        for line in lines:
            if '* %s' % curBranch in line:
                if '[%s/' % self._remoteRepositoryName in line:
                    return line.split('[')[1].split(']')[0].split(':')[0].replace('%s/' % self.remoteRepositoryName, '')
                break
        return ''

    def checkoutBranch(self, targetBranch: str = None, forceClone: bool = False):
        """
        按需进行仓库clone, 分支切换, 仅本地分支不存在,首次创建时才会拉取最新代码
        :param targetBranch 要切换的分支名,默认为 self.branch
        :param forceClone 是否要强制clone, true-若本地目录存在,删除后重新clone
        :return: self
        """
        # 强制重新clone
        if forceClone:
            FileUtil.deleteFile(self.localRepositoryPath)

        if CommonUtil.isNoneOrBlank(targetBranch):
            targetBranch = self.branch

        print('--> checkoutBranch targetBranch=%s' % targetBranch)
        # 若对应git仓库目录已存在,则直接进行分支切换,代码pull
        if FileUtil.isDirFileExist("%s" % self._dotGitPath):
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
                raise Exception('checkoutBranch失败')

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
            gitCmd = "git clone -b %s --depth=%s %s %s  --recurse-submodules" % (
                targetBranch, self._depth, self.remoteRepositoryUrl, self.localRepositoryPath)
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

    def updateBranch(self, branch: str = None, byRebase: bool = False):
        """
        更新分支代码, 要求对应的远程分支存在
        :param branch: 分支名, 默认使用当前分支, 要求对应的远程分支存在
        :param byRebase: True-使用rebase更新本地分支 False-使用pull更新本地分支
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
        gitCmd = 'git %s fetch %s %s' % (self._gitDirWorkTreeInfo, self._remoteRepositoryName, branch)
        CommonUtil.exeCmd(gitCmd)

        gitCmd = 'git %s %s %s %s' % (
            self._gitDirWorkTreeInfo, 'rebase' if byRebase else 'pull', self._remoteRepositoryName, branch)
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
