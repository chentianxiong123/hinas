#!/system/bin/sh
# eth0.sh - 网络初始化脚本
# ZTE B860AV1.1-T2 机顶盒

# 加载 WiFi 驱动
insmod /system/lib/modules/8189fs.ko
sleep 2

# 启动 wpa_supplicant
wpa_supplicant -B -iwlan0 -c /data/wpa.conf
sleep 3

# 获取 IP 地址
dhcpcd wlan0
sleep 2

# 配置 DNS
setprop net.dns1 8.8.8.8
setprop net.dns2 8.8.4.4

# 启用 ADB over TCP
setprop service.adb.tcp.port 5555
stop adbd
start adbd

# 设置主机名
setprop persist.sys.hostname alpine
setprop net.hostname alpine

# 设置路由
route add default gw 192.168.31.1

echo "网络初始化完成"
