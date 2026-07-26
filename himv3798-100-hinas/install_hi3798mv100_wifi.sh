#!/bin/bash

set -e

RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[34m"
PLAIN="\033[0m"

echo -e "${BLUE}========================================${PLAIN}"
echo -e "${GREEN}hi3798mv100 WiFi 驱动安装脚本${PLAIN}"
echo -e "${BLUE}========================================${PLAIN}"
echo ""

check_root() {
    if [ "$(id -u)" != "0" ]; then
        echo -e "${RED}错误：必须以 root 用户身份运行此脚本${PLAIN}"
        exit 1
    fi
}

check_system() {
    if [ ! -f "/etc/os-release" ]; then
        echo -e "${RED}错误：无法检测系统版本${PLAIN}"
        exit 1
    fi
    
    . /etc/os-release
    echo -e "${YELLOW}当前系统: $NAME $VERSION${PLAIN}"
}

install_wifi() {
    echo -e "${YELLOW}开始安装 WiFi 驱动...${PLAIN}"
    
    local WIFI_TAR="hi3798mv100_hinas_wifi.tar.gz"
    local WIFI_DIR="/tmp/wifi_install"
    
    mkdir -p "$WIFI_DIR"
    
    if [ ! -f "$WIFI_TAR" ]; then
        echo -e "${RED}错误：未找到 $WIFI_TAR${PLAIN}"
        exit 1
    fi
    
    echo -e "${BLUE}解压驱动包...${PLAIN}"
    tar -zxf "$WIFI_TAR" -C "$WIFI_DIR"
    
    echo -e "${BLUE}安装驱动文件...${PLAIN}"
    cp -rf "$WIFI_DIR"/* /
    
    echo -e "${BLUE}更新模块依赖...${PLAIN}"
    depmod -a
    
    echo -e "${BLUE}加载 WiFi 模块...${PLAIN}"
    modprobe mt7601u || modprobe mt76x0u || true
    
    echo -e "${GREEN}WiFi 驱动安装完成！${PLAIN}"
    echo ""
    echo -e "${YELLOW}请重启系统以生效，或执行:${PLAIN}"
    echo -e "${BLUE}  reboot${PLAIN}"
}

check_root
check_system
install_wifi