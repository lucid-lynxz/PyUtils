#!/bin/bash
# ##############################################################################
# 脚本名称: setup_all.sh
# 功能总览:
# 1. 配置主机静态IP、网关、DNS（Ubuntu使用Netplan，macOS使用networksetup）
# 2. 开启系统IP转发，让主机具备路由器功能
# 3. 配置NAT流量转发，实现USB设备共享主机有线上网
# 4. 批量ADB操作：设备开启USB网络共享、强制关闭WiFi
# 5. 所有配置永久生效，服务器重启后不丢失
# 适用环境: Ubuntu 20.04+ 或 macOS 10.15+ 系统 + USB集线器 + 安卓设备
# 版本: 1.5 (兼容Ubuntu和macOS)
# 版本: 2.0 (兼容有线和无线网络)
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
    echo -e "${RED}❌ 错误：请使用 sudo 运行此脚本${NC}"
    echo "   示例: sudo $0"
    exit 1
fi

set -e  # 开启严格模式：任意命令执行失败，脚本直接退出
# 注意：移除了 set -x 以避免泄露敏感信息（如 WiFi 密码）

# ======================== 系统检测 ========================
# 检测操作系统
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
# 脚本存放目录（所有脚本、日志、备份都存放在此目录）
# 使用 ~/setup_all/ 作为主目录，兼容 Linux 和 macOS
SCRIPT_DIR="$HOME/setup_all"

# 备份目录（每次运行生成唯一目录）
BACKUP_DIR="${SCRIPT_DIR}/backup_$(date +%Y%m%d_%H%M%S)"

# 日志文件（每次运行生成唯一日志文件）
LOG_FILE="${SCRIPT_DIR}/setup_all_$(date +%Y%m%d_%H%M%S).log"
# 确保目录存在且有写权限
mkdir -p "$SCRIPT_DIR" 2>/dev/null || true
# 修复目录权限（如果目录所有者是 root，则改为当前用户）
if [ -d "$SCRIPT_DIR" ] && [ "$(stat -f %u "$SCRIPT_DIR" 2>/dev/null)" = "0" ]; then
    chown -R "$USER" "$SCRIPT_DIR" 2>/dev/null || true
fi
# 同时输出到屏幕和日志文件（日志中移除 ANSI 颜色代码）
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

# ======================== 网络核心变量（可通过参数传入）========================
# 默认值（根据当前电脑配置）
# 
# 获取网络配置信息的方法：
# 
# macOS:
#   - 获取 IP 和网卡: ifconfig | grep "inet " | grep -v "127.0.0.1"
#   - 获取网关: netstat -nr | grep "default" | grep -v "::" | awk '{print $2}'
#   - 获取 DNS: scutil --dns | grep "nameserver\[0\]" | head -1 | awk '{print $3}'
#
# Ubuntu/Linux:
#   - 获取 IP 和网卡: ip addr show | grep "inet " | grep -v "127.0.0.1"
#   - 获取网关: ip route | grep "default" | awk '{print $3}'
#   - 获取 DNS: cat /etc/resolv.conf | grep "nameserver" | head -1 | awk '{print $2}'
#
DEFAULT_IP="30.85.204.150"
DEFAULT_ETH="en0"
DEFAULT_GATEWAY="30.85.204.1"
DEFAULT_DNS="30.30.30.30"

# 检查交互式模式
INTERACTIVE=false
if [ "$1" = "--interactive" ]; then
    INTERACTIVE=true
    shift
fi

# 使用参数传入的值（如果提供）
IP="${1:-$DEFAULT_IP}"
ETH="${2:-$DEFAULT_ETH}"
GATEWAY="${3:-$DEFAULT_GATEWAY}"
DNS="${4:-$DEFAULT_DNS}"
# ==================================================================================================

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
echo ""
echo "  网络模式: $(if $WIFI_MODE; then echo "WiFi"; else echo "有线"; fi)"
echo ""

# 判断是否是无线接口
is_wireless() {
    if [ "$OS" = "macOS" ]; then
        # macOS: 检查接口是否是 WiFi 接口
        # 使用 networksetup -listallhardwareports 获取所有硬件端口，检查接口是否属于 Wi-Fi
        local wifi_iface=$(networksetup -listallhardwareports 2>/dev/null | grep -B1 "Device: $1" | grep -q "Hardware Port: Wi-Fi" && echo "yes" || true)
        if [ "$wifi_iface" = "yes" ]; then
            return 0
        fi
        return 1
    else
        # Linux: 使用 iw 命令检测无线接口（更可靠）
        if command -v iw &>/dev/null; then
            iw dev "$1" info &>/dev/null && return 0 || return 1
        else
            # 备用方案：检查接口名称是否包含 wlan/wlp
            echo "$1" | grep -qE '^wlan|^wlp' && return 0 || return 1
        fi
    fi
}

# 检查系统版本兼容性
echo -e "${BLUE}[步骤0] 检查系统版本...${NC}"
if [ "$OS" = "macOS" ]; then
    echo -e "${GREEN}✅ 检测到macOS版本: $OS_VERSION${NC}"
else
    UBUNTU_VERSION=$(lsb_release -rs 2>/dev/null || cat /etc/issue | grep -oP '\d+\.\d+' | head -1)
    if [ -z "$UBUNTU_VERSION" ]; then
        echo -e "${YELLOW}⚠️  警告：无法检测Ubuntu版本，请确认系统为Ubuntu 18.04+${NC}"
    else
        echo -e "${GREEN}✅ 检测到Ubuntu版本: $UBUNTU_VERSION${NC}"
        # 检查版本是否 >= 18.04
        if [ "$(echo "$UBUNTU_VERSION < 18.04" | bc)" -eq 1 ]; then
            echo -e "${RED}❌ 错误：需要Ubuntu 18.04或更高版本${NC}"
            exit 1
        fi
    fi
fi

# 自动安装依赖
echo -e "${BLUE}[步骤0.1] 检查并安装依赖...${NC}"
if [ "$OS" = "macOS" ]; then
    # macOS 使用 Homebrew（注意：Homebrew 不允许以 root 运行，需要使用 sudo -u $USER）
    if ! command -v brew &>/dev/null; then
        echo -e "${YELLOW}⚠️  警告：未检测到 Homebrew，建议安装${NC}"
        echo "  安装命令: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    else
        # 检查并安装 dnsmasq（Homebrew 不允许 root，需手动安装）
        if ! command -v dnsmasq &>/dev/null; then
            echo -e "    ${YELLOW}⚠️  未检测到 dnsmasq，请手动安装${NC}"
            echo "    运行以下命令安装: brew install dnsmasq"
        else
            echo -e "    ${GREEN}✅ dnsmasq 已安装${NC}"
        fi
        # 检查并安装 adb（Homebrew 不允许 root，需手动安装）
        if ! command -v adb &>/dev/null; then
            echo -e "    ${YELLOW}⚠️  未检测到 adb，请手动安装${NC}"
            echo "    运行以下命令安装: brew install --cask android-platform-tools"
        else
            echo -e "    ${GREEN}✅ adb 已安装${NC}"
        fi
    fi
else
    # Ubuntu 使用 apt
    # 检查并安装 netplan
    if ! command -v netplan &>/dev/null; then
        echo "  安装 netplan..."
        apt update
        apt install netplan -y
    fi
    # 检查并安装 bc
    if ! command -v bc &>/dev/null; then
        echo "  安装 bc..."
        apt install bc -y
    fi
fi
echo -e "${GREEN}✅ 依赖检查完成${NC}"
echo ""

# -------------------------- 步骤1：创建脚本存放目录和备份目录 --------------------------
# -p 参数：目录不存在则创建，存在不报错
echo "[步骤1] 创建脚本存放目录和备份目录..."
mkdir -p "$SCRIPT_DIR"
mkdir -p "$BACKUP_DIR"
echo "✅ 备份目录: $BACKUP_DIR"

# 备份原始配置文件
echo "[步骤1.1] 备份原始配置文件..."
if [ -f "$NETWORK_INTERFACES" ]; then
    cp "$NETWORK_INTERFACES" "$BACKUP_DIR/"
    echo "✅ 已备份 $NETWORK_INTERFACES"
fi
if [ -f "$SYSCTL_CONF" ]; then
    cp "$SYSCTL_CONF" "$BACKUP_DIR/"
    echo "✅ 已备份 $SYSCTL_CONF"
fi
if [ -d "$IPTABLES_DIR" ]; then
    cp -r "$IPTABLES_DIR" "$BACKUP_DIR/"
    echo "✅ 已备份 $IPTABLES_DIR"
fi

# -------------------------- 步骤2：检测USB网络接口 --------------------------
echo -e "${BLUE}[步骤2] 检测USB网络接口...${NC}"
# 使用更健壮的语法检测USB网络接口
if [ "$OS" = "macOS" ]; then
    # macOS 使用 ifconfig
    USB_INTERFACES=$(ifconfig -l | tr ' ' '\n' | grep -E '^en[0-9]+' || true)
    echo "    当前网络接口列表:"
    ifconfig -l | tr ' ' '\n' | while read IFACE; do
        echo "    - $IFACE"
    done
else
    # Linux 使用 ip link
    USB_INTERFACES=$(ip link show | grep 'usb' | awk '{print $2}' | sed 's/@.*//; s/:$//' || true)
    echo "    当前网络接口列表:"
    ip link show | awk '/^[0-9]+:/ {print "    " $2}' | sed 's/://g' || echo "    无法获取网络接口列表"
fi

if [ -z "$USB_INTERFACES" ]; then
    echo -e "${YELLOW}⚠️  警告：未检测到USB网络接口，请检查USB集线器和设备连接${NC}"
else
    echo -e "${GREEN}✅ 检测到USB网络接口: $USB_INTERFACES${NC}"
    USB_COUNT=$(echo "$USB_INTERFACES" | wc -w)
    echo "    共检测到 $USB_COUNT 个USB网络接口"
fi

# -------------------------- 步骤3：检查网卡并配置静态IP --------------------------
echo -e "${BLUE}[步骤3] 检查网卡并配置静态IP...${NC}"

# 检查有线网卡是否存在
if [ "$OS" = "macOS" ]; then
    if ! networksetup -listallhardwareports | grep -q "$ETH"; then
        echo -e "${RED}❌ 错误：网卡 $ETH 不存在${NC}"
        echo "    当前可用网卡列表:"
        networksetup -listallhardwareports | grep "Ethernet Address" -B1 | awk '/Hardware Port/ {print "    " $3}'
        exit 1
    fi
else
    if ! ip link show "$ETH" &>/dev/null; then
        echo -e "${RED}❌ 错误：网卡 $ETH 不存在${NC}"
        echo "    当前可用网卡列表:"
        ip link show | awk '/^[0-9]+:/ {print "    " $2}' | sed 's/://g'
        exit 1
    fi
fi
echo -e "${GREEN}✅ 网卡 $ETH 存在${NC}"

# 备份现有配置
if [ "$OS" = "macOS" ]; then
    # macOS 备份 networksetup 配置
    echo "  备份网络配置..."
    networksetup -listallnetworkservices > "$BACKUP_DIR/networkservices.txt" 2>/dev/null || true
    echo -e "    ${GREEN}✅ 已备份网络配置${NC}"
else
    # Ubuntu 备份 Netplan 配置
    if [ -d "$NETPLAN_DIR" ]; then
        cp -r "$NETPLAN_DIR" "$BACKUP_DIR/"
        echo -e "    ${GREEN}✅ 已备份 $NETPLAN_DIR${NC}"
    fi
fi

# 配置静态IP
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[Dry-Run] 跳过实际配置${NC}"
else
    if [ "$OS" = "macOS" ]; then
        # macOS 使用 networksetup
        echo "  配置网络..."
        # 获取网络服务名称（networksetup 需要服务名，而不是接口名）
        service_name=$(networksetup -listallhardwareports 2>/dev/null | grep -B1 "Device: $ETH" | grep "Hardware Port:" | sed 's/Hardware Port: //' || true)
        if [ -z "$service_name" ]; then
            echo -e "    ${RED}❌ 错误：无法找到网卡 $ETH 对应的网络服务名称${NC}"
            exit 1
        fi
        echo "    网络服务名称: $service_name"
        
        # 仅在使用有线网卡时关闭 WiFi，避免冲突
        if ! is_wireless "$ETH"; then
            # 动态获取 WiFi 服务名
            wifi_service=$(networksetup -listallnetworkservices 2>/dev/null | grep -v "^[[:space:]]*#" | grep -iE "Wi-Fi|Airport" | head -1 || true)
            if [ -n "$wifi_service" ]; then
                networksetup -setairportpower "$wifi_service" off 2>/dev/null || true
                echo "    已关闭 WiFi ($wifi_service) 避免冲突"
            fi
        fi
        
        # WiFi 模式使用 DHCP，有线模式使用静态 IP
        if is_wireless "$ETH"; then
            echo "    WiFi 模式，使用 DHCP 自动获取 IP..."
            networksetup -setdhcp "$service_name"
        else
            echo "    有线模式，配置静态 IP..."
            networksetup -setmanual "$service_name" "$IP" "255.255.255.0" "$GATEWAY"
            networksetup -setsearchdomains "$service_name" "$DNS"
        fi
        echo -e "    ${GREEN}✅ macOS网络配置完成${NC}"
    else
        # Ubuntu 使用 Netplan
        if is_wireless "$ETH"; then
            # 如果是无线网卡，则使用 wifis 配置（DHCP 模式）
            echo "  检测到无线网卡，使用 DHCP 自动获取 IP..."
            cat > "$NETPLAN_CONF" << EOF
network:
  version: 2
  wifis:
    ${ETH}:
      dhcp4: yes
EOF
        else
            # 有线网卡使用 ethernets（静态 IP）
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

        # 应用Netplan配置
        echo "  应用Netplan配置..."
        # 先进行语法校验，避免配置错误导致网络中断
        if ! netplan try; then
            echo -e "${RED}❌ Netplan配置校验失败，请检查 $NETPLAN_CONF${NC}"
            exit 1
        fi
        echo -e "${GREEN}✅ Netplan配置校验通过${NC}"

        # 应用配置
        if netplan apply; then
            echo -e "${GREEN}✅ Netplan配置应用成功${NC}"
        else
            echo -e "${RED}❌ Netplan配置应用失败${NC}"
            exit 1
        fi
    fi

    # 验证IP配置
    echo "  验证IP配置..."
    if [ "$OS" = "macOS" ]; then
        CURRENT_IP=$(ifconfig "$ETH" | grep "inet " | awk '{print $2}' | cut -d'/' -f1)
    else
        CURRENT_IP=$(ip addr show dev ${ETH} | grep "inet " | awk '{print $2}' | cut -d'/' -f1)
    fi
    if [ "$CURRENT_IP" = "$IP" ]; then
        echo -e "${GREEN}✅ IP配置验证成功: $CURRENT_IP${NC}"
    else
        echo -e "${RED}❌ IP配置验证失败: 当前=$CURRENT_IP, 期望=$IP${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✅ 静态IP配置完成${NC}"


# -------------------------- 步骤4：开启系统IP转发 --------------------------
echo -e "${BLUE}[步骤4] 开启系统IP转发...${NC}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[Dry-Run] 跳过实际配置${NC}"
else
    if [ "$OS" = "macOS" ]; then
        # macOS 使用 sysctl 开启IP转发
        echo "  开启IP转发..."
        sysctl -w net.inet.ip.forwarding=1
        echo "net.inet.ip.forwarding=1" >> /etc/sysctl.conf
    else
        # Ubuntu 使用 sysctl.conf
        # 检查并添加IP转发配置
        if grep -q "^net.ipv4.ip_forward=1" "$SYSCTL_CONF"; then
            echo -e "    ${GREEN}✅ IP转发配置已存在${NC}"
        elif grep -q "^#net.ipv4.ip_forward=1" "$SYSCTL_CONF"; then
            sed -i 's/^#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' "$SYSCTL_CONF"
            echo -e "    ${GREEN}✅ 已启用IP转发配置${NC}"
        else
            echo "net.ipv4.ip_forward=1" >> "$SYSCTL_CONF"
            echo -e "    ${GREEN}✅ 已添加IP转发配置${NC}"
        fi

        # 立即加载配置
        sysctl -p
    fi
fi
echo -e "${GREEN}✅ IP转发已开启${NC}"


# -------------------------- 步骤5：配置NAT流量转发和DHCP服务器 --------------------------
echo -e "${BLUE}[步骤5] 配置NAT流量转发和DHCP服务器...${NC}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[Dry-Run] 跳过实际配置${NC}"
else
    if [ "$OS" = "macOS" ]; then
        # macOS 使用 pf (Packet Filter) 进行NAT
        echo "  配置NAT规则..."
        # 确保 pf.anchors 目录存在
        mkdir -p /etc/pf.anchors 2>/dev/null || true
        cat > /etc/pf.anchors/nat << EOF
# NAT规则：USB网卡流量伪装成有线网卡IP
nat on $ETH from (en+) to any -> ($ETH)
EOF
        # 启用 pf 防火墙并重新加载配置
        pfctl -e 2>/dev/null || true
        pfctl -f /etc/pf.conf 2>/dev/null || true
        echo -e "    ${GREEN}✅ macOS NAT规则已配置${NC}"
    else
        # Ubuntu 使用 iptables
        apt update
        # 安装iptables持久化工具和dnsmasq
        apt install iptables-persistent dnsmasq -y

        # 配置NAT规则
        # 注意：只清空 NAT 规则，不清空过滤规则，避免影响其他防火墙配置
        iptables -t nat -F  # 清空旧的NAT转发规则
        # 核心NAT规则：所有USB网卡流量，伪装成主机有线网卡IP对外上网
        iptables -t nat -A POSTROUTING -o $ETH -j MASQUERADE
        # 允许所有转发流量通过
        iptables -A FORWARD -j ACCEPT
        # 保存防火墙规则
        netfilter-persistent save
        echo -e "    ${GREEN}✅ NAT流量转发配置完成${NC}"
    fi

    # 配置DHCP服务器
    echo "  配置DHCP服务器..."
    mkdir -p /etc/dnsmasq.d 2>/dev/null || true
    cat > /etc/dnsmasq.d/usb-dhcp.conf << EOF
# 为USB网卡提供DHCP服务
# 自动匹配所有以 usb 开头的接口
interface=usb+
dhcp-range=192.168.42.100,192.168.42.200,12h
dhcp-option=3,192.168.42.1
dhcp-option=6,$DNS
listen-address=192.168.42.1
port=53
EOF

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
            echo -e "    ${GREEN}✅ dnsmasq服务运行正常${NC}"
        else
            echo -e "    ${YELLOW}⚠️  dnsmasq服务启动失败，请手动启动${NC}"
            echo "    运行以下命令启动: launchctl load /opt/homebrew/opt/dnsmasq/homebrew.mxcl.dnsmasq.plist"
            if ! launchctl load /opt/homebrew/opt/dnsmasq/homebrew.mxcl.dnsmasq.plist; then
                echo -e "${RED}❌ dnsmasq服务加载失败${NC}"
                exit 1
            fi
        fi
    else
        if systemctl is-active --quiet dnsmasq; then
            echo -e "    ${GREEN}✅ dnsmasq服务运行正常${NC}"
        else
            echo -e "    ${RED}❌ dnsmasq服务启动失败${NC}"
        fi
    fi
fi
echo -e "${GREEN}✅ DHCP服务器配置完成${NC}"



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
                echo -e "    ${YELLOW}⚠️  请手动安装 adb: brew install --cask android-platform-tools${NC}"
            fi
        fi
    else
        apt install android-tools-adb -y
    fi
fi
echo -e "${GREEN}✅ ADB工具安装完成${NC}"

# -------------------------- 步骤7：批量配置所有主板网络模式 --------------------------
echo "[步骤7] 批量配置所有主板网络模式..."

# 检查ADB设备连接
# 使用更精确的匹配：只匹配第二列是 "device" 的行
DEVICES=$(adb devices | grep -E '\tdevice$' | awk '{print $1}' | grep -v "^$" | grep -v "^List$")
DEVICE_COUNT=$(echo "$DEVICES" | grep -c . || echo "0")
if [ "$DEVICE_COUNT" -eq 0 ]; then
    echo "⚠️  警告：未检测到ADB设备，请检查USB连接和USB调试开关"
    echo "    跳过主板网络配置步骤"
else
    echo "✅ 检测到 $DEVICE_COUNT 台ADB设备"
    # 调试输出
    echo "    [DEBUG] DEVICES: [$DEVICES]"

    # 1. 批量开启主板USB网络共享（RNDIS模式）
    echo "  - 开启USB网络共享..."
    # 使用 for 循环遍历设备列表
    for DEVICE in $DEVICES; do
        # 跳过无效设备名
        if [ -z "$DEVICE" ] || [ "$DEVICE" = "List" ]; then
            continue
        fi
        # 获取设备型号和Android版本
        MODEL=$(adb -s "$DEVICE" shell getprop ro.product.model 2>/dev/null || echo "未知")
        ANDROID_VERSION=$(adb -s "$DEVICE" shell getprop ro.build.version.release 2>/dev/null || echo "未知")
        echo "    设备: $DEVICE (型号: $MODEL, Android: $ANDROID_VERSION)"
        
        # 尝试多种方法开启USB网络共享
        USB_ENABLED=false
        # 方法1: 使用 svc usb setFunctions rndis
        if adb -s "$DEVICE" shell svc usb setFunctions rndis 2>/dev/null; then
            USB_ENABLED=true
        # 方法2: 使用 svc usb setFunctions rndis,adb (同时保留adb功能)
        elif adb -s "$DEVICE" shell svc usb setFunctions rndis,adb 2>/dev/null; then
            USB_ENABLED=true
        # 方法3: 使用 svc usb setFunctions rndis,mtp,adb
        elif adb -s "$DEVICE" shell svc usb setFunctions rndis,mtp,adb 2>/dev/null; then
            USB_ENABLED=true
        fi
        
        if [ "$USB_ENABLED" = true ]; then
            echo "      ✅ USB网络共享已开启"
        else
            echo "      ⚠️  USB网络共享开启失败，请手动在开发者选项中开启"
        fi
    done

    # 2. 批量关闭主板WiFi
    echo "  - 关闭WiFi..."
    for DEVICE in $DEVICES; do
        # 跳过无效设备名
        if [ -z "$DEVICE" ] || [ "$DEVICE" = "List" ]; then
            continue
        fi
        # 方法1: 使用 svc wifi disable
        if adb -s "$DEVICE" shell svc wifi disable 2>/dev/null; then
            echo "    ✅ $DEVICE WiFi已关闭"
        # 方法2: 使用 settings put 命令
        elif adb -s "$DEVICE" shell settings put global wifi_on 0 2>/dev/null; then
            echo "    ✅ $DEVICE WiFi已关闭 (使用settings命令)"
        # 方法3: 使用 am broadcast 发送 WiFi 关闭广播
        elif adb -s "$DEVICE" shell am broadcast -a android.net.wifi.STATE_CHANGE -e enabled false 2>/dev/null; then
            echo "    ✅ $DEVICE WiFi已关闭 (使用broadcast命令)"
        else
            echo "    ⚠️  $DEVICE WiFi关闭失败，请手动关闭"
        fi
    done
    echo "✅ 主板网络模式配置完成"
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
    echo -e "    ${GREEN}✅ IP配置正确: $CURRENT_IP${NC}"
else
    echo -e "    ${RED}❌ IP配置错误: 当前=$CURRENT_IP, 期望=$IP${NC}"
fi

# 验证IP转发
echo "  - 验证IP转发..."
if [ "$OS" = "macOS" ]; then
    IP_FORWARD=$(sysctl -n net.inet.ip.forwarding)
else
    IP_FORWARD=$(sysctl -n net.ipv4.ip_forward)
fi
if [ "$IP_FORWARD" = "1" ]; then
    echo -e "    ${GREEN}✅ IP转发已开启${NC}"
else
    echo -e "    ${RED}❌ IP转发未开启${NC}"
fi

# 验证NAT规则
echo "  - 验证NAT规则..."
if [ "$OS" = "macOS" ]; then
    # 检查 NAT 规则文件是否存在
    if [ -f /etc/pf.anchors/nat ] && grep -q "$ETH" /etc/pf.anchors/nat 2>/dev/null; then
        echo -e "    ${GREEN}✅ NAT规则已配置${NC}"
    else
        echo -e "    ${YELLOW}⚠️  NAT规则未配置（macOS pf）${NC}"
    fi
else
    if iptables -t nat -L POSTROUTING | grep -q "MASQUERADE"; then
        echo -e "    ${GREEN}✅ NAT规则已配置${NC}"
    else
        echo -e "    ${RED}❌ NAT规则未配置${NC}"
    fi
fi

# 验证dnsmasq服务
echo "  - 验证dnsmasq服务..."
if [ "$OS" = "macOS" ]; then
    # 检查 dnsmasq 进程是否存在
    if pgrep -x dnsmasq >/dev/null 2>&1; then
        echo -e "    ${GREEN}✅ dnsmasq服务运行正常${NC}"
    else
        echo -e "    ${RED}❌ dnsmasq服务未运行${NC}"
    fi
else
    if systemctl is-active --quiet dnsmasq; then
        echo -e "    ${GREEN}✅ dnsmasq服务运行正常${NC}"
    else
        echo -e "    ${RED}❌ dnsmasq服务未运行${NC}"
    fi
fi

# 输出最终结果
echo ""
echo "====================================="
echo " ✅ 全部配置完成！"
echo " ✅ 主机IP：$IP（永久静态）"
echo " ✅ 网卡：$ETH"
echo " ✅ 网关：$GATEWAY"
echo " ✅ DNS：$DNS"
echo " ✅ 日志文件：$LOG_FILE"
echo " ✅ 备份目录：$BACKUP_DIR"
echo "====================================="
echo ""
echo "如需回滚配置，可执行以下命令:"
echo "  cp -r $BACKUP_DIR/* /etc/"
echo "  netplan apply"
echo "====================================="
