#!/bin/bash

# 通用模板脚本
# 其他脚本可调用本脚本, 并依此传入两个参数后自动触发
# 参数1: 待调用的python脚本相对于项目根目录的路径, 如: a/b/c.py
# 参数2: 配置文件名称, 如: a.ini
#
# 举例, 假设 common_shell.sh 同级目录下有其他脚本 a.py, 内容如下(不包括前面的'#'号):

# cd $(dirname $0)                       # 切换到脚本所在目录
# var=${0//\\//}                         # 将路径中的斜杠替换为反斜杠
# sh_abs_path=$(pwd)/${var##*/}          # 获取脚本绝对路径
# parent_dir=$(dirname $sh_abs_path)     # 获取脚本所在目录路径
#
# $parent_dir/common_shell.sh   a/b/c.py    a.ini
# $SHELL

# 执行上述脚本后,会自动执行 {项目跟目录}/a/b/c.py

# 第一个参数需要传入待执行的脚本相对路径
if [ -z $1 ]; then
  echo please set python scipt relative path
  sleep 5
  exit 1
fi

# 第二个参数需要传入python脚本使用的配置文件名
if [ -z $2 ]; then
  echo please set config file name
  sleep 5
  exit 2
fi

cd $(dirname $0)                       # 切换到脚本所在目录
var=${0//\\//}                         # 将路径中的斜杠替换为反斜杠
sh_abs_path=$(pwd)/${var##*/}          # 获取脚本绝对路径
file_name=$(basename $sh_abs_path .sh) # 获取脚本文件名(不包含后缀 .sh)
parent_dir=$(dirname $sh_abs_path)     # 获取脚本所在目录路径
parent_dir=$(dirname $parent_dir)      # 获取脚本和配置文件目录的共同父目录

# 读取配置文件所在目录名
config_dir_name_path="$parent_dir/config_dir_name.txt"
echo config_dir_name_path is: $config_dir_name_path
config_dir_name="config" # 默认为: config
if [ -f "$config_dir_name_path" ]; then
  echo config_dir_name.txt exist
  config_dir_name=$(tail -n -1 "$config_dir_name_path")
fi
echo config_dir_name is:$config_dir_name

#config_name=$file_name.ini # 拼接获取脚本对应的配置文件名: {脚本文件名}.ini
config_name=$2 # 拼接获取脚本对应的配置文件名: {脚本文件名}.ini
config_abs_path="$parent_dir/$config_dir_name/$config_name"

# 切换到项目根目录
cd ../..
root_dir_path=$(pwd)
echo $root_dir_path

# 拼接获得python脚本绝对路径
python_script_path="$root_dir_path/$1"

echo sh_abs_path is:$sh_abs_path
echo config_abs_path is:$config_abs_path
echo python_script_path is:$python_script_path
echo all shell params:$@

# 确认系统是否有可用的 python 或  python3命令
# 检测命令对应的python命令是否是python3
# 输入的参数1为： “python” 或者 “python3”
# 会自动拼接为：python --version 2>&1 并对结果做检测
# 方法执行后，通过 $hitPython3 获取结果， 1表示当前命令可用且表示python3
function testPython3(){
    hitPython3=0
    cmd="$1 --version 2>&1 >/dev/null"
    result=$($cmd)
    if [[ "$result" =~ "command not found" ]]; then
        hitPython3=0
    else
        if [[ "$result" == *"Python 3"* ]]; then
            hitPython3=1
        fi
    fi
}

# 依次检测系统 'python3' 和 ‘python’ 命令是否可用
finalPythonCmd=""
pythonCmd="python"
python3Cmd="python3"
python3CmdInner="" # 本项目内置的python3命令(仅有windows版)
if [ "$OSTYPE" = "msys" ]; then
  echo windows
  pythonCmd="python.exe"
  python3Cmd="python3.exe"
  python3CmdInner="$root_dir_path/third_tools/python3/windows/python3.exe"
fi

testPython3 $python3Cmd # 检测 'python3' 命令
if [[ $hitPython3 == "1" ]]; then
    finalPythonCmd=$python3Cmd
else
  testPython3 $pythonCmd # 检测 'python' 命令
  if [[ $hitPython3 == "1" ]]; then
    finalPythonCmd=$pythonCmd
  fi
fi

# 若系统不支持python3，则尝试使用内置的命令
if [ -z "$finalPythonCmd" ]; then
  finalPythonCmd=$python3CmdInner
fi

# 未找到python3命令，报错并退出
if [ -z "$finalPythonCmd" ]; then
    echo "当前未找到python3命令,取消执行,请确保已安装并配置了系统环境变量"
    exit 1
fi
echo "final python3 command:$finalPythonCmd"

# 获取其他参数(剔除有特定含义的参数1和2)并透传到python脚本中
otherParams=${@/$1/}
otherParams=${otherParams/$2/}

cmdContent=""
if [ -f "$config_abs_path" ]; then
  cmdContent="$python_script_path --config $config_abs_path $otherParams"
else
  echo custom config file is not exist, use defaul settingss
  cmdContent="$python_script_path $otherParams"
fi

# 执行命令
echo "$finalPythonCmd $cmdContent"
which $finalPythonCmd
#$finalPythonCmd --version

$finalPythonCmd $cmdContent

#$SHELL
secs=10
echo will exit after $secs secs
sleep $secs
exit
