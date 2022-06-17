class BranchInfo(object):
    """
    分支信息汇总
    """

    def __init__(self):
        self.branchNameLocal: str = ''  # 本地分支名
        self.branchNameRemote: str = ''  # 对应的远程分支名
        self.srcBranchName: str = ''  # 源分支名称

        self.headCommitId: str = ''  # 最近一次commitId
        self.headCommitMsg: str = ''  # 最近一次commitMsg
        self.headCommitTimeStr: str = ''  # 最近一次提交时间

        self.firstCommitId: str = ''  # 第一次commitId
        self.firstCommitMsg: str = ''  # 第一次commit信息
        self.firstCommitTimeStr: str = ''  # 第一次commit时间, 格式: 2022-06-16 13:30:30
