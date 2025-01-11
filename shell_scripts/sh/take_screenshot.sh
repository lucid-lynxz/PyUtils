#! /bin/bash

cd $(dirname $0)                   # 切换到脚本所在目录
var=${0//\\//}                     # 将路径中的斜杠替换为反斜杠
sh_abs_path=$(pwd)/${var##*/}      # 获取脚本绝对路径
sh_name=$(basename $var .sh)       # 获取shell脚本文件名(不包括 .sh 后缀)
parent_dir=$(dirname $sh_abs_path) # 获取脚本所在目录路径
parent_dir=$(dirname $parent_dir)  # 获取shell_script目录路径

$parent_dir/sh/common_shell.sh utils_for_android_dev/take_screenshot.py $sh_name.ini $@
#$SHELL
