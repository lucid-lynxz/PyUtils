#!/bin/bash
# ##############################################################################
# 脚本名称: rollback.sh
# 功能: 恢复 setup_all.sh 运行时的备份配置
# 版本: 1.2 (兼容Ubuntu和macOS、目录配置同步)
# 用法: sudo ./rollback.sh [备份目录]
# 示例: sudo ./rollback.sh ~/setup_all/backup_20260515_112121
#       sudo ./rollback.sh  # 使用最新的备份目录
#       sudo ./rollback.sh --list  # 列出所有可用备份
# ##############################################################################

# ======================== 颜色定义 ========================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
# =========================================================

# 检查root权限
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ 错误：请使用 sudo 运行此脚本${NC}"
    echo "   示例: sudo $0"
    exit 1
fi

# 检测操作系统
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
else
    OS="Linux"
fi

# 脚本存放目录（与 setup_all.sh 保持一致）
SCRIPT_DIR="$HOME/setup_all"

# 日志文件
LOG_FILE="${SCRIPT_DIR}/rollback_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1  # 同时输出到屏幕和日志文件

# 列出所有备份
if [ "$1" = "--list" ]; then
    echo -e "${BLUE}[可用备份列表]${NC}"
    BACKUPS=$(ls -td "${SCRIPT_DIR}"/backup_* 2>/dev/null)
    if [ -z "$BACKUPS" ]; then
        echo -e "${YELLOW}⚠️  未找到任何备份目录${NC}"
    else
        echo "$BACKUPS" | while read BACKUP; do
            echo "  - $BACKUP"
        done
    fi
    exit 0
fi

# 获取备份目录
if [ -n "$1" ]; then
    BACKUP_DIR="$1"
else
    # 使用最新的备份目录
    BACKUP_DIR=$(ls -td "${SCRIPT_DIR}"/backup_* 2>/dev/null | head -1)
    if [ -z "$BACKUP_DIR" ]; then
        echo -e "${RED}❌ 错误：未找到备份目录${NC}"
        echo ""
        echo -e "${YELLOW}提示：${NC}"
        echo "  1. 运行 setup_all.sh 会生成备份目录"
        echo "  2. 备份目录位于: $SCRIPT_DIR"
        echo "  3. 使用 --list 参数查看所有可用备份:"
        echo "     sudo $0 --list"
        echo "  4. 或指定备份目录:"
        echo "     sudo $0 /path/to/backup"
        exit 1
    fi
    echo -e "${BLUE}使用最新备份目录: $BACKUP_DIR${NC}"
fi

# 检查备份目录是否存在
if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}❌ 错误：备份目录不存在: $BACKUP_DIR${NC}"
    echo ""
    echo -e "${YELLOW}提示：${NC}"
    echo "  1. 检查路径是否正确"
    echo "  2. 使用 --list 参数查看所有可用备份:"
    echo "     sudo $0 --list"
    echo "  3. 备份目录通常位于: $SCRIPT_DIR"
    exit 1
fi

echo -e "${BLUE}===================================== ${NC}"
echo -e "${BLUE}  配置回滚脚本${NC}"
echo -e "${BLUE}===================================== ${NC}"
echo -e "${YELLOW}备份目录: $BACKUP_DIR${NC}"
echo ""

# 显示备份目录内容
echo -e "${BLUE}[备份目录内容]${NC}"
ls -la "$BACKUP_DIR" 2>/dev/null || echo "    无法读取备份目录"
echo ""

# 确认回滚
echo -e "${YELLOW}⚠️  警告：此操作将恢复以下配置:${NC}"
echo "  - /etc/sysctl.conf (IP转发配置)"
if [ "$OS" = "macOS" ]; then
    echo "  - macOS 网络配置 (networksetup)"
else
    echo "  - /etc/netplan/ (网络配置)"
    echo "  - /etc/network/interfaces (网络接口配置)"
    echo "  - /etc/iptables/ (防火墙规则)"
fi
echo ""
read -p "是否继续回滚？(y/N): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo -e "${YELLOW}回滚已取消${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}[开始回滚]${NC}"

# 恢复 sysctl.conf
if [ -f "$BACKUP_DIR/sysctl.conf" ]; then
    echo "  恢复 /etc/sysctl.conf..."
    cp "$BACKUP_DIR/sysctl.conf" /etc/sysctl.conf
    sysctl -p
    echo -e "    ${GREEN}✅ 已恢复${NC}"
else
    echo -e "    ${YELLOW}⚠️  备份中无 sysctl.conf${NC}"
fi

# macOS 恢复 networkservices 配置
if [ "$OS" = "macOS" ]; then
    if [ -f "$BACKUP_DIR/networkservices.txt" ]; then
        echo "  恢复 macOS 网络配置..."
        # 尝试自动开启 WiFi
        wifi_service=$(networksetup -listallnetworkservices 2>/dev/null | grep -v "^[[:space:]]*#" | grep -iE "Wi-Fi|Airport" | head -1 || true)
        if [ -n "$wifi_service" ]; then
            echo "    开启 WiFi ($wifi_service)..."
            networksetup -setairportpower "$wifi_service" on 2>/dev/null || true
            echo -e "    ${GREEN}✅ WiFi 已开启${NC}"
        else
            echo -e "    ${YELLOW}⚠️  未找到 WiFi 服务${NC}"
        fi
        echo -e "    ${YELLOW}⚠️  其他网络配置需要手动恢复，请检查备份文件: $BACKUP_DIR/networkservices.txt${NC}"
    fi
else
    # 恢复 netplan 配置
    if [ -d "$BACKUP_DIR/netplan" ]; then
        echo "  恢复 /etc/netplan/..."
        cp -r "$BACKUP_DIR/netplan"/* /etc/netplan/
        netplan apply
        echo -e "    ${GREEN}✅ 已恢复${NC}"
    else
        echo -e "    ${YELLOW}⚠️  备份中无 netplan 配置${NC}"
    fi

    # 恢复 network/interfaces
    if [ -f "$BACKUP_DIR/interfaces" ]; then
        echo "  恢复 /etc/network/interfaces..."
        cp "$BACKUP_DIR/interfaces" /etc/network/interfaces
        systemctl restart networking 2>/dev/null || true
        echo -e "    ${GREEN}✅ 已恢复${NC}"
    else
        echo -e "    ${YELLOW}⚠️  备份中无 interfaces 配置${NC}"
    fi

    # 恢复 iptables 配置
    if [ -d "$BACKUP_DIR/iptables" ]; then
        echo "  恢复 /etc/iptables/..."
        cp -r "$BACKUP_DIR/iptables"/* /etc/iptables/
        netfilter-persistent reload 2>/dev/null || true
        echo -e "    ${GREEN}✅ 已恢复${NC}"
    else
        echo -e "    ${YELLOW}⚠️  备份中无 iptables 配置${NC}"
    fi
fi

# 恢复 dnsmasq 配置（如果备份中有）
if [ -f "$BACKUP_DIR/usb-dhcp.conf" ]; then
    echo "  恢复 /etc/dnsmasq.d/usb-dhcp.conf..."
    mkdir -p /etc/dnsmasq.d 2>/dev/null || true
    cp "$BACKUP_DIR/usb-dhcp.conf" /etc/dnsmasq.d/
    if [ "$OS" = "macOS" ]; then
        launchctl stop homebrew.mxcl.dnsmasq 2>/dev/null || true
        launchctl start homebrew.mxcl.dnsmasq 2>/dev/null || true
    else
        systemctl restart dnsmasq 2>/dev/null || true
    fi
    echo -e "    ${GREEN}✅ 已恢复${NC}"
else
    echo -e "    ${YELLOW}⚠️  备份中无 dnsmasq 配置${NC}"
fi

# 恢复手机配置（关闭 RNDIS 模式，开启 WiFi）
echo "  恢复手机配置..."
if command -v adb &>/dev/null; then
    # 获取所有设备列表（过滤掉 "List" 等无效设备名）
    # 使用更精确的匹配：只匹配第二列是 "device" 的行
    DEVICES=$(adb devices | grep -E '\tdevice$' | awk '{print $1}' | grep -v "^$" | grep -v "^List$")
    DEVICE_COUNT=$(echo "$DEVICES" | grep -c . || echo "0")
    if [ "$DEVICE_COUNT" -gt 0 ]; then
        echo "    检测到 $DEVICE_COUNT 台设备，正在恢复配置..."
        
        # 关闭 RNDIS 模式
        for DEVICE in $DEVICES; do
            # 跳过无效设备名
            if [ -z "$DEVICE" ] || [ "$DEVICE" = "List" ]; then
                continue
            fi
            
            # 获取设备型号和Android版本
            MODEL=$(adb -s "$DEVICE" shell getprop ro.product.model 2>/dev/null || echo "未知")
            ANDROID_VERSION=$(adb -s "$DEVICE" shell getprop ro.build.version.release 2>/dev/null || echo "未知")
            echo "    设备: $DEVICE (型号: $MODEL, Android: $ANDROID_VERSION)"
            
            # 尝试多种方法关闭 RNDIS
            RNDIS_DISABLED=false
            # 方法1: 使用 svc usb setFunctions none
            if adb -s "$DEVICE" shell svc usb setFunctions none 2>/dev/null; then
                RNDIS_DISABLED=true
            # 方法2: 使用 svc usb setFunctions mtp,adb (恢复为MTP+ADB模式)
            elif adb -s "$DEVICE" shell svc usb setFunctions mtp,adb 2>/dev/null; then
                RNDIS_DISABLED=true
            # 方法3: 使用 svc usb setFunctions adb (仅ADB模式)
            elif adb -s "$DEVICE" shell svc usb setFunctions adb 2>/dev/null; then
                RNDIS_DISABLED=true
            fi
            
            if [ "$RNDIS_DISABLED" = true ]; then
                echo "      ✅ RNDIS 已关闭"
            else
                echo "      ⚠️  RNDIS 关闭失败，请手动在开发者选项中关闭USB网络共享"
            fi
        done
        
        # 开启 WiFi
        for DEVICE in $DEVICES; do
            # 跳过无效设备名
            if [ -z "$DEVICE" ] || [ "$DEVICE" = "List" ]; then
                continue
            fi
            
            # 获取设备 Android 版本
            ANDROID_VERSION=$(adb -s "$DEVICE" shell getprop ro.build.version.release 2>/dev/null || echo "未知")
            
            # 方法1: 使用 svc wifi enable
            if adb -s "$DEVICE" shell svc wifi enable 2>/dev/null; then
                echo "    ✅ $DEVICE WiFi 已开启"
            # 方法2: 使用 settings put 命令
            elif adb -s "$DEVICE" shell settings put global wifi_on 1 2>/dev/null; then
                echo "    ✅ $DEVICE WiFi 已开启 (使用settings命令)"
            # 方法3: 使用 am broadcast 发送 WiFi 开启广播
            elif adb -s "$DEVICE" shell am broadcast -a android.net.wifi.STATE_CHANGE -e enabled true 2>/dev/null; then
                echo "    ✅ $DEVICE WiFi 已开启 (使用broadcast命令)"
            # 方法4: 针对 Android 10+，使用 dumpsys 命令
            elif adb -s "$DEVICE" shell dumpsys wifi setWifiEnabled true 2>/dev/null; then
                echo "    ✅ $DEVICE WiFi 已开启 (使用dumpsys命令)"
            else
                echo "    ⚠️  $DEVICE WiFi 开启失败 (Android $ANDROID_VERSION)，请手动开启"
            fi
        done
    else
        echo -e "    ${YELLOW}⚠️  未检测到 ADB 设备${NC}"
    fi
else
    echo -e "    ${YELLOW}⚠️  adb 未安装${NC}"
fi

echo ""
echo -e "${GREEN}===================================== ${NC}"
echo -e "${GREEN}  回滚完成！${NC}"
echo -e "${GREEN}===================================== ${NC}"
echo ""
echo -e "${YELLOW}日志文件: $LOG_FILE${NC}"
echo ""

# 询问是否重启
echo -e "${YELLOW}是否需要立即重启系统？${NC}"
read -p "重启后配置将完全生效 (y/N): " REBOOT_CONFIRM
if [ "$REBOOT_CONFIRM" = "y" ] || [ "$REBOOT_CONFIRM" = "Y" ]; then
    echo -e "${BLUE}系统将在 10 秒后重启...${NC}"
    sleep 10
    reboot
else
    echo -e "${YELLOW}如需重启，请手动执行: sudo reboot${NC}"
fi
echo ""
