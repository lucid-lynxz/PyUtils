import os
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util.GitUtil import GitUtil, CommitInfo, BranchInfo
from util.FileUtil import FileUtil

if __name__ == '__main__':
    remote = ''  # 远程仓库地址
    local = ''  # 本地仓库保存路径
    resultFile = './result.txt'  # 保存结果文件的路径
    gitutil = GitUtil(remote, local, 'master').updateBranch().formatLogDate()

    # 所有远程分支列表, 按commit时间降序
    rBranchList = gitutil.getBranchList('-r --sort=-committerdate')
    print("---> all remote branches: %s" % len(rBranchList))
    print(rBranchList)

    rBranchInfoList = []  # 元素是 BranchInfo 对象
    FileUtil.write2File(resultFile, 'branchName, firstDate, firstId, headDate, headId')

    limit = 65  # 最多提取前n条分支信息
    count = 0
    for branch in rBranchList:
        if count > limit:
            break
        count += 1

        # 分支名:  origin/branchA 则移除 origin/ 字符
        tip = '%s/' % gitutil.remoteRepositoryName
        branch = branch.replace('origin/HEAD ->', '').strip()
        remoteBranch = branch
        if branch.startswith(tip):
            branch = branch[len(tip):]
        headCommit: CommitInfo = gitutil.checkoutBranch(branch).updateBranch().getCommitInfo()
        print('---> 进度: %s/%s %s %s' % (count, limit, branch, headCommit.date))

        commitDate: str = headCommit.date  # 2022-06-16 10:25:06
        date = commitDate.split(' ')[0]
        dateArr = date.split('-')
        year = int(dateArr[0])
        month = int(dateArr[1])
        day = int(dateArr[2])
        dateInt = year * 365 + month * 30 + day
        if dateInt >= 2021 * 365 + 4 * 30 + 1:
            info = BranchInfo()
            info.branchNameLocal = branch
            info.branchNameRemote = remoteBranch
            info.headCommitInfo.id = headCommit.id
            info.headCommitInfo.msg = headCommit.msg
            info.headCommitInfo.date = commitDate

            # print('---> 进度:%s/%s 获取最早提交记录 %s' % (count, limit, branch))
            # firstCommitInfoTuple = gitutil.getBranchFirstCommitInfo(branch)
            # info.firstCommitId = firstCommitInfoTuple[1]
            # info.firstCommitMsg = firstCommitInfoTuple[2]
            rBranchInfoList.append(info)
            FileUtil.append2File(resultFile, '%s,%s,%s,%s,%s' % (info.branchNameLocal,
                                                                 info.firstCommitInfo.date, info.firstCommitInfo.id,
                                                                 info.headCommitInfo.date, info.headCommitInfo.id))

        while True:
            gitutil.exeGitCmd('reset --hard HEAD')
            status = gitutil.getStatus()
            nothingToCommit = 'nothing to commit' in status

            if nothingToCommit:
                break

            gitutil.deleteDotGitFile('index.lock')
            gitutil.exeGitCmd('clean -df')
            gitutil.exeGitCmd('reset --hard HEAD')

            status = gitutil.getStatus()
            nothingToCommit = 'nothing to commit' in status
            if not nothingToCommit:
                gitutil.exeGitCmd('add .')
                gitutil.exeGitCmd('commit -am $这是自动提交的信息$')
                print('--> %s %s 分支自动提交了信息' % (count, branch))
            else:
                break

    print('提交的分支列表为: %s \n%s' % (len(rBranchInfoList), rBranchInfoList))
