#!/bin/bash
# ZTE B860AV1.1-T2 工具脚本

set -e

# 配置
TFTP_DIR="/tmp/tftp_test"
DEVICE_IP="192.168.0.22"
SERVER_IP="192.168.0.189"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 帮助
show_help() {
    echo "ZTE B860AV1.1-T2 工具脚本"
    echo ""
    echo "用法: $0 <命令>"
    echo ""
    echo "命令:"
    echo "  tftp-start    启动 TFTP 服务器"
    echo "  tftp-stop     停止 TFTP 服务器"
    echo "  flash-orig    刷入原始 boot 镜像"
    echo "  flash-head    刷入无头服务器 boot 镜像"
    echo "  connect       连接设备 (ADB)"
    echo "  status        查看设备状态"
    echo ""
}

# 启动 TFTP
start_tftp() {
    echo -e "${YELLOW}启动 TFTP 服务器...${NC}"
    sudo pkill -f "in.tftpd" 2>/dev/null || true
    sudo mkdir -p "$TFTP_DIR"
    sudo /usr/sbin/in.tftpd -l -s "$TFTP_DIR" -a 0.0.0.0:69 -t 30 &
    echo -e "${GREEN}TFTP 服务器已启动，目录: $TFTP_DIR${NC}"
}

# 停止 TFTP
stop_tftp() {
    echo -e "${YELLOW}停止 TFTP 服务器...${NC}"
    sudo pkill -f "in.tftpd" 2>/dev/null || true
    echo -e "${GREEN}TFTP 服务器已停止${NC}"
}

# 刷入原始 boot
flash_original() {
    echo -e "${YELLOW}准备刷入原始 boot 镜像...${NC}"
    cp boot/boot_original.bin "$TFTP_DIR/boot.img"
    echo -e "${GREEN}文件已复制到 TFTP 目录${NC}"
    echo ""
    echo "请在 U-Boot 中执行以下命令:"
    echo "  setenv ipaddr $DEVICE_IP"
    echo "  setenv serverip $SERVER_IP"
    echo "  tftp 0x48000000 boot.img"
    echo "  mmc write 0 0x48000000 0x228000 0x62dc"
    echo "  reset"
}

# 刷入无头服务器 boot
flash_headless() {
    echo -e "${YELLOW}准备刷入无头服务器 boot 镜像...${NC}"
    cp boot/boot_headless.bin "$TFTP_DIR/boot.img"
    echo -e "${GREEN}文件已复制到 TFTP 目录${NC}"
    echo ""
    echo "请在 U-Boot 中执行以下命令:"
    echo "  setenv ipaddr $DEVICE_IP"
    echo "  setenv serverip $SERVER_IP"
    echo "  tftp 0x48000000 boot.img"
    echo "  mmc write 0 0x48000000 0x228000 0x62dc"
    echo "  reset"
}

# 连接设备
connect_device() {
    echo -e "${YELLOW}连接设备...${NC}"
    adb connect "$DEVICE_IP:5555"
}

# 查看状态
show_status() {
    echo -e "${YELLOW}设备状态:${NC}"
    echo ""
    echo "网络连接:"
    ping -c 1 -W 2 "$DEVICE_IP" > /dev/null 2>&1 && echo "  设备: $DEVICE_IP - 在线" || echo "  设备: $DEVICE_IP - 离线"
    echo ""
    echo "ADB 连接:"
    adb devices 2>/dev/null | grep "$DEVICE_IP" || echo "  未连接"
}

# 主函数
case "${1:-}" in
    tftp-start)
        start_tftp
        ;;
    tftp-stop)
        stop_tftp
        ;;
    flash-orig)
        flash_original
        ;;
    flash-head)
        flash_headless
        ;;
    connect)
        connect_device
        ;;
    status)
        show_status
        ;;
    *)
        show_help
        ;;
esac
