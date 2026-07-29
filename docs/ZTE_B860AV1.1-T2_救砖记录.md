# ZTE B860AV1.1-T2 救砖记录

## 设备信息
- **型号**: ZTE B860AV1.1-T2 (中兴机顶盒)
- **芯片**: ZX296716 (中兴微)
- **系统**: Android 4.4.2 (KitKat)
- **内存**: 1GB RAM
- **存储**: 4GB eMMC

## 起因
在 Debian chroot 环境中误删了 `/system/lib/` 下的关键 .so 文件：
- `libc.so`
- `libcrypto.so`
- `libcorkscrew.so`
- `libbinder.so`
- `libkeystore_binder.so`

导致设备 boot loop，无法进入 Android。

## 尝试的恢复方法（均失败）

### 1. TFTP 传输 system.img
- 创建了 500MB raw ext4 镜像
- TFTP 传输成功（524288000 字节）
- `mmc write` 失败：扇区计算错误（用了 0x8F0000，正确应为 0x23C000）

### 2. 修复 cache 分区
- 尝试清除损坏的 cache 分区（errors=panic 导致 kernel hang）
- `mmc erase` 命令在 U-Boot 中不可用

### 3. BCB (Bootloader Control Block) 方案
- 计划写入 misc 分区让 recovery 自动刷机
- 未实施（recovery 30秒超时问题未解决）

### 4. 自制 system 镜像
- 从 OTA 包提取 system 文件（386MB）
- 创建 500MB ext4 镜像
- 权限问题：原始文件缺少执行权限（664 而非 755）
- 手动设置权限后，仍无法确认能否启动

## 最终解决方案：U-Boot `upgrade` 命令

### 关键发现
通过分析 `/tmp/version/u-boot.bin` 的字符串，发现 U-Boot 内置 `upgrade` 命令：

```
upgrade - burn image into disk
upgrade <partition name> - upgrade specific partition
```

### 所需文件
- `B860AV2.2-all.img`（313MB，EMMC Compressed format）
- 包含完整固件：bootloader + recovery + system + cache + data

### 操作步骤

#### 1. 准备 TFTP 服务器（工作站）
```bash
sudo mkdir -p /tmp/tftp_test
sudo cp /tmp/version/B860AV2.2-all.img /tmp/tftp_test/all.img
sudo chmod 755 /tmp/tftp_test/all.img
sudo in.tftpd -l -s /tmp/tftp_test -a 0.0.0.0:69 -t 30
```

**重要**：文件必须命名为 `all.img`，U-Boot 会自动下载这个文件名。

#### 2. U-Boot 中执行
```
setenv ipaddr 192.168.0.22
setenv serverip 192.168.0.189
upgrade all
```

**注意**：不需要先 `tftp` 传文件！`upgrade all` 会自动从 TFTP 下载 `all.img`。

#### 3. 等待刷写完成
U-Boot 会：
1. 自动 TFTP 下载 `all.img`（313MB）
2. 解压 EMMC Compressed format
3. 擦除 data 和 cache 分区
4. 写入所有 27 个分区
5. 显示 `all image upgrade ok!`

#### 4. 重启
```
reset
```

## 关键知识点

### eMMC 分区表
```
 0: all                 0                       100000000               1
 1: bootloader          0                       400000                  1
 2: reserved            2400000                 4000000                 1
 3: conf                6c00000                 400000                  1
 4: cache               7800000                 30000000                2
 5: env                 38000000                800000                  1
 6: logo                39000000                2000000                 1
 7: recovery            3b800000                2000000                 1
 8: rsv                 3e000000                800000                  1
 9: tee                 3f000000                800000                  1
10: crypt               40000000                2000000                 1
11: misc                42800000                2000000                 1
12: boot                45000000                2000000                 1
13: system              47800000                40000000                1
14: data                88000000                61000000                4
```

### system 分区
- **偏移**: 0x47800000 字节
- **起始扇区**: 0x23C000 (2342912)
- **大小**: 0x40000000 字节 (1GB)
- **文件系统**: ext4

### U-Boot 网络配置
- **设备 IP**: 192.168.0.22
- **服务器 IP**: 192.168.0.189（工作站 WiFi 地址）
- **TFTP 文件名**: `all.img`（必须用这个名字）

### boot.img 结构
- **ZTE 头部**: 0x00-0x5F（magic: `Ufw.norm`）
- **Android bootimg**: 从 0x60 开始（magic: `ANDROID!`）
- **内核偏移**: 0x860
- **ramdisk 偏移**: 0xB0C060
- **页面大小**: 2048 (0x800)

### recovery.img 功能
- **恢复出厂**: wipe data + 从 OTA 刷机
- **OTA 更新**: 从 `/cache/upgrade/` 或 `/data/ztebackup/ota.zip`
- **超时重启**: 30秒无操作自动重启
- **BCB 命令**: 从 `/misc` 分区读取 `boot-recovery` 指令

## 踩过的坑

1. **扇区计算错误**: `0x47800000 / 512 = 0x23C000`，不是 `0x8F0000`
2. **TFTP 文件名**: `upgrade all` 自动找 `all.img`，不用先手动 tftp
3. **权限问题**: 从 eMMC 复制的文件会丢失执行权限（664 → 需要 755）
4. **cache 分区损坏**: ext4 `errors=panic` 导致 kernel hang
5. **USB 烧录**: 设备不识别 USB（XProb_V2.1 工具无法使用）

## 相关文件位置
- **固件包**: `/tmp/version/B860AV2.2-all.img`
- **OTA 包**: `/tmp/ota/`（415MB，含 system/ + boot.img）
- **boot.img**: `/tmp/boot.img`（ZTE 格式）
- **recovery.img**: `/tmp/recovery.img`
- **系统备份**: `/tmp/system/`（386MB，权限已修复）
- **TFTP 目录**: `/tmp/tftp_test/`

## 系统精简（转无头服务器）

### 目标
去掉 Android 框架，只保留 Linux 核心 + 网络 + 驱动，作为无头服务器使用。

### 删除的内容
- **Android 服务**: surfaceflinger, servicemanager, mediaserver, installd, keystore, vold, netd, debuggerd, zygote, drm, media, bootanim 等
- **Android 框架库**: libandroid_runtime.so, libbinder.so, libcamera*.so, libhwui.so, libskia.so, libstagefright*.so, libsurfaceflinger*.so 等（约 88 个 .so）
- **Android 配置**: media_codecs.xml, audio_policy.conf, fonts, recovery-resource.dat 等
- **ZTE 运营商定制**: libCMCC_*.so, libCTC_*.so, libzteplayer.so, libzxic_stbmc.so 等

### 保留的内容
- **C 运行库**: libc.so, libm.so, libdl.so, libstdc++.so
- **网络工具**: ip, iptables, wpa_supplicant, dhcpcd, hostapd
- **系统命令**: busybox (273 个命令), mksh, sh
- **硬件驱动**: 8189fs.ko (WiFi), mali.ko (GPU)
- **内核模块**: /system/lib/modules/8189fs.ko

### 最终状态
```
/system  — 991.9M 总空间，173.8M 已用，818.1M 可用
/lib/    — 155 个 .so 库
/bin/    — 146 个命令
/xbin/   — 273 个命令（busybox）
/etc/    — 38 个配置
```

## WiFi 配置

### 驱动
- **芯片**: Realtek RTL8189FS
- **模块**: `/system/lib/modules/8189fs.ko`
- **版本要求**: `vermagic=4.1.18-svn103878`（必须匹配运行内核）
- **注意**: 原始模块是 `4.1.18-b16t22`，不匹配。从 `/tmp/lib/modules/` 获取正确版本。

### wpa_supplicant 配置
文件: `/system/etc/wpa_supplicant.conf`
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

### 依赖库
wpa_supplicant 需要 `libkeystore_binder.so`，删除系统时误删了，需要从备份恢复。

## 开机自启脚本

### 钩子位置
`init.zxic.rc` 中的 `service zte_post_boot`，在 `on post-fs-data` 阶段执行。

### 脚本内容
文件: `/system/etc/init.zte.post_boot.sh`
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

## Boot 镜像修改

### 问题
原始 ramdisk 的 init.rc 引用了大量已删除的 Android 服务，导致：
1. `panic_on_oops=1` 触发 Emergency Remount R/O
2. 系统 10 秒后强制重启
3. 反复失败触发 `bootsys` 的启动失败计数器

### 修改内容
1. **init.rc**: `panic_on_oops` 从 1 改成 0
2. **init.rc**: 去掉 `exec /system/bin/sh /system/etc/boot.sh`
3. **init.zxic.rc**: 在 `on post-fs-data` 里加 `exec /system/bin/sh /system/etc/boot.sh`

### 打包方法
```bash
cd /tmp/analysis/ramdisk
find . | cpio -o -H newc | gzip > /tmp/analysis/new_ramdisk.cpio.gz
python3 /tmp/analysis/rebuild_boot.py
```

### 刷入方法
```bash
# U-Boot 中执行
setenv ipaddr 192.168.0.22
setenv serverip 192.168.0.189
tftp 0x48000000 boot.img
mmc write 0 0x48000000 0x228000 0x62dd
```

## 启动失败计数器问题

### 症状
- 设备一直自动进恢复模式
- 手动选 "normal" 可以正常启动
- 清空 misc 分区无效

### 原因
`bootsys` 命令内部有启动失败计数器，存储在 **conf 分区**（不是 misc 分区）。多次启动失败后，`bootsys` 自动切换到 recovery 分区启动。

### 解决方案
**清空 conf 分区**：
```bash
# U-Boot 中执行
mmc read 0 0x48000000 0x36000 4
mw.l 0x48000000 0 256
mmc write 0 0x48000000 0x36000 4
```

或在 Linux 中：
```bash
dd if=/dev/zero of=/dev/block/conf bs=512 count=2
```

### 关键分区说明
| 分区 | 用途 | 大小 |
|------|------|------|
| misc | BCB 命令（boot-recovery） | 2MB |
| conf | 启动失败计数器 | 4MB |
| env | U-Boot 环境变量 | 8MB |

## 总结

### 救砖方法
用 U-Boot 内置的 `upgrade all` 命令刷官方固件。

### 转无头服务器步骤
1. `upgrade all` 刷固件
2. 删除 Android 框架和 ZTE 定制
3. 恢复 `libkeystore_binder.so`
4. 配置 WiFi（`wpa_supplicant.conf`）
5. 修改 ramdisk（去掉 `panic_on_oops`，调整 `exec` 位置）
6. 刷入新 boot 镜像
7. 清空 conf 分区（重置启动计数器）

### 连接方式
```
串口:    /dev/ttyUSB0 115200
ADB:     adb connect <设备IP>:5555
Telnet:  telnet <设备IP>
```

### 关键教训
1. **conf 分区**存储启动失败计数器，不是 misc
2. **boot 镜像对齐**必须严格按页大小（0x800）
3. **WiFi 模块版本**必须匹配运行内核（`4.1.18-svn103878`）
4. **libkeystore_binder.so** 是 wpa_supplicant 的依赖，不能删
5. **panic_on_oops** 在精简系统时必须设为 0
