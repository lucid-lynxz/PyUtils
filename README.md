## 抽取个人日常工作中常用的脚本工具

1. 将本项目放置于: `D:\workSpace\python\` 目录下
2. 修改 `D:\workSpace\python\PyUtils\custom_config_test\*.ini` 配置文件
3. 执行 `D:\workSpace\python\PyUtils\custom_config_test\bat\*.bat` 脚本

各脚本的含义见下方说明

## 基础工具:

```shell script
## util/CommonUtil.py
# 执行shell命令,并得到结果str
def exeCmd(cls, cmd: str) -> str

# 字符串判空,返回bool值
def isNoneOrBlank(cls, info: str) -> bool


## util/ConfigUtil.py  config.ini 文件读取工具类
util = NewConfigParser().initPath(init_path) # 传入 config.ini 配置文件路径
secMap = util.getSectionItems('sectionName') # 获取指定section名称的参数dict

# util/FileUtil.py  文件读写工具类
# 读取文件行信息,返回列表
def readFile(path: str, encoding='utf-8') -> list

# 写入/追加内容到指定文件中, 若文件不存在, 自动创建
def write2File(path: str, msg: str) -> bool
def append2File(path: str, msg: str) -> bool

# 创建文件/目录(目录要求以斜杠或反斜杠结尾)
def createFile(path: str, recreateIfExist: bool = False)

# 删除文件
def deleteFile(path: str) 

# 文件/目录是否存在
def isFileExist(path: str)->bool
def isDirFileExist(path: str) -> bool


## util/GitUtil.py  git操作工具类,包括: clone/pull/merge/reset/获取commitId 等内容
```

## 业务脚本:

### `auto_merge_branch`

功能: 合并指定分支代码, 合并成功后按需push到远程仓库 要求: 本地代码已全部commit, 合并发生冲突时默认以源分支代码为准

### `auto_push_branch`

功能: 自动提交指定git目录下指定分支的代码 要求: 本地代码已全部commit, 若存在未commit的代码,则不进行push操作

### 1. `auto_update_reposity`

功能: 自动更新指定目录(或其一级子目录下)下各git仓库代码 要求: 本地代码已全部commit, 若存在未commit的代码,则不进行pull操作
 