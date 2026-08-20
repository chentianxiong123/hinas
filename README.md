# tvbox-linux 机顶盒改造工具集

本仓库包含多个机顶盒设备的改造工具和脚本,涵盖海纳思系统软件包管理、中兴 ZTE B860AV 机顶盒救砖与无头服务器改造等。

---

## 项目列表

### 1. himv3798-100-hinas (海纳思 Hi3798MV100)

海纳思(hinas)系统软件包管理工具，支持一键安装/卸载 FileBrowser、Nginx、Samba、Alist、Aria2、Transmission、Jellyfin、HomeAssistant 等 30+ 款软件。

**设备信息:**
- 处理器: Hi3798MV100
- 系统: 海纳思 (hinas)

**软件包:**
- `hi3798mv100_hinas_wifi.tar.gz` → 从 [Releases] 下载
- `hinas_install_uninstall.sh` — 安装卸载脚本
- `install_hi3798mv100_wifi.sh` — WiFi 安装脚本
- `check_docker_registry.sh` — Docker 镜像检查脚本

### 2. b860av1-t2 (ZTE B860AV1.1-T2)

ZTE B860AV1.1-T2 机顶盒改造项目，通过逆向工程、内核补丁、系统裁剪等技术，将机顶盒改造为专用 Linux 服务器。

**设备信息:**
- 处理器: ZX296716 (ARM Cortex-A53, 64位)
- 内存: 990MB RAM
- 存储: 8GB eMMC
- 系统: Android 4.4.2

**主要功能:**
- ✓ 内核补丁 (禁用 set_fs_safe_mode 和 conf_fs_write)
- ✓ 系统裁剪 (删除 APK、框架、系统库)
- ✓ 网络持久化 (WiFi 驱动自动加载)
- ✓ ADB over TCP 访问

**快速开始:**
```bash
git clone https://github.com/chentianxiong123/tvbox-linux.git
cd tvbox-linux/b860av1-t2
cat README.md
python3 scripts/kernel_analysis.py --help
```

### 3. ZTE B860AV1.1-T2 救砖与改造

ZTE B860AV1.1-T2 机顶盒救砖记录、固件分析和无头服务器改造方案。详见 [b860av1-t2](b860av1-t2/) 目录。

**设备信息:**
- **型号**: ZTE B860AV1.1-T2
- **芯片**: ZX296716 (中兴微)
- **系统**: Android 4.4.2 (KitKat)
- **内存**: 1GB RAM
- **存储**: 4GB eMMC
- **WiFi**: Realtek RTL8189FS

**无头服务器改造内容:**
1. 删除 Android 框架（surfaceflinger, zygote, media 等）
2. 保留 Linux 核心（libc, libm, libdl 等）
3. 配置 WiFi 自动连接
4. 开机自启 SSH
5. 内核补丁绕过 `CONFIG_ANDROID_PARANOID_NETWORK`
6. ZRAM 512MB swap 自动启用

**内核补丁:**
绕过 Android 的 `CONFIG_ANDROID_PARANOID_NETWORK` 检查，使所有进程无需 GID 3003/3004 即可创建网络 socket。

| 地址 | GID | 函数 | 补丁 |
|------|-----|------|------|
| 0x5c9210 | 3003 (AID_INET) | `current_has_network()` 1 | ✅ |
| 0x6107ec | 3003 (AID_INET) | `current_has_network()` 2 | ✅ |
| 0x23ec2c | 3004 (AID_NET_RAW) | `current_has_network_admin()` | ✅ |
| 0x23ec50 | 3005 (AID_NET_ADMIN) | `current_has_network_admin()` 2 | ✅ |

**开机脚本功能:**
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

**分区表:**

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

---

## 目录结构

```
tvbox-linux/
├── README.md                          # 本文件
├── himv3798-100-hinas/                # 海纳思 Hi3798MV100 项目
│   ├── hinas_install_uninstall.sh
│   ├── install_hi3798mv100_wifi.sh
│   ├── check_docker_registry.sh
│   └── ...
├── b860av1-t2/                        # ZTE B860AV1.1-T2 项目
│   ├── README.md
│   ├── scripts/
│   ├── docs/
│   ├── patches/
│   └── device/
│── boot/                              # boot 镜像 (从 Releases 下载)
│── docs/                              # 技术文档
│── tools/                             # 工具脚本
```

## 使用说明

### 海纳思项目
```bash
cd himv3798-100-hinas
./hinas_install_uninstall.sh
./check_docker_registry.sh
```

### ZTE B860 项目
```bash
cd b860av1-t2
cat README.md
python3 scripts/kernel_analysis.py extract boot.img kernel.bin
python3 scripts/patch_kernel.py patch boot.img boot_patched.img
```

## 技术文档

详细技术文档请参阅各项目的 `docs/` 目录:
- `ZTE_B860AV1.1-T2_救砖记录.md` — 完整的救砖和改造记录
- `14_Android_Chroot网络权限解决方案.md` — Chroot 网络权限 GID 方案
- `15_Android内核二进制补丁绕过PARANOID_NETWORK.md` — 内核二进制补丁方案
- `16_为什么64位内核跑32位用户态.md` — 64位内核兼容性分析
- `17_ZX296716硬件映射与主线内核评估.md` — 硬件映射文档
- `18_ZX296716驱动开发寄存器手册.md` — 驱动寄存器手册

## 许可证

本项目仅供学习和研究使用。

## 联系方式

如有问题或建议，请通过 GitHub Issues 联系。