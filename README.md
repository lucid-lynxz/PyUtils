# 抽取个人日常工作中常用的脚本工具

```shell
# 使用wool脚本需要安装以下内容, -i参数是表示使用镜像源
# 其中 airtest pocoui 必装
# psutil是检测笔记本电脑电量以及是否插电,用于提醒用户,避免挂机失败
# cnocr 是因为部分页面使用pocoui/airtest无法识别,需要文字识别
pip install chardet pycryptodome airtest pocoui psutil cnocr zstd pillow pyperclip pandas pydantic schedule longport akshare openpyxl pyautogui Crypto wmi pillow pywin32 paramiko onnxruntime -i https://pypi.tuna.tsinghua.edu.cn/simple

# 若pycryptdome不可用,可卸载重装
# 导包若是: from Crypto.Cipher import AES  则改为: from Cryptodome.Cipher import AES
pip uninstall pycryptodome
pip install pycryptodomex

# 使用 pybroker 进行回测需要安装以下库
pip install lib-pybroker TA-Lib akshare matplotlib yfinance riskfolio-lib
```

## 注意事项：

**由于我在window上python2/3均有安装，默认使用python2，因此需要将 python3 安装目录下的 `python.exe` 改名为 `python3.exe`**

* 2023.02.03更新：
    * 对于windows用户，当前本项目已内置了python3.10程序，因此可无需再自行安装(内置版本不包含pip,未安装相关依赖库)
    * 对于linux/macos系统用户，可能需要自行安装python3并配置环境变量，同时需要提供命令: `python3`，经测试：
        * Ubuntu22.10/Fedora37均已内置了 python3， 无需再手动安装
        * macos 10.13 内置的是 python2，从 [官网](https://www.python.org/downloads/macos/)
          下载 [3.10.9](https://www.python.org/ftp/python/3.10.9/python-3.10.9-macos11.pkg) 版本一路next安装完成后，
          无需再手动配置环境变量即可生效

## shell脚本及配置文件的使用

父目录为: `shell_scripts/`, 其中脚本文件位于 `sh/` 子目录中, 对应的配置文件在 `config/` 子目录中,
各shell脚本用途机具体用法见[该文档](shell_scripts/README.md)
对于需要定时/定期触发的脚本, 请结合jenkins实现, 具体也是见上方见[该文档](shell_scripts/README.md)

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

## python业务脚本:

### `auto_merge_branch`

功能: 合并指定分支代码, 合并成功后按需push到远程仓库 要求: 本地代码已全部commit, 合并发生冲突时默认以源分支代码为准

### `auto_push_branch`

功能: 自动提交指定git目录下指定分支的代码 要求: 本地代码已全部commit, 若存在未commit的代码,则不进行push操作

### `auto_update_reposity`

功能: 自动更新指定目录(或其一级子目录下)下各git仓库代码 要求: 本地代码已全部commit, 若存在未commit的代码,则不进行pull操作

### `collect_branch_info`

功能：收集分支信息,包括首次提交时间, commitId,最新提交时间及commitId, commitAuthor列表等

### `custom_work_scripts/batch_compress/`

功能：使用7zip 批量压缩指定父目录下所有子目录

### `custom_work_scripts/monitor_pc_status/`

功能：监听指定pc上连接的android手机变化情况

### `uitls_for_android_dev`

功能：基于adb功能，实现：

1. `clear_log.py` 删除指定文件
2. `get_log.py` 从手机中提取多文件保存到本机中
3. `scrcpy_multi_devices.py` 基于scrcpy项目，实现多手机投屏功能(当前仅支持windows)
4. `take_screenshot.py` 通过adb screenshot进行截屏并保存文件到本机中