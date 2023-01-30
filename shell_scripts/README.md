## 注意事项

以windows为例, 各shell脚本中的使用的是 `python3.exe` 命令, 因此请将python3安装目录中的 `python.exe`
复制一份并重命名为: `python3.exe` 避免找不到命令

## 主要文件目录说明说明

通过shell脚本触发Python, 其中:

1. `sh/` 目录是脚本所在目录
2. `config/` 是脚本对应的配置文件所在目录
3. `config_dir_name.txt` 用于设置 config 文件所在目录名, 默认为: 'config', 可自行指定其他名称
   以上三个文件/目录属于同一级别
4. `jenkins_job_demo/` 提取了一份用于触发 `common_shell.sh` 脚本的jenkins job,
   具体说明见[文档](jenkins_job_demo/README.md)

另外:

* `sh/` 目录中的脚本文件名和 `config/` 中的配置文件名一一对应, 仅后缀名不同而已(一个 .sh, 一个 .ini)
* `sh/` 下的脚本执行时,会自动搜索 `config/` 中的同名配置文件

## 自定义 config 目录名

`config/` 目录下得配置文件默认是空白的, 入职各公司后, 建议复制一份 `config/` 目录, 按需更新其中的属性值
同时, 按需创建/更新 `config_dir_name.txt` 文件, 比如入职了新公司a, 则:

1. 复制一份 `config/` 目录为: `config_a/`
2. 创建 `config_a/.gitignore` 文件, 取消本目录下所有文件跟踪, 内容为: `*`
3. 修改 `config_dir_name.txt` (若无请自行创建),内容为(不包括引号):`config_a`

## `sh/` 目录下各shell脚本功能说明

1. `auto_merge_dev.sh` 分支代码合并, 支持多个同一仓库下得多个不同分支间的代码合并
2. `auto_push_dev.sh` 自动提交指定目录下的特定分支代码, 支持多个不同目录/分支的提交
3. `clear_log.sh` 清除Android手机中的特定文件, 要求adb命令已在环境变量中
4. `get_log.sh` 提取Android收集中的特定文件
5. `get_log_descrypted.sh` 提取Android收集中的特定文件,并解密,解密脚本需要自行编写,各公司不同
6. `collect_branch_info.sh` 收集指定时间段内,有提交记录的分支信息,包括分支名,创建日期,最后提交日期等信息
7. `compress_backup_logs.sh` 使用7z对指定目录下的所有子目录进行压缩
8. `compress_backup_logs_then_delete.sh` 使用7z对指定目录下的所有子目录进行压缩,压缩完成后删除源文件
9. `monitor_pc_status_server.sh` 开启服务器功能,可以监听本机连接的Android设备变化情况
10. `monitor_pc_status_client.sh` 向server端发起请求,定期轮询获取server端连接的Android设备变化情况
11. `scrcpy_multi_devices.sh` 基于 [scrcpy](https://github.com/Genymobile/scrcpy/releases) 项目, 支持显示多台Android手机的投屏
    P.S. 当前脚本仅适配了Windows端
12. `take_screenshot.sh` 通过adb命令对手机屏幕进行截图并保存到特定目录中

## 创建新的shell脚本

在 `sh/` 目录下新建脚本文件, 如: `a.sh`, 触发同目录下的 `common_shell.sh` 脚本, 内容如下:
P.S. 也可根据各公司需求, 创建 `sh/` 的同级目录, 如: `sh_a/`, 然后再在其中创建脚本文件
如下最后一行大括号中的路径是最终执行的python脚本文件在项目中的相对路径, 如: `utils_for_android_dev/clear_log.py`
使用的配置文件为: `config/a.ini` 其中父目录名通过文件 `config_dir_name.txt` 文件确定

```shell
#! /bin/bash
# a.sh

cd $(dirname $0)                       # 切换到脚本所在目录
var=${0//\\//}                         # 将路径中的斜杠替换为反斜杠
sh_abs_path=$(pwd)/${var##*/}          # 获取脚本绝对路径
sh_name=$(basename $var .sh)           # 获取shell脚本文件名(不包括 .sh 后缀)
parent_dir=$(dirname $sh_abs_path)     # 获取脚本所在目录路径
parent_dir=$(dirname $parent_dir)      # 获取shell_script目录路径

$parent_dir/sh/common_shell.sh {python文件相对路径}  $sh_name.ini $@
```