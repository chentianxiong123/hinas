# WiFi 驱动调试与连接

## WiFi 硬件

- 芯片：Realtek 8189FS (SDIO接口)
- 驱动：`/system/lib/modules/8189fs.ko`
- 接口：wlan0, wlan1

## 驱动加载

```bash
insmod /system/lib/modules/8189fs.ko
```

加载后 dmesg 输出：
```
RTL871X: module init start
RTL871X: rtl8189fs v4.3.24_18813.20160729_beta
######set_wifi_en: WIFI_EN_ON-0:wifi_bt_open_cnt=0
wifi_gpio_en = 81
mmc1: new high speed SDIO card at address 0001
RTL871X: rtw_ndev_init(wlan0) if1 mac_addr=a4:40:27:9c:f2:48
RTL871X: rtw_ndev_init(wlan1) if2 mac_addr=a6:40:27:9c:f2:48
```

## 踩坑：wlan0 up 后 link is not ready

`ifconfig wlan0 up` 返回成功，但 operstate 仍是 down。

分析：这是正常现象。WiFi 的 "link is not ready" 表示还没连上 AP，和以太网没插网线一样。IPv6 ADDRCONF 消息是信息性的，不代表错误。

## 连接 WiFi

```bash
# 扫描
iwlist wlan0 scan | grep ESSID

# 启动 wpa_supplicant
wpa_supplicant -B -i wlan0 -c /data/wpa.conf

# 获取 IP
dhcpcd wlan0
```

wpa.conf 格式：
```
network={
    ssid="Xiaomi_F5A3"
    psk="123456789"
}
```

## 踩坑：dhcpcd 锁文件冲突

```
dhcpcd: flock `/data/misc/dhcp/dhcpcd-wlan0.pid': Try again
```

解决：
```bash
rm -f /data/misc/dhcp/dhcpcd-wlan0.pid
killall dhcpcd
dhcpcd wlan0
```

## 踩坑：dhcpcd waiting for carrier

WiFi 驱动加载后需要几秒才能关联 AP。dhcpcd 启动太快会等待 carrier。

解决：先 `wpa_supplicant`，等几秒再 `dhcpcd`。
