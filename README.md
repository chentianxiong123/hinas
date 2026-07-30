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
- `boot_headless.bin` - 改造后的 boot 镜像（无头服务器版本 + 内核补丁绕过 PARANOID_NETWORK + ZRAM 512MB）

### docs/
- `ZTE_B860AV1.1-T2_救砖记录.md` - 完整的救砖和改造记录
- `14_Android_Chroot网络权限解决方案.md` - Chroot 网络权限 GID 方案
- `15_Android内核二进制补丁绕过PARANOID_NETWORK.md` - 内核二进制补丁方案

## 无头服务器改造

### 改造内容
1. 删除 Android 框架（surfaceflinger, zygote, media 等）
2. 保留 Linux 核心（libc, libm, libdl 等）
3. 配置 WiFi 自动连接
4. 开机自启 SSH
5. 内核补丁绕过 `CONFIG_ANDROID_PARANOID_NETWORK`
6. ZRAM 512MB swap 自动启用

### 关键修改
- `init.rc`: `panic_on_oops` 从 1 改成 0
- `init.zxic.rc`: `zte_post_boot` 服务从 `class main` 改成 `class core`
- 添加 `/system/etc/init.zte.post_boot.sh` 开机脚本
- 内核二进制补丁：4 处 `bl in_egroup_p` → `movz w0, #1`

### 内核补丁

绕过 Android 的 `CONFIG_ANDROID_PARANOID_NETWORK` 检查，使所有进程无需 GID 3003/3004 即可创建网络 socket。

| 地址 | GID | 函数 | 补丁 |
|------|-----|------|------|
| 0x5c9210 | 3003 (AID_INET) | `current_has_network()` 1 | ✅ |
| 0x6107ec | 3003 (AID_INET) | `current_has_network()` 2 | ✅ |
| 0x23ec2c | 3004 (AID_NET_RAW) | `current_has_network_admin()` | ✅ |
| 0x23ec50 | 3005 (AID_NET_ADMIN) | `current_has_network_admin()` 2 | ✅ |

详见 `docs/15_Android内核二进制补丁绕过PARANOID_NETWORK.md`。

### 开机脚本功能
```sh
#!/system/bin/sh
# ZRAM Swap
mknod /dev/zram0 b 254 0
echo 536870912 > /sys/block/zram0/disksize
mkswap /dev/zram0 && swapon /dev/zram0

# 网络
insmod /system/lib/modules/8189fs.ko
wpa_supplicant -Dnl80211 -iwlan0 -c /system/etc/wpa_supplicant.conf -B
ifconfig wlan0 up
dhcpcd wlan0

# 远程访问
/sbin/adbd &
/usr/sbin/sshd
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
