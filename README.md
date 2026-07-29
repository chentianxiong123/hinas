# ZTE B860AV1.1-T2 救砖与改造

## 项目概述

ZTE B860AV1.1-T2 机顶盒救砖记录、固件分析和无头服务器改造方案。

## 设备信息

- **型号**: ZTE B860AV1.1-T2
- **芯片**: ZX296716 (中兴微)
- **系统**: Android 4.4.2 (KitKat)
- **内存**: 1GB RAM
- **存储**: 4GB eMMC
- **WiFi**: Realtek RTL8189FS

## 文件说明

### boot/
- `boot_original.bin` - 原始 boot 分区备份
- `boot_headless.bin` - 改造后的 boot 镜像（无头服务器版本）

### docs/
- `ZTE_B860AV1.1-T2_救砖记录.md` - 完整的救砖和改造记录

## 无头服务器改造

### 改造内容
1. 删除 Android 框架（surfaceflinger, zygote, media 等）
2. 保留 Linux 核心（libc, libm, libdl 等）
3. 配置 WiFi 自动连接
4. 开机自启 ADB 和 Telnet

### 关键修改
- `init.rc`: `panic_on_oops` 从 1 改成 0
- `init.zxic.rc`: `zte_post_boot` 服务从 `class main` 改成 `class core`
- 添加 `/system/etc/init.zte.post_boot.sh` 开机脚本

### 开机脚本功能
```sh
#!/system/bin/sh
insmod /system/lib/modules/8189fs.ko
/system/bin/wpa_supplicant -Dnl80211 -iwlan0 -c /system/etc/wpa_supplicant.conf -B
/system/bin/dhcpcd wlan0
/sbin/adbd &
/system/xbin/telnetd -l /system/bin/sh
ifconfig eth0 up
/system/bin/dhcpcd eth0
```

## 使用方法

### 救砖
```bash
# U-Boot 中执行
setenv ipaddr 192.168.0.22
setenv serverip 192.168.0.189
tftp 0x48000000 boot_original.bin
mmc write 0 0x48000000 0x228000 0x62dc
reset
```

### 刷入无头服务器 boot
```bash
# U-Boot 中执行
setenv ipaddr 192.168.0.22
setenv serverip 192.168.0.189
tftp 0x48000000 boot_headless.bin
mmc write 0 0x48000000 0x228000 0x62dc
reset
```

### WiFi 配置
编辑 `/system/etc/wpa_supplicant.conf`:
```
ctrl_interface=/data/misc/wifi/sockets
update_config=1
device_name=zte_b860av

network={
    ssid="你的WiFi名"
    psk="你的WiFi密码"
    key_mgmt=WPA-PSK
    priority=1
}
```

## 分区表

| 分区 | 偏移 | 大小 | 用途 |
|------|------|------|------|
| bootloader | 0x0 | 4MB | U-Boot |
| conf | 0x6c00000 | 4MB | 启动计数器 |
| cache | 0x7800000 | 768MB | 缓存 |
| env | 0x38000000 | 8MB | U-Boot 环境 |
| logo | 0x39000000 | 32MB | 开机画面 |
| recovery | 0x3b800000 | 32MB | 恢复模式 |
| misc | 0x42800000 | 32MB | BCB 命令 |
| boot | 0x45000000 | 32MB | 内核+ramdisk |
| system | 0x47800000 | 1GB | 系统分区 |
| data | 0x88000000 | 1.5GB | 用户数据 |

## 连接方式

- **串口**: `/dev/ttyUSB0` 115200 baud
- **ADB**: `adb connect <设备IP>:5555`
- **Telnet**: `telnet <设备IP>`

## 注意事项

1. **启动计数器**存储在 conf 分区，清空 conf 可重置计数器
2. **boot 镜像对齐**必须严格按页大小（0x800）
3. **WiFi 模块版本**必须匹配运行内核（`4.1.18-svn103878`）
4. **libkeystore_binder.so** 是 wpa_supplicant 的依赖，不能删

## 许可证

MIT License
