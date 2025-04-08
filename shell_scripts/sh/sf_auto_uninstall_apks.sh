#!/bin/bash
# 功能: 在指定的设备上卸载指定包名的app
# 设备号通过变量 devices 设置, 若列表为空,则会获取本机说连接的所有设备
# 包名通过变量 pkgs 设置, 支持多个, 空格分隔, 要求非空

# 待卸载的app包名, 此处是shizuku的包名示例
pkgs=( "moe.shizuku.privileged.api" )

# 设备序列号列表，用空格分隔, 若未指定, 则会自动获取所有已连接的设备序列号
#devices=("序列号1"  "序列号2"  "序列号3"  )
devices=()
if [ ${#devices[@]} -eq 0 ]; then
    echo "未指定设备列表, 使用所有在线设备"
    devices=($(adb devices | awk '{print $1}' | tail -n +2))
fi

echo -e "\n待处理的设备列表为:"
for dev in "${devices[@]}"; do
    echo " $dev"
done

echo -e "\n待卸载的包名:"
for pkg in "${pkgs[@]}"; do
    echo " $pkg"
done

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
    for pkg in ${pkgs[@]}; do
        if adb shell pm list packages | grep -q "^package:$pkg\$"; then
            :
        else
            echo "包不存在:$pkg, 状态码: $?"
            continue
        fi
        echo "正在卸载: $pkg"
        adb -s "$device" uninstall "$pkg"
        
        if [ $? -ne 0 ]; then
            echo "卸载失败"
        fi
    done
    
    # 等待一会
    sleep 3
done