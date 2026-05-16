#!/bin/bash
# ##############################################################################
# 脚本名称: setup_all.sh
# 功能总览:
# 1. 配置主机静态IP、网关、DNS（Ubuntu使用Netplan，macOS使用networksetup）
# 2. 开启系统IP转发，让主机具备路由器功能
# 3. 配置NAT流量转发，实现USB设备通过主机网络上网（反向共享）
# 4. 为USB网络接口配置IP地址，启动DHCP服务为手机分配IP
# 5. 批量ADB操作：配置手机路由和DNS、强制关闭WiFi
# 6. 兼容 Android 8 ~ 16 各版本
# 7. 所有配置永久生效，服务器重启后不丢失
# 适用环境: Ubuntu 20.04+ 或 macOS 10.15+ 系统 + USB集线器 + 安卓设备
# 版本: 1.5 (兼容Ubuntu和macOS)
# 版本: 2.0 (兼容有线和无线网络)
# 版本: 3.0 (修复USB反向共享逻辑，兼容Android 8-16)
# macOS 手动操作（仅安装 dnsmasq，其他配置由脚本自动完成）:
#   brew install dnsmasq  # 安装 dnsmasq
#   launchctl load /opt/homebrew/opt/dnsmasq/homebrew.mxcl.dnsmasq.plist  # 启动 dnsmasq 服务
# 用法: sudo ./setup_all.sh [IP] [ETH] [GATEWAY] [DNS]
# 示例: sudo ./setup_all.sh 192.168.1.100 eth0 192.168.1.1 8.8.8.8
#       sudo ./setup_all.sh --interactive  # 交互式配置
#       sudo ./setup_all.sh --dry-run      # 仅测试，不实际修改配置
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
    echo -e "${RED}[ERROR] 请使用 sudo 运行此脚本${NC}"
    echo "   示例: sudo $0"
    exit 1
fi

set -e  # 开启严格模式：任意命令执行失败，脚本直接退出

# ======================== 系统检测 ========================
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
    OS_VERSION=$(sw_vers -productVersion)
else
    OS="Linux"
    OS_VERSION=$(lsb_release -rs 2>/dev/null || cat /etc/os-release | grep VERSION_ID | cut -d'"' -f2)
fi
echo -e "${BLUE}[系统信息]${NC}"
echo "  操作系统: $OS $OS_VERSION"
echo ""

# 检查dry-run模式
DRY_RUN=false
if [ "$1" = "--dry-run" ]; then
    DRY_RUN=true
    echo -e "${YELLOW}[Dry-Run 模式]${NC}"
    echo "  此模式下仅测试配置，不会实际修改系统"
    shift
fi

# 检查wifi模式
WIFI_MODE=false
if [ "$1" = "--wifi" ]; then
    WIFI_MODE=true
    echo -e "${YELLOW}[WiFi 模式]${NC}"
    echo "  将使用无线接口作为网络出口"
    shift
fi
# =========================================================

# ======================== 目录配置 ========================
SCRIPT_DIR="$HOME/setup_all"
BACKUP_DIR="${SCRIPT_DIR}/backup_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${SCRIPT_DIR}/setup_all_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$SCRIPT_DIR" 2>/dev/null || true
# 修复目录权限（如果目录所有者是 root，则改为当前用户）
if [ -d "$SCRIPT_DIR" ] && [ "$(ls -ldn "$SCRIPT_DIR" 2>/dev/null | awk '{print $3}')" = "0" ]; then
    chown -R "$USER" "$SCRIPT_DIR" 2>/dev/null || true
fi
exec > >(tee >(sed 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE")) 2>&1
# =========================================================

# ======================== 系统配置文件路径 ========================
if [ "$OS" = "macOS" ]; then
    SYSCTL_CONF="/etc/sysctl.conf"
    NETPLAN_DIR=""
    NETPLAN_CONF=""
    NETWORK_INTERFACES=""
    IPTABLES_DIR=""
else
    SYSCTL_CONF="/etc/sysctl.conf"
    NETPLAN_DIR="/etc/netplan"
    NETPLAN_CONF="${NETPLAN_DIR}/01-static-ip.yaml"
    NETWORK_INTERFACES="/etc/network/interfaces"
    IPTABLES_DIR="/etc/iptables"
fi
# ================================================================

# ======================== 网络核心变量 ========================
DEFAULT_IP="30.85.204.150"
DEFAULT_ETH="en0"
DEFAULT_GATEWAY="30.85.204.1"
DEFAULT_DNS="30.30.30.30"

INTERACTIVE=false
if [ "$1" = "--interactive" ]; then
    INTERACTIVE=true
    shift
fi

IP="${1:-$DEFAULT_IP}"
ETH="${2:-$DEFAULT_ETH}"
GATEWAY="${3:-$DEFAULT_GATEWAY}"
DNS="${4:-$DEFAULT_DNS}"
# ================================================================

echo -e "${BLUE}===================================== ${NC}"
echo -e "${BLUE}  一键配置：Ubuntu/macOS 静态IP + USB共享上网${NC}"
echo -e "${BLUE}===================================== ${NC}"

# 交互式配置菜单
if [ "$INTERACTIVE" = true ]; then
    echo -e "${YELLOW}[交互式配置]${NC}"
    echo "  当前配置值（按回车使用默认值，或输入新值）:"
    read -p "  IP [$IP]: " NEW_IP
    [ -n "$NEW_IP" ] && IP="$NEW_IP"
    read -p "  网卡 [$ETH]: " NEW_ETH
    [ -n "$NEW_ETH" ] && ETH="$NEW_ETH"
    read -p "  网关 [$GATEWAY]: " NEW_GATEWAY
    [ -n "$NEW_GATEWAY" ] && GATEWAY="$NEW_GATEWAY"
    read -p "  DNS [$DNS]: " NEW_DNS
    [ -n "$NEW_DNS" ] && DNS="$NEW_DNS"
    echo ""
fi

# 显示最终配置值
echo -e "${YELLOW}[最终配置]${NC}"
echo "  IP: $IP"
echo "  网卡: $ETH"
echo "  网关: $GATEWAY"
echo "  DNS: $DNS"
echo "  网络模式: $(if $WIFI_MODE; then echo "WiFi"; else echo "有线"; fi)"
echo ""

# 判断是否是无线接口
is_wireless() {
    if [ "$OS" = "macOS" ]; then
        local wifi_iface=$(networksetup -listallhardwareports 2>/dev/null | grep -B1 "Device: $1" | grep -q "Hardware Port: Wi-Fi" && echo "yes" || true)
        [ "$wifi_iface" = "yes" ] && return 0 || return 1
    else
        if command -v iw &>/dev/null; then
            iw dev "$1" info &>/dev/null && return 0 || return 1
        else
            echo "$1" | grep -qE '^wlan|^wlp' && return 0 || return 1
        fi
    fi
}

# 检查系统版本兼容性
echo -e "${BLUE}[步骤0] 检查系统版本...${NC}"
if [ "$OS" = "macOS" ]; then
    echo -e "${GREEN}检测到macOS版本: $OS_VERSION${NC}"
else
    UBUNTU_VERSION=$(lsb_release -rs 2>/dev/null || cat /etc/issue | grep -oP '\d+\.\d+' | head -1)
    if [ -z "$UBUNTU_VERSION" ]; then
        echo -e "${YELLOW}警告：无法检测Ubuntu版本，请确认系统为Ubuntu 18.04+${NC}"
    else
        echo -e "${GREEN}检测到Ubuntu版本: $UBUNTU_VERSION${NC}"
        if [ "$(echo "$UBUNTU_VERSION < 18.04" | bc)" -eq 1 ]; then
            echo -e "${RED}错误：需要Ubuntu 18.04或更高版本${NC}"
            exit 1
        fi
    fi
fi

# 自动安装依赖
echo -e "${BLUE}[步骤0.1] 检查并安装依赖...${NC}"
if [ "$OS" = "macOS" ]; then
    if ! command -v brew &>/dev/null; then
        echo -e "${YELLOW}警告：未检测到 Homebrew，建议安装${NC}"
    else
        if ! command -v dnsmasq &>/dev/null; then
            echo -e "    ${YELLOW}未检测到 dnsmasq，请手动安装: brew install dnsmasq${NC}"
        else
            echo -e "    ${GREEN}dnsmasq 已安装${NC}"
        fi
        if ! command -v adb &>/dev/null; then
            echo -e "    ${YELLOW}未检测到 adb，请手动安装: brew install --cask android-platform-tools${NC}"
        else
            echo -e "    ${GREEN}adb 已安装${NC}"
        fi
    fi
else
    if ! command -v netplan &>/dev/null; then
        apt update && apt install netplan -y
    fi
    if ! command -v bc &>/dev/null; then
        apt install bc -y
    fi
fi
echo -e "${GREEN}依赖检查完成${NC}"
echo ""

# -------------------------- 步骤1：创建脚本存放目录和备份目录 --------------------------
echo "[步骤1] 创建脚本存放目录和备份目录..."
mkdir -p "$SCRIPT_DIR"
mkdir -p "$BACKUP_DIR"
echo "备份目录: $BACKUP_DIR"

echo "[步骤1.1] 备份原始配置文件..."
[ -f "$NETWORK_INTERFACES" ] && cp "$NETWORK_INTERFACES" "$BACKUP_DIR/" && echo "已备份 $NETWORK_INTERFACES"
[ -f "$SYSCTL_CONF" ] && cp "$SYSCTL_CONF" "$BACKUP_DIR/" && echo "已备份 $SYSCTL_CONF"
[ -d "$IPTABLES_DIR" ] && cp -r "$IPTABLES_DIR" "$BACKUP_DIR/" && echo "已备份 $IPTABLES_DIR"

# -------------------------- 步骤2：检测USB网络接口 --------------------------
echo -e "${BLUE}[步骤2] 检测USB网络接口...${NC}"
if [ "$OS" = "macOS" ]; then
    USB_INTERFACES=$(ifconfig -l | tr ' ' '\n' | grep -E '^en[0-9]+' || true)
    echo "    当前网络接口列表:"
    ifconfig -l | tr ' ' '\n' | while read IFACE; do echo "    - $IFACE"; done
else
    USB_INTERFACES=$(ip link show | grep 'usb' | awk '{print $2}' | sed 's/@.*//; s/:$//' || true)
    echo "    当前网络接口列表:"
    ip link show | awk '/^[0-9]+:/ {print "    " $2}' | sed 's/://g' || echo "    无法获取网络接口列表"
fi

if [ -z "$USB_INTERFACES" ]; then
    echo -e "${YELLOW}警告：未检测到USB网络接口，请检查USB集线器和设备连接${NC}"
else
    echo -e "${GREEN}检测到USB网络接口: $USB_INTERFACES${NC}"
    USB_COUNT=$(echo "$USB_INTERFACES" | wc -w)
    echo "    共检测到 $USB_COUNT 个USB网络接口"
fi

# -------------------------- 步骤3：检查网卡并配置静态IP --------------------------
echo -e "${BLUE}[步骤3] 检查网卡并配置静态IP...${NC}"

if [ "$OS" = "macOS" ]; then
    if ! networksetup -listallhardwareports | grep -q "$ETH"; then
        echo -e "${RED}错误：网卡 $ETH 不存在${NC}"
        exit 1
    fi
else
    if ! ip link show "$ETH" &>/dev/null; then
        echo -e "${RED}错误：网卡 $ETH 不存在${NC}"
        ip link show | awk '/^[0-9]+:/ {print "    " $2}' | sed 's/://g'
        exit 1
    fi
fi
echo -e "${GREEN}网卡 $ETH 存在${NC}"

if [ "$OS" = "macOS" ]; then
    networksetup -listallnetworkservices > "$BACKUP_DIR/networkservices.txt" 2>/dev/null || true
else
    [ -d "$NETPLAN_DIR" ] && cp -r "$NETPLAN_DIR" "$BACKUP_DIR/"
fi

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[Dry-Run] 跳过实际配置${NC}"
else
    if [ "$OS" = "macOS" ]; then
        echo "  配置网络..."
        service_name=$(networksetup -listallhardwareports 2>/dev/null | grep -B1 "Device: $ETH" | grep "Hardware Port:" | sed 's/Hardware Port: //' || true)
        if [ -z "$service_name" ]; then
            echo -e "    ${RED}错误：无法找到网卡 $ETH 对应的网络服务名称${NC}"
            exit 1
        fi
        echo "    网络服务名称: $service_name"

        if ! is_wireless "$ETH"; then
            wifi_service=$(networksetup -listallnetworkservices 2>/dev/null | grep -v "^[[:space:]]*#" | grep -iE "Wi-Fi|Airport" | head -1 || true)
            if [ -n "$wifi_service" ]; then
                networksetup -setairportpower "$wifi_service" off 2>/dev/null || true
                echo "    已关闭 WiFi ($wifi_service) 避免冲突"
            fi
        fi

        if is_wireless "$ETH"; then
            echo "    WiFi 模式，使用 DHCP..."
            networksetup -setdhcp "$service_name"
        else
            echo "    有线模式，配置静态 IP..."
            networksetup -setmanual "$service_name" "$IP" "255.255.255.0" "$GATEWAY"
            networksetup -setsearchdomains "$service_name" "$DNS"
        fi
        echo -e "    ${GREEN}macOS网络配置完成${NC}"
    else
        if is_wireless "$ETH"; then
            echo "  检测到无线网卡，使用 DHCP..."
            cat > "$NETPLAN_CONF" << EOF
network:
  version: 2
  wifis:
    ${ETH}:
      dhcp4: yes
EOF
        else
            cat > "$NETPLAN_CONF" << EOF
network:
  version: 2
  ethernets:
    ${ETH}:
      dhcp4: no
      addresses:
        - ${IP}/24
      routes:
        - to: default
          via: ${GATEWAY}
      nameservers:
        addresses:
          - ${DNS}
EOF
        fi

        echo "  应用Netplan配置..."
        if ! netplan try; then
            echo -e "${RED}Netplan配置校验失败${NC}"
            exit 1
        fi
        echo -e "${GREEN}Netplan配置校验通过${NC}"
        if netplan apply; then
            echo -e "${GREEN}Netplan配置应用成功${NC}"
        else
            echo -e "${RED}Netplan配置应用失败${NC}"
            exit 1
        fi
    fi

    echo "  验证IP配置..."
    if [ "$OS" = "macOS" ]; then
        CURRENT_IP=$(ifconfig "$ETH" | grep "inet " | awk '{print $2}' | cut -d'/' -f1)
    else
        CURRENT_IP=$(ip addr show dev ${ETH} | grep "inet " | awk '{print $2}' | cut -d'/' -f1)
    fi
    if [ "$CURRENT_IP" = "$IP" ]; then
        echo -e "${GREEN}IP配置验证成功: $CURRENT_IP${NC}"
    else
        echo -e "${RED}IP配置验证失败: 当前=$CURRENT_IP, 期望=$IP${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}静态IP配置完成${NC}"


# -------------------------- 步骤4：开启系统IP转发 --------------------------
echo -e "${BLUE}[步骤4] 开启系统IP转发...${NC}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[Dry-Run] 跳过实际配置${NC}"
else
    if [ "$OS" = "macOS" ]; then
        sysctl -w net.inet.ip.forwarding=1
        echo "net.inet.ip.forwarding=1" >> /etc/sysctl.conf
    else
        if grep -q "^net.ipv4.ip_forward=1" "$SYSCTL_CONF"; then
            echo -e "    ${GREEN}IP转发配置已存在${NC}"
        elif grep -q "^#net.ipv4.ip_forward=1" "$SYSCTL_CONF"; then
            sed -i 's/^#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' "$SYSCTL_CONF"
            echo -e "    ${GREEN}已启用IP转发配置${NC}"
        else
            echo "net.ipv4.ip_forward=1" >> "$SYSCTL_CONF"
            echo -e "    ${GREEN}已添加IP转发配置${NC}"
        fi
        sysctl -p
    fi
fi
echo -e "${GREEN}IP转发已开启${NC}"


# -------------------------- 步骤5：配置NAT流量转发和DHCP服务器 --------------------------
echo -e "${BLUE}[步骤5] 配置NAT流量转发和DHCP服务器...${NC}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[Dry-Run] 跳过实际配置${NC}"
else
    if [ "$OS" = "macOS" ]; then
        echo "  配置NAT规则..."
        mkdir -p /etc/pf.anchors 2>/dev/null || true
        cat > /etc/pf.anchors/nat << EOF
# NAT规则：USB网卡流量伪装成有线网卡IP
nat on $ETH from (en+) to any -> ($ETH)
EOF
        pfctl -e 2>/dev/null || true
        pfctl -f /etc/pf.conf 2>/dev/null || true
        echo -e "    ${GREEN}macOS NAT规则已配置${NC}"
    else
        apt update
        apt install iptables-persistent dnsmasq -y

        # 配置NAT规则
        iptables -t nat -F
        iptables -t nat -A POSTROUTING -o $ETH -j MASQUERADE
        iptables -A FORWARD -j ACCEPT
        netfilter-persistent save
        echo -e "    ${GREEN}NAT流量转发配置完成${NC}"
    fi

    # 为每个USB网络接口配置IP地址
    echo "  配置USB网络接口IP地址..."
    USB_SUBNET_BASE="192.168.42"
    USB_IFACE_INDEX=1
    USB_IFACE_LIST=""

    if [ -z "$USB_INTERFACES" ]; then
        echo -e "    ${YELLOW}未检测到USB网络接口，跳过USB接口IP配置${NC}"
        echo -e "    ${YELLOW}请确保手机已通过USB连接并开启了网络共享${NC}"
    else
        for USB_IFACE in $USB_INTERFACES; do
            USB_GW_IP="${USB_SUBNET_BASE}.${USB_IFACE_INDEX}"
            USB_DHCP_START="${USB_SUBNET_BASE}.$((USB_IFACE_INDEX * 10 + 100))"
            USB_DHCP_END="${USB_SUBNET_BASE}.$((USB_IFACE_INDEX * 10 + 200))"

            echo "    配置接口 $USB_IFACE -> $USB_GW_IP/24"

            if [ "$OS" = "macOS" ]; then
                ifconfig "$USB_IFACE" "$USB_GW_IP" netmask 255.255.255.0 up 2>/dev/null || true
            else
                ip addr flush dev "$USB_IFACE" 2>/dev/null || true
                ip addr add "${USB_GW_IP}/24" dev "$USB_IFACE" 2>/dev/null || true
                ip link set "$USB_IFACE" up 2>/dev/null || true
            fi

            USB_IFACE_LIST="${USB_IFACE_LIST}${USB_IFACE}:${USB_GW_IP}:${USB_DHCP_START}:${USB_DHCP_END} "
            USB_IFACE_INDEX=$((USB_IFACE_INDEX + 1))
        done

        # 持久化USB接口IP配置
        if [ "$OS" != "macOS" ]; then
            mkdir -p /etc/NetworkManager/dispatcher.d 2>/dev/null || true
            cat > /etc/NetworkManager/dispatcher.d/50-usb-network.sh << 'DISPATCHER_EOF'
#!/bin/bash
# 自动为USB网络接口配置IP地址
if echo "$1" | grep -qE '^usb[0-9]+$'; then
    case "$2" in
        up)
            IFACE_NUM=$(echo "$1" | grep -oE '[0-9]+$')
            GW_IP="192.168.42.$((IFACE_NUM + 1))"
            ip addr flush dev "$1" 2>/dev/null || true
            ip addr add "${GW_IP}/24" dev "$1" 2>/dev/null || true
            ip link set "$1" up 2>/dev/null || true
            ;;
    esac
fi
DISPATCHER_EOF
            chmod +x /etc/NetworkManager/dispatcher.d/50-usb-network.sh 2>/dev/null || true
            echo -e "    ${GREEN}USB接口IP持久化配置已创建${NC}"
        fi
    fi

    # 配置DHCP服务器
    echo "  配置DHCP服务器..."
    mkdir -p /etc/dnsmasq.d 2>/dev/null || true

    DHCP_CONF="# 为USB网卡提供DHCP服务（自动生成）\n"
    if [ -n "$USB_IFACE_LIST" ]; then
        for ITEM in $USB_IFACE_LIST; do
            IFACE_NAME=$(echo "$ITEM" | cut -d: -f1)
            IFACE_GW=$(echo "$ITEM" | cut -d: -f2)
            DHCP_START=$(echo "$ITEM" | cut -d: -f3)
            DHCP_END=$(echo "$ITEM" | cut -d: -f4)
            DHCP_CONF="${DHCP_CONF}interface=${IFACE_NAME}\n"
            DHCP_CONF="${DHCP_CONF}dhcp-range=${IFACE_NAME},${DHCP_START},${DHCP_END},12h\n"
            DHCP_CONF="${DHCP_CONF}dhcp-option=${IFACE_NAME},3,${IFACE_GW}\n"
            DHCP_CONF="${DHCP_CONF}dhcp-option=${IFACE_NAME},6,${DNS}\n"
            DHCP_CONF="${DHCP_CONF}listen-address=${IFACE_GW}\n"
        done
    else
        DHCP_CONF="${DHCP_CONF}# 未检测到USB接口，使用默认配置\n"
        DHCP_CONF="${DHCP_CONF}interface=usb0\n"
        DHCP_CONF="${DHCP_CONF}dhcp-range=usb0,192.168.42.100,192.168.42.200,12h\n"
        DHCP_CONF="${DHCP_CONF}dhcp-option=usb0,3,192.168.42.1\n"
        DHCP_CONF="${DHCP_CONF}dhcp-option=usb0,6,${DNS}\n"
        DHCP_CONF="${DHCP_CONF}listen-address=192.168.42.1\n"
    fi
    DHCP_CONF="${DHCP_CONF}port=53\n"
    echo -e "$DHCP_CONF" > /etc/dnsmasq.d/usb-dhcp.conf
    echo -e "    ${GREEN}dnsmasq配置文件已生成${NC}"

    # 重启dnsmasq服务
    if [ "$OS" = "macOS" ]; then
        launchctl stop homebrew.mxcl.dnsmasq 2>/dev/null || true
        launchctl start homebrew.mxcl.dnsmasq 2>/dev/null || true
    else
        systemctl restart dnsmasq
        systemctl enable dnsmasq
    fi

    # 验证dnsmasq服务状态
    if [ "$OS" = "macOS" ]; then
        if pgrep -x dnsmasq >/dev/null 2>&1; then
            echo -e "    ${GREEN}dnsmasq服务运行正常${NC}"
        else
            echo -e "    ${YELLOW}dnsmasq服务启动失败，请手动启动${NC}"
            launchctl load /opt/homebrew/opt/dnsmasq/homebrew.mxcl.dnsmasq.plist 2>/dev/null || true
        fi
    else
        if systemctl is-active --quiet dnsmasq; then
            echo -e "    ${GREEN}dnsmasq服务运行正常${NC}"
        else
            echo -e "    ${RED}dnsmasq服务启动失败${NC}"
            echo -e "    ${YELLOW}尝试查看日志: journalctl -u dnsmasq -n 20${NC}"
        fi
    fi
fi
echo -e "${GREEN}DHCP服务器配置完成${NC}"



# -------------------------- 步骤6：安装ADB工具 --------------------------
echo -e "${BLUE}[步骤6] 安装ADB工具...${NC}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[Dry-Run] 跳过实际安装${NC}"
else
    if [ "$OS" = "macOS" ]; then
        if ! command -v adb &>/dev/null; then
            echo "  安装 adb..."
            if command -v brew &>/dev/null; then
                brew install --cask android-platform-tools
            else
                echo -e "    ${YELLOW}请手动安装 adb: brew install --cask android-platform-tools${NC}"
            fi
        fi
    else
        apt install android-tools-adb -y
    fi
fi
echo -e "${GREEN}ADB工具安装完成${NC}"

# -------------------------- 步骤7：批量配置手机通过电脑上网（反向共享） --------------------------
echo -e "${BLUE}[步骤7] 批量配置手机通过电脑上网（反向共享）...${NC}"

# 检查ADB设备连接
DEVICES=$(adb devices | grep -E '\tdevice$' | awk '{print $1}' | grep -v "^$" | grep -v "^List$")
DEVICE_COUNT=$(echo "$DEVICES" | grep -c . || echo "0")
if [ "$DEVICE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}警告：未检测到ADB设备，请检查USB连接和USB调试开关${NC}"
    echo "    跳过手机网络配置步骤"
else
    echo -e "${GREEN}检测到 $DEVICE_COUNT 台ADB设备${NC}"

    # ===================== 阶段1: 开启手机USB网络共享(RNDIS) =====================
    # 让手机开启RNDIS模式，电脑端才会出现USB网络接口(usb0等)
    # 注意：RNDIS让手机作为USB网卡设备被电脑识别，手机上网的路由在阶段3配置
    echo -e "  ${YELLOW}[阶段1]${NC} 开启手机USB网络共享(RNDIS)..."
    DEVICE_IFACE_MAP=""  # 记录 设备:USB接口 的映射关系

    for DEVICE in $DEVICES; do
        if [ -z "$DEVICE" ] || [ "$DEVICE" = "List" ]; then
            continue
        fi
        MODEL=$(adb -s "$DEVICE" shell getprop ro.product.model 2>/dev/null || echo "未知")
        ANDROID_VERSION=$(adb -s "$DEVICE" shell getprop ro.build.version.release 2>/dev/null || echo "未知")
        ANDROID_SDK=$(adb -s "$DEVICE" shell getprop ro.build.version.sdk 2>/dev/null || echo "0")
        ANDROID_VERSION=$(echo "$ANDROID_VERSION" | tr -d '\r')
        ANDROID_SDK=$(echo "$ANDROID_SDK" | tr -d '\r')
        echo "    设备: $DEVICE (型号: $MODEL, Android: $ANDROID_VERSION, SDK: $ANDROID_SDK)"

        # 记录开启RNDIS前的网络接口列表
        IFACES_BEFORE=$(ls /sys/class/net/ 2>/dev/null | sort)

        # 尝试多种方法开启USB网络共享(RNDIS)
        USB_ENABLED=false

        # 根据Android版本选择不同策略
        if [ "$ANDROID_SDK" -ge 30 ] 2>/dev/null; then
            # Android 11+ (SDK 30+): 优先使用 rndis,adb 组合，保留adb连接
            if adb -s "$DEVICE" shell svc usb setFunctions rndis,adb 2>/dev/null; then
                USB_ENABLED=true
            elif adb -s "$DEVICE" shell svc usb setFunctions rndis 2>/dev/null; then
                USB_ENABLED=true
            fi
        else
            # Android 8-10 (SDK 26-29): 优先使用 rndis 单独模式
            if adb -s "$DEVICE" shell svc usb setFunctions rndis 2>/dev/null; then
                USB_ENABLED=true
            elif adb -s "$DEVICE" shell svc usb setFunctions rndis,adb 2>/dev/null; then
                USB_ENABLED=true
            fi
        fi

        # 备用方法
        if [ "$USB_ENABLED" = false ]; then
            adb -s "$DEVICE" shell settings put global tether_dun_required 0 2>/dev/null || true
            adb -s "$DEVICE" shell svc usb setFunctions rndis,mtp,adb 2>/dev/null && USB_ENABLED=true || true
        fi

        if [ "$USB_ENABLED" = true ]; then
            echo -e "      ${GREEN}USB网络共享(RNDIS)已开启${NC}"

            # 等待USB网络接口出现（最多等10秒）
            echo "      等待USB网络接口出现..."
            NEW_IFACE=""
            for WAIT_SEC in $(seq 1 10); do
                sleep 1
                IFACES_AFTER=$(ls /sys/class/net/ 2>/dev/null | sort)
                NEW_IFACE=$(comm -13 <(echo "$IFACES_BEFORE") <(echo "$IFACES_AFTER") | head -1 || true)
                if [ -n "$NEW_IFACE" ]; then
                    break
                fi
            done

            if [ -n "$NEW_IFACE" ]; then
                echo -e "      ${GREEN}检测到新USB接口: $NEW_IFACE${NC}"
                DEVICE_IFACE_MAP="${DEVICE_IFACE_MAP}${DEVICE}:${NEW_IFACE} "
            else
                echo -e "      ${YELLOW}未检测到新USB接口，尝试使用已有的USB接口${NC}"
                EXISTING_USB=$(ip link show | grep 'usb' | awk '{print $2}' | sed 's/@.*//; s/://' | head -1 || true)
                if [ -n "$EXISTING_USB" ]; then
                    echo "      使用已有USB接口: $EXISTING_USB"
                    DEVICE_IFACE_MAP="${DEVICE_IFACE_MAP}${DEVICE}:${EXISTING_USB} "
                fi
            fi
        else
            echo -e "      ${YELLOW}USB网络共享开启失败，请手动在设置中开启USB网络共享${NC}"
            echo "      路径: 设置 -> 网络和互联网 -> 热点和网络共享 -> USB网络共享"
        fi
    done

    # ===================== 阶段2: 为新出现的USB接口配置IP和DHCP =====================
    echo -e "  ${YELLOW}[阶段2]${NC} 配置USB接口IP和更新DHCP..."
    if [ -n "$DEVICE_IFACE_MAP" ]; then
        EXISTING_USB_COUNT=$(echo "$USB_INTERFACES" | wc -w 2>/dev/null || echo "0")
        USB_IFACE_INDEX=$((EXISTING_USB_COUNT + 1))

        for ITEM in $DEVICE_IFACE_MAP; do
            DEV=$(echo "$ITEM" | cut -d: -f1)
            IFACE=$(echo "$ITEM" | cut -d: -f2)

            # 跳过已经在步骤5中配置过的接口
            if echo "$USB_IFACE_LIST" | grep -q "$IFACE:"; then
                echo "      接口 $IFACE 已在之前配置，跳过"
                continue
            fi

            USB_GW_IP="${USB_SUBNET_BASE}.${USB_IFACE_INDEX}"
            USB_DHCP_START="${USB_SUBNET_BASE}.$((USB_IFACE_INDEX * 10 + 100))"
            USB_DHCP_END="${USB_SUBNET_BASE}.$((USB_IFACE_INDEX * 10 + 200))"
            echo "      配置接口 $IFACE -> $USB_GW_IP/24 (设备: $DEV)"

            if [ "$OS" = "macOS" ]; then
                ifconfig "$IFACE" "$USB_GW_IP" netmask 255.255.255.0 up 2>/dev/null || true
            else
                ip addr flush dev "$IFACE" 2>/dev/null || true
                ip addr add "${USB_GW_IP}/24" dev "$IFACE" 2>/dev/null || true
                ip link set "$IFACE" up 2>/dev/null || true
            fi

            # 更新dnsmasq配置
            cat >> /etc/dnsmasq.d/usb-dhcp.conf << DHCP_APPEND

# 动态添加: 设备 $DEV 的接口 $IFACE
interface=${IFACE}
dhcp-range=${IFACE},${USB_DHCP_START},${USB_DHCP_END},12h
dhcp-option=${IFACE},3,${USB_GW_IP}
dhcp-option=${IFACE},6,${DNS}
listen-address=${USB_GW_IP}
DHCP_APPEND

            if [ "$OS" = "macOS" ]; then
                launchctl stop homebrew.mxcl.dnsmasq 2>/dev/null || true
                launchctl start homebrew.mxcl.dnsmasq 2>/dev/null || true
            else
                systemctl restart dnsmasq 2>/dev/null || true
            fi

            USB_IFACE_INDEX=$((USB_IFACE_INDEX + 1))
        done
        echo -e "    ${GREEN}USB接口IP和DHCP配置完成${NC}"
    else
        echo -e "    ${YELLOW}没有新的USB接口需要配置${NC}"
    fi

    # ===================== 阶段3: 配置手机端路由和DNS（反向共享核心） =====================
    # 这是实现"手机通过电脑上网"的关键步骤
    # 原理：手机开启RNDIS后，手机端会出现一个usb0网络接口
    #        需要通过adb配置手机端usb0的路由和DNS，让手机流量走USB接口
    echo -e "  ${YELLOW}[阶段3]${NC} 配置手机端路由和DNS（反向共享核心）..."
    for ITEM in $DEVICE_IFACE_MAP; do
        DEV=$(echo "$ITEM" | cut -d: -f1)
        PC_IFACE=$(echo "$ITEM" | cut -d: -f2)

        # 获取该设备对应的PC端USB接口网关IP
        PC_GW_IP=$(ip addr show dev "$PC_IFACE" 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d/ -f1 || true)
        if [ -z "$PC_GW_IP" ]; then
            echo -e "      ${YELLOW}无法获取接口 $PC_IFACE 的IP，跳过设备 $DEV${NC}"
            continue
        fi

        ANDROID_SDK=$(adb -s "$DEV" shell getprop ro.build.version.sdk 2>/dev/null | tr -d '\r' || echo "0")
        MODEL=$(adb -s "$DEV" shell getprop ro.product.model 2>/dev/null | tr -d '\r' || echo "未知")
        echo "      配置设备: $DEV ($MODEL, SDK: $ANDROID_SDK)"

        # 检查adb连接是否仍然可用
        if ! adb -s "$DEV" shell echo ok >/dev/null 2>&1; then
            echo -e "      ${YELLOW}adb连接已断开，尝试重新连接...${NC}"
            adb reconnect "$DEV" 2>/dev/null || true
            sleep 3
            if ! adb -s "$DEV" shell echo ok >/dev/null 2>&1; then
                echo -e "      ${RED}无法重新连接设备 $DEV，请检查USB连接${NC}"
                continue
            fi
            echo -e "      ${GREEN}adb重新连接成功${NC}"
        fi

        # 获取手机端usb0接口名称
        PHONE_USB_IFACE=$(adb -s "$DEV" shell ip link show 2>/dev/null | grep -E 'usb|rndis' | awk -F: '{print $2}' | awk '{print $1}' | head -1 || true)
        PHONE_USB_IFACE=$(echo "$PHONE_USB_IFACE" | tr -d '\r')
        if [ -z "$PHONE_USB_IFACE" ]; then
            PHONE_USB_IFACE="usb0"
            echo "      未检测到手机端USB接口名，使用默认: $PHONE_USB_IFACE"
        else
            echo "      手机端USB接口: $PHONE_USB_IFACE"
        fi

        # 计算手机端IP（与PC端网关IP同网段，末位+10避免冲突）
        PHONE_IP=$(echo "$PC_GW_IP" | awk -F. '{print $1"."$2"."$3"."($4+10)}')

        # 配置手机端IP
        echo "      配置手机端IP: $PHONE_USB_IFACE -> $PHONE_IP/24"
        adb -s "$DEV" shell ip addr flush dev "$PHONE_USB_IFACE" 2>/dev/null || true
        adb -s "$DEV" shell ip addr add "${PHONE_IP}/24" dev "$PHONE_USB_IFACE" 2>/dev/null || true
        adb -s "$DEV" shell ip link set "$PHONE_USB_IFACE" up 2>/dev/null || true

        # 配置默认路由
        echo "      配置手机端默认路由 -> $PC_GW_IP"
        adb -s "$DEV" shell ip route del default 2>/dev/null || true
        if adb -s "$DEV" shell ip route add default via "$PC_GW_IP" dev "$PHONE_USB_IFACE" 2>/dev/null; then
            echo -e "      ${GREEN}默认路由配置成功${NC}"
        else
            adb -s "$DEV" shell route add default gw "$PC_GW_IP" dev "$PHONE_USB_IFACE" 2>/dev/null || true
            echo -e "      ${GREEN}默认路由配置成功(使用route命令)${NC}"
        fi

        # 配置DNS
        echo "      配置手机端DNS -> $DNS"
        DNS_CONFIGURED=false
        if [ "$ANDROID_SDK" -ge 28 ] 2>/dev/null; then
            # Android 9+ (SDK 28+): 使用 ndc resolver
            adb -s "$DEV" shell ndc resolver setnetdns "$PHONE_USB_IFACE" "" "$DNS" 2>/dev/null && DNS_CONFIGURED=true || true
            adb -s "$DEV" shell ndc resolver setdefaultif "$PHONE_USB_IFACE" 2>/dev/null || true
        fi

        if [ "$DNS_CONFIGURED" = false ]; then
            # Android 8 (SDK 26-27) 或 ndc 失败时: 使用 setprop
            adb -s "$DEV" shell setprop net.dns1 "$DNS" 2>/dev/null && DNS_CONFIGURED=true || true
            adb -s "$DEV" shell setprop net.dns2 "8.8.4.4" 2>/dev/null || true
        fi

        if [ "$DNS_CONFIGURED" = true ]; then
            echo -e "      ${GREEN}DNS配置成功${NC}"
        else
            echo -e "      ${YELLOW}DNS配置可能失败，手机可能需要手动设置DNS${NC}"
        fi

        # Android 14+ (SDK 34+): 关闭私有DNS避免干扰
        if [ "$ANDROID_SDK" -ge 34 ] 2>/dev/null; then
            echo "      关闭私有DNS (Android 14+)..."
            adb -s "$DEV" shell settings put global private_dns_mode off 2>/dev/null || true
        fi

        echo -e "      ${GREEN}设备 $DEV 反向共享配置完成${NC}"
    done

    # ===================== 阶段4: 关闭WiFi =====================
    echo -e "  ${YELLOW}[阶段4]${NC} 关闭手机WiFi..."
    for DEVICE in $DEVICES; do
        if [ -z "$DEVICE" ] || [ "$DEVICE" = "List" ]; then
            continue
        fi
        WIFI_CLOSED=false
        # 方法1: svc wifi disable
        if adb -s "$DEVICE" shell svc wifi disable 2>/dev/null; then
            WIFI_CLOSED=true
        # 方法2: settings put
        elif adb -s "$DEVICE" shell settings put global wifi_on 0 2>/dev/null; then
            WIFI_CLOSED=true
        # 方法3: am broadcast
        elif adb -s "$DEVICE" shell am broadcast -a android.net.wifi.STATE_CHANGE -e enabled false 2>/dev/null; then
            WIFI_CLOSED=true
        fi

        if [ "$WIFI_CLOSED" = true ]; then
            echo -e "    ${GREEN}$DEVICE WiFi已关闭${NC}"
        else
            echo -e "    ${YELLOW}$DEVICE WiFi关闭失败，请手动关闭${NC}"
        fi
    done
    echo -e "${GREEN}手机网络配置完成${NC}"
fi


# -------------------------- 步骤8：最终验证 --------------------------
echo -e "${BLUE}[步骤8] 最终验证...${NC}"

# 验证IP配置
echo "  - 验证IP配置..."
if [ "$OS" = "macOS" ]; then
    CURRENT_IP=$(ifconfig "$ETH" | grep "inet " | awk '{print $2}' | cut -d'/' -f1)
else
    CURRENT_IP=$(ip addr show dev ${ETH} | grep "inet " | awk '{print $2}' | cut -d'/' -f1)
fi
if [ "$CURRENT_IP" = "$IP" ]; then
    echo -e "    ${GREEN}IP配置正确: $CURRENT_IP${NC}"
else
    echo -e "    ${RED}IP配置错误: 当前=$CURRENT_IP, 期望=$IP${NC}"
fi

# 验证IP转发
echo "  - 验证IP转发..."
if [ "$OS" = "macOS" ]; then
    IP_FORWARD=$(sysctl -n net.inet.ip.forwarding)
else
    IP_FORWARD=$(sysctl -n net.ipv4.ip_forward)
fi
if [ "$IP_FORWARD" = "1" ]; then
    echo -e "    ${GREEN}IP转发已开启${NC}"
else
    echo -e "    ${RED}IP转发未开启${NC}"
fi

# 验证NAT规则
echo "  - 验证NAT规则..."
if [ "$OS" = "macOS" ]; then
    if [ -f /etc/pf.anchors/nat ] && grep -q "$ETH" /etc/pf.anchors/nat 2>/dev/null; then
        echo -e "    ${GREEN}NAT规则已配置${NC}"
    else
        echo -e "    ${YELLOW}NAT规则未配置（macOS pf）${NC}"
    fi
else
    if iptables -t nat -L POSTROUTING | grep -q "MASQUERADE"; then
        echo -e "    ${GREEN}NAT规则已配置${NC}"
    else
        echo -e "    ${RED}NAT规则未配置${NC}"
    fi
fi

# 验证dnsmasq服务
echo "  - 验证dnsmasq服务..."
if [ "$OS" = "macOS" ]; then
    if pgrep -x dnsmasq >/dev/null 2>&1; then
        echo -e "    ${GREEN}dnsmasq服务运行正常${NC}"
    else
        echo -e "    ${RED}dnsmasq服务未运行${NC}"
    fi
else
    if systemctl is-active --quiet dnsmasq; then
        echo -e "    ${GREEN}dnsmasq服务运行正常${NC}"
    else
        echo -e "    ${RED}dnsmasq服务未运行${NC}"
    fi
fi

# 验证手机连通性
echo "  - 验证手机连通性..."
if [ -n "$DEVICE_IFACE_MAP" ]; then
    for ITEM in $DEVICE_IFACE_MAP; do
        DEV=$(echo "$ITEM" | cut -d: -f1)
        PC_IFACE=$(echo "$ITEM" | cut -d: -f2)
        PC_GW_IP=$(ip addr show dev "$PC_IFACE" 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d/ -f1 || true)
        if [ -n "$PC_GW_IP" ]; then
            PHONE_IP=$(echo "$PC_GW_IP" | awk -F. '{print $1"."$2"."$3"."($4+10)}')
            if ping -c 1 -W 2 "$PHONE_IP" >/dev/null 2>&1; then
                echo -e "    ${GREEN}设备 $DEV ($PHONE_IP) 连通正常${NC}"
            else
                echo -e "    ${YELLOW}设备 $DEV ($PHONE_IP) 暂时无法ping通，可能需要等待DHCP分配${NC}"
            fi
        fi
    done
else
    echo -e "    ${YELLOW}未配置设备，跳过连通性验证${NC}"
fi

# 输出最终结果
echo ""
echo "====================================="
echo " 全部配置完成！"
echo " 主机IP：$IP（永久静态）"
echo " 网卡：$ETH"
echo " 网关：$GATEWAY"
echo " DNS：$DNS"
echo " 日志文件：$LOG_FILE"
echo " 备份目录：$BACKUP_DIR"
echo "====================================="
echo ""
echo "如需回滚配置，可执行以下命令:"
echo "  cp -r $BACKUP_DIR/* /etc/"
echo "  netplan apply"
echo -e "${GREEN}DHCP服务器配置完成${NC}"
