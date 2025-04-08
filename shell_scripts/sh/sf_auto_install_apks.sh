#!/bin/bash
# 功能: 在指定的设备上安装指定目录下的apk
# 设备号通过变量 devices 设置, 若列表为空,则会获取本机说连接的所有设备
# apk目录通过变量 apk_dir 设置, 若为空, 则会使用当前文件所在目录

# 设备序列号列表，用空格分隔, 若未指定, 则会自动获取所有已连接的设备序列号
#devices=("序列号1"  "序列号2"  "序列号3"  )
devices=()
if [ ${#devices[@]} -eq 0 ]; then
    echo "未指定设备列表, 使用所有在线设备"
    devices=($(adb devices | awk '{print $1}' | tail -n +2))
fi
echo -e "\n待处理的设备列表为:\n${devices[@]}"

# APK 目录路径, 该目录下所有的apk都会被安装, 若未指定路径,则会使用当前脚本所在目录
# apk_dir="~/apk/" 
apk_dir=""

# 若 apk_dir 为空，则使用脚本所在目录
if [ -z "$apk_dir" ]; then
    apk_dir=$(dirname "$(realpath "$0")")
fi

# 需要执行的 ADB 命令列表
# 主要是启动并运行shizuku
commands=(
    "shell monkey -p moe.shizuku.privileged.api -c android.intent.category.LAUNCHER 1"
    "tcpip 5555"
)

commands2=(
    "shell sh /storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh"
)

# 获取目录下所有的 APK 文件
apks=$(find "$apk_dir" -name "*.apk") # 返回字符串
IFS=$'\n' read -r -d '' -a apks <<< "$apks" # 将结果分割成数组
echo -e "\n待安装的apk列表为:"
for apk in "${apks[@]}"; do
    echo " $apk"
done

# 检查是否有 APK 文件
# if [ -z "$apks" ]; then
#     echo "没有找到任何 APK 文件！"
#     exit 1
# fi

# 使用 adb devices 获取设备列表，并检查设备是否在其中
online_devices=$(adb devices | grep -v 'List' | awk '{print $1}') # 返回一个字符串
IFS=$'\n' read -r -d '' -a online_devices <<< "$online_devices" # 将结果分割成数组
echo -e "\n在线设备:"
for dev in "${online_devices[@]}"; do
    echo " $dev"
done

# 遍历每个设备
for device in "${devices[@]}"; do
    # 检查设备是否在在线设备列表中
    if [[ ! " ${online_devices[*]} " =~ " ${device} " ]]; then
        echo "$device 不在线，跳过此次循环"
        continue
    fi
    echo -e "\n正在处理设备: $device"
    
    # 在当前设备上遍历每个APK进行安装
    for apk in "${apks[@]}"; do
        if [ -n "$apk" ]; then
            echo -e "\n正在安装: $apk"
            
            # 使用adb命令安装APK到指定设备
            adb -s "$device" install -r -g "$apk"
            
            if [ $? -ne 0 ]; then
                echo "失败安装"
            fi
        fi
    done
    
    # 执行额外的 ADB shell 指令
    echo "执行额外的 ADB shell 指令..."
    for cmd in "${commands[@]}"; do
        echo "执行命令: adb -s $device $cmd"
        adb -s "$device" $cmd
    done
    
    # 等待一会
    sleep 3

    # 执行额外的 ADB shell 指令
    for cmd in "${commands2[@]}"; do
        echo "执行命令2: adb -s $device $cmd"
        adb -s "$device" $cmd
    done
done