# ZTE B860AV1.1-T2 完整探索记录

## 设备信息

| 项目 | 参数 |
|------|------|
| 型号 | ZTE B860AV1.1-T2 |
| SoC | ZX296716 (ARM Cortex-A53, 4核) |
| RAM | 990MB (CMA 336MB → 修改后 20MB) |
| 存储 | 8GB eMMC |
| 系统 | Android 4.4.2 (API 19) |
| 串口 | /dev/ttyUSB0, 115200 baud |
| Root 密码 | 123456 |

---

## 阶段一：初始探索

### 1.1 串口连接

```bash
screen /dev/ttyUSB0 115200
```

退出 screen：`Ctrl+A` → `K` → `Y`

### 1.2 设备分区表

| 分区 | 设备 | 大小 | 用途 |
|------|------|------|------|
| p1 | mmcblk0p1 | 4MB | 未知 |
| p2 | mmcblk0p2 | 64MB | 未知 |
| p3 | mmcblk0p3 | 4MB | conf（配置分区） |
| p4 | mmcblk0p4 | 768MB | cache |
| p5 | mmcblk0p5 | 8MB | env |
| p6 | mmcblk0p6 | 32MB | 未知 |
| p7 | mmcblk0p7 | 32MB | 未知 |
| p8 | mmcblk0p8 | 8MB | 未知 |
| p9 | mmcblk0p9 | 8MB | 未知 |
| p10 | mmcblk0p10 | 32MB | boot |
| p11 | mmcblk0p11 | 32MB | 未知 |
| p12 | mmcblk0p12 | 32MB | 未知 |
| p13 | mmcblk0p13 | 1GB | system |
| p14 | mmcblk0p14 | 5.2GB | data |

### 1.3 Boot.img 结构

```
偏移        大小        内容
0x0000      96B         ZTE header (magic: 55667788)
0x0060      64B         ANDROID! header
0x0800      11.3MB      Kernel (ARM64)
0xB0C060    1.27MB      Ramdisk (gzip)
0xC439A0    32KB        DTB 0 (设备树)
0xC4B9A0    32KB        DTB 1
0xC539A0    32KB        DTB 2
```

### 1.4 内核启动参数

```
root=/dev/ram0 rw initrd=0x41000000,0x1373e9
boardtype=0x13 console=ttyS0,115200n8
androidboot.hardware=zxic androidboot.selinux=disabled
WorkMode=0
```

---

## 阶段二：恢复机制探索

### 2.1 发现恢复机制

设备每次修改后重启，所有修改都会被还原。原因：

内核内置了 `set_fs_safe_mode` 驱动，会：
1. 检测 ext4 文件系统错误
2. 递增 conf 分区的 SafeErrCode
3. 当 SafeErrCode >= MonitorFailedNum 时，触发恢复模式
4. 恢复模式会还原 system、boot、data 分区

### 2.2 conf 分区格式

```
设备: /dev/block/conf (mmcblk0p3, 4MB)
格式: INI, append-only, 每条 2048 字节
编码: UTF-16LE + BOM (ff fe)

每条结构:
0x0000  ff fe           (BOM)
0x0002  [System]\n      (UTF-16LE)
        WorkMode=N\n
        SafeErrCode=N\n
        MonitorFailedNum=N\n
        [Common]\n      (可选)
        KeyControlTime=N\n
        00 00 ...       (零填充到 2048 字节)
```

### 2.3 恢复触发流程

```
内核启动
  ↓
set_fs_safe_mode 驱动加载
  ↓
读取 /dev/block/conf
  ↓
检查上次关机是否干净？
  ├─ 干净 → SafeErrCode 不变
  └─ 不干净 → SafeErrCode++
  ↓
SafeErrCode >= MonitorFailedNum ?
  ├─ 否 → 正常启动
  └─ 是 → WorkMode=1 → bootloader 进恢复模式
```

### 2.4 关键发现

- `set_fs_safe_mode` 在**每次 ext4 错误时**都会被调用，不只是启动时
- 即使 fstab 设了 `errors=continue`，驱动仍然在 fstab 处理之前拦截错误
- `/system` 分区默认没有 `errors=continue`
- `panic_on_oops=1` 在 init.rc 中设置

---

## 阶段三：内核二进制 Patch

### 3.1 分析内核

```bash
# 提取内核
dd if=/tmp/ota/boot.img of=/tmp/kernel.bin bs=1 skip=2048 count=11581328

# 安装 ARM64 反汇编工具
sudo apt-get install binutils-aarch64-linux-gnu

# 反汇编
aarch64-linux-gnu-objdump -D -b binary -m aarch64 /tmp/kernel.bin
```

### 3.2 定位 set_fs_safe_mode 函数

通过 strings 找到关键字符串：

```bash
strings -t x /tmp/ota/boot.img | grep "set_fs_safe_mode"
# 93c291: "goto set_fs_safe_mode"
# 9923d8: "[set_fs_safe_mode  %d]"
# 992780: "ALERT:File system panic, system will enter safemode..."
# 9927b9: "Restarting system from safe_mode."
```

### 3.3 查找 ADRP 引用

编写 Python 脚本扫描内核中引用这些字符串地址的 ADRP+ADD 指令对：

```python
# /tmp/find_adrp.py
# 扫描 ARM64 ADRP 指令，找到引用目标页面的代码位置
```

找到关键函数位置：
- `0x4798E0`: ALERT 处理函数
- `0x47991C`: set_fs_safe_mode 主函数

### 3.4 Patch 内核

```python
# /tmp/patch_kernel.py
import struct

RET = 0xD65F03C0      # ARM64 RET 指令
NOP = 0xD503201F      # ARM64 NOP 指令

# 三个 patch 点：
# 1. 0x47A0E0: ALERT 处理函数入口 → RET
# 2. 0x47A110: 调用 panic/restart → NOP
# 3. 0x47A11C: set_fs_safe_mode 函数入口 → RET
```

### 3.5 验证

刷入 patched boot.img 后：
- 删除 framework JAR → 系统不重启
- 删除所有 APK → 系统不重启
- 等待 3 分钟 → 系统稳定运行

---

## 阶段四：系统裁剪

### 4.1 APK 清理

```bash
rm -rf /system/app/*.apk
rm -rf /system/priv-app/*.apk
rm -rf /system/preinstall/*.apk
rm -rf /system/framework/*.jar
rm -rf /system/framework/*.apk
```

### 4.2 二进制清理

安全删除的 Android 框架二进制：

```bash
rm -rf /system/bin/surfaceflinger /system/bin/drmserver /system/bin/installd
rm -rf /system/bin/keystore /system/bin/keystore_cli /system/bin/bootanimation
rm -rf /system/bin/debuggerd /system/bin/media /system/bin/mediaserver
rm -rf /system/bin/sensorservice /system/bin/uiautomator /system/bin/monkey
rm -rf /system/bin/screencap /system/bin/screenrecord /system/bin/screenshot
rm -rf /system/bin/dumpsys /system/bin/dumpstate /system/bin/gdbserver
rm -rf /system/bin/dalvikvm /system/bin/dex2oat /system/bin/dexopt
rm -rf /system/bin/ime /system/bin/input /system/bin/wm /system/bin/am
rm -rf /system/bin/pm /system/bin/settings /system/bin/service /system/bin/svc
rm -rf /system/bin/sm /system/bin/content /system/bin/bmgr /system/bin/bu
rm -rf /system/bin/logcat /system/bin/logwrapper /system/bin/atrace /system/bin/bugreport
rm -rf /system/bin/cobshell /system/bin/controlHgProcess
rm -rf /system/bin/hgAgent /system/bin/hgAgentTcp
rm -rf /system/bin/zte_probe /system/bin/zte_probe_monitor
rm -rf /system/bin/MainCenter /system/bin/ServiceMonitor /system/bin/FactoryTestTool_C
rm -rf /system/bin/airplayserver /system/bin/netdiagnose /system/bin/startup_log
rm -rf /system/bin/zte_logo_mk.sh /system/bin/zte_mdnsd /system/bin/zte_middleware.sh
rm -rf /system/bin/zlogcat /system/bin/cp7601.sh
rm -rf /system/bin/mcsp_cfgexport /system/bin/mcsp_cfgimport /system/bin/mcsp_xmlimport
rm -rf /system/bin/mkimg /system/bin/mkmd5 /system/bin/mklogo
rm -rf /system/bin/corrupt_gdt_free_blocks /system/bin/set_ext4_err_bit
rm -rf /system/bin/property_set_recovery_ver
rm -rf /system/bin/init.zte.post_boot.sh /system/bin/preinstall.sh
rm -rf /system/bin/showlease /system/bin/setup_fs /system/bin/monitor_e2fs
rm -rf /system/bin/wirelesskey /system/bin/netaccess /system/bin/depconfig
rm -rf /system/bin/watchprops /system/bin/wipe /system/bin/zip
rm -rf /system/bin/pngtest /system/bin/oatdump /system/bin/radiooptions
rm -rf /system/bin/mtpd /system/bin/racoon /system/bin/garp
rm -rf /system/bin/requestsync /system/bin/smd /system/bin/notify
```

### 4.3 资源清理

```bash
rm -rf /system/fonts/*
rm -rf /system/media/*
rm -rf /system/lib/drm /system/lib/egl /system/lib/soundfx
rm -rf /system/lib/libclcore*.bc
rm -rf /system/lib/hw/audio.*.so /system/lib/hw/gralloc.*.so
rm -rf /system/lib/hw/tvout.*.so /system/lib/hw/keystore.*.so
rm -rf /system/lib/hw/ca /system/lib/hw/power.*.so
rm -rf /system/lib/modules/dwc2.ko
```

### 4.4 配置清理

```bash
rm -rf /system/etc/appstore.ini /system/etc/BannedKillBackgroundProcessesWhiteList.ini
rm -rf /system/etc/LegalPackagesForDIMS.ini /system/etc/MV3Plugin.ini
rm -rf /system/etc/notUploadPackageList.ini /system/etc/productinfo.ini
rm -rf /system/etc/recovery_install.ini /system/etc/SetFun.txt
rm -rf /system/etc/standardcfg.ini /system/etc/stbconfig_bak
rm -rf /system/etc/stbconfig_clear.ini /system/etc/stbhgagent_config.ini
rm -rf /system/etc/stbname_default*.ini /system/etc/stb_version.inf
rm -rf /system/etc/sw.inf /system/etc/ver.inf /system/etc/middleware_ver.inf
rm -rf /system/etc/vod_tr069_interface.xml /system/etc/lang.cfg
rm -rf /system/etc/simsun.ttc /system/etc/NOTICE.html.gz
rm -rf /system/etc/init.device.add_permission.sh /system/etc/init.insmod_usb.sh
rm -rf /system/etc/init.zte.post_boot.sh /system/etc/install-recovery.sh
rm -rf /system/etc/eth0_ap.sh /system/etc/eth_off.sh
rm -rf /system/etc/ppp* /system/etc/pppoe*
rm -rf /system/etc/system_fonts.xml /system/etc/fallback_fonts.xml
rm -rf /system/etc/media_codecs.xml /system/etc/audio_effects.conf
rm -rf /system/etc/audio_policy.conf /system/etc/wpa_supplicant_psk.conf
rm -rf /system/etc/zd1211.conf /system/etc/fw_env.config
```

### 4.5 保留的关键文件

**必须保留的二进制：**
- `sh` — shell
- `toolbox` — 基本命令提供者
- `servicemanager` — IPC
- `adbd` — ADB
- `busybox` — 基本工具
- `daemonsu` — root
- `mount` / `umount` / `reboot`
- `setprop` / `getprop` / `start` / `stop`
- `insmod` / `rmmod` / `lsmod`
- `ifconfig` / `route` / `netcfg` / `netd`
- `dhcpcd` / `wpa_supplicant` / `wpa_cli`
- `ip` / `iptables` / `ip6tables`
- `ping` / `netstat` / `iftop` / `iperf`
- `e2fsck` / `mkswap`
- `ps` / `df` / `ls` / `cat` / `echo` / `rm` / `mkdir`
- `chmod` / `chown` / `sleep` / `sync` / `top` / `touch`
- `uptime` / `vdc` / `vmstat`

**必须保留的库：**
- `/system/lib/*.so` — 全部保留！
- `/system/lib/modules/8189fs.ko` — WiFi 驱动

---

## 阶段五：网络配置

### 5.1 有线网络

```bash
# DHCP
netcfg eth0 dhcp

# 或手动配置
ifconfig eth0 192.168.31.208 netmask 255.255.255.0 up
route add default gw 192.168.31.1
echo "nameserver 8.8.8.8" > /etc/resolv.conf
```

### 5.2 WiFi

```bash
# 加载驱动
insmod /system/lib/modules/8189fs.ko

# 创建配置
echo 'ctrl_interface=/data/misc/wifi/wpa_supplicant
network={ssid="Xiaomi_F5A3" psk="123456789" key_mgmt=WPA-PSK}' > /data/wpa.conf

# 连接
wpa_supplicant -Dnl80211 -iwlan0 -c/data/wpa.conf -B
dhcpcd wlan0
```

---

## 阶段六：OTA 分析

### 6.1 OTA 结构

```
/tmp/ota.zip (258MB)
├── META-INF/
│   ├── CERT.RSA           (签名)
│   ├── CERT.SF            (签名文件)
│   ├── MANIFEST.MF        (清单)
│   └── com/google/android/
│       ├── update-binary   (ARM ELF)
│       └── updater-script  (脚本)
├── boot.img               (内核+ramdisk+DTB)
├── bootloader.img         (U-boot)
├── recovery/recovery.img  (恢复模式)
└── system/                (系统文件)
```

### 6.2 updater-script 关键操作

```
format("ext4", "EMMC", "/dev/block/system", "0", "/system")
mount("ext4", "EMMC", "/dev/block/system", "/system")
package_extract_dir("system", "/system")
package_extract_file("boot.img", "/dev/block/boot")
package_extract_file("bootloader.img", "/dev/block/mmcblk0boot0")
```

### 6.3 签名验证

OTA 使用 JAR 签名格式：
- `MANIFEST.MF`: 每个文件的 SHA-256 + SHA-1 摘要
- `CERT.SF`: MANIFEST.MF 的 SHA-256 摘要
- `CERT.RSA`: 对 CERT.SF 的 PKCS#7 签名 (DER)

原始签名者：CN=laoli (自签名证书)

---

## 阶段七：init.rc 钩子分析

### 7.1 启动链

```
内核 → init → 读取 rc 文件
  → on early-init → start ueventd
  → on init → 创建目录、挂载 cgroup
  → on fs → mount_all /fstab.zxic
  → on post-fs → 挂载 rootfs 只读
  → on post-fs-data → 创建 /data 下目录
  → on boot → class_start core、网络配置
  → on nonencrypted → class_start late_start
```

### 7.2 属性触发器

| 属性 | 触发动作 |
|------|----------|
| `sys.boot_completed=1` | start preinstall |
| `sys.zte.sshd=start` | start ssh_start |
| `sys.zte.sshd=stop` | start ssh_stop |
| `sys.evtmanager.started=1` | start middwareShell |
| `wifi.ap=1` | start seteth0ap |
| `sys.zte.cleanData=1` | start zte-clean-data |
| `config.StartupLog=1` | start StartupLog |
| `sys.powerctl=*` | powerctl |

### 7.3 服务 onrestart 链

```
servicemanager 崩溃 → restart healthd, zygote, media, surfaceflinger, drm
surfaceflinger 崩溃 → restart zygote
zygote 崩溃 → restart media, netd
```

### 7.4 class 分组

| class | 启动时机 | 包含服务 |
|-------|----------|----------|
| core | on boot | ueventd, healthd, adbd, servicemanager, vold |
| main | class_start main | netd, surfaceflinger, zygote, media 等 |
| late_start | on nonencrypted | sdcard, ethernet |

---

## 阶段八：关键教训

### 8.1 绝对不能删的

- `/system/lib/*.so` — 所有动态链接库
- `servicemanager` — IPC 核心
- `toolbox` — 提供基本命令
- `sh` — shell
- `mount` / `umount` — 文件系统挂载

### 8.2 安全删除的原则

1. **先用 echo 测试**：`echo /system/bin/target*` 确认文件存在
2. **分批删除**：每次删几个，重启验证
3. **保留 .so 库**：宁可多留，不能删错
4. **备份 conf 分区**：修改前先 `dd if=/dev/block/conf of=/sdcard/conf_backup.bin`

### 8.3 恢复方法

如果系统无法启动：
1. 进 u-boot（串口按任意键）
2. `bootsys` 正常启动
3. 或 `safe` 进恢复模式
4. 通过 U 盘刷原版 OTA 恢复

---

## 阶段九：最终状态

### 9.1 系统概况

```
/system/         ~227MB 已用，764MB 空闲
  /bin/          116 个 Linux 基础工具
  /lib/          351 个 .so 库
  /xbin/         280 个（busybox 符号链接）
  /etc/          精简后的配置
  /fonts/        空
  /media/        空
/data/           ~5GB 可用（用于 Linux rootfs）
```

### 9.2 运行中的进程

```
servicemanager  — IPC（必须）
vold            — 存储管理
adbd            — ADB 远程访问
daemonsu        — root 权限
busybox         — 基本工具
sh              — shell
```

### 9.3 内核 Patch

三个 patch 点，彻底禁用 `set_fs_safe_mode`：
- `0x47A0E0`: ALERT 处理函数 → RET
- `0x47A110`: panic/restart 调用 → NOP
- `0x47A11C`: set_fs_safe_mode 函数 → RET

---

## 阶段十：下一步计划

### 10.1 安装 Alpine Linux (chroot)

```bash
# 下载 rootfs
wget https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/armhf/alpine-minirootfs-3.19.1-armhf.tar.gz

# 传到设备
mkdir -p /data/alpine
tar -xzf alpine-minirootfs-3.19.1-armhf.tar.gz -C /data/alpine

# 挂载
mount -t proc proc /data/alpine/proc
mount -t sysfs sysfs /data/alpine/sys
mount -o bind /dev /data/alpine/dev

# 进入 chroot
chroot /data/alpine /bin/sh

# 初始化
apk update
apk add bash openssh vim
```

### 10.2 开机自动启动

创建 `/system/bin/start_linux.sh`：

```bash
#!/system/bin/sh
mount -t proc proc /data/alpine/proc
mount -t sysfs sysfs /data/alpine/sys
mount -o bind /dev /data/alpine/dev
mount -o bind /dev/pts /data/alpine/dev/pts
chroot /data/alpine /usr/sbin/sshd
```

---

## 附录：关键文件位置

| 文件 | 位置 | 用途 |
|------|------|------|
| 原始 boot.img | `/tmp/ota/boot.img` | 原始内核 |
| Patched boot.img | `/tmp/boot_cma16_patched.bin` | 内核 patch + CMA 修改 |
| conf 分区镜像 | `/tmp/conf_fixed.bin` | MonitorFailedNum=255 |
| OTA 包 | `/tmp/ota.zip` | 原始 OTA |
| 提取的 ramdisk | `/tmp/boot_plan/ramdisk/` | ramdisk 文件 |
| 内核二进制 | `/tmp/kernel.bin` | 提取的内核 |
| ADRP 扫描脚本 | `/tmp/find_adrp.py` | 查找内核函数 |
| 内核 Patch 脚本 | `/tmp/patch_kernel.py` | 二进制 patch |
| conf 生成脚本 | `/tmp/build_conf.py` | 生成 conf 分区 |

---

## 附录：常用命令

```bash
# 串口连接
screen /dev/ttyUSB0 115200

# 查看分区
ls -l /dev/block/

# 查看空间
df /system

# 查看进程
ps

# 设置属性
setprop sys.boot_completed 1

# 查看属性
getprop sys.boot_completed

# 加载内核模块
insmod /system/lib/modules/8189fs.ko

# 网络配置
netcfg eth0 dhcp
ifconfig eth0 192.168.31.208 netmask 255.255.255.0 up
route add default gw 192.168.31.1

# 查看 conf 分区
hexdump -C /dev/block/conf | tail -20

# 备份 boot
dd if=/dev/block/boot of=/sdcard/boot_backup.bin bs=4096

# 刷入 boot
dd if=/sdcard/boot_patched.bin of=/dev/block/boot bs=4096 conv=fsync
```

---

*文档完成时间：2026年7月25日*
*设备：ZTE B860AV1.1-T2 (ZX296716)*
