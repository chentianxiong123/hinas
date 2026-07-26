# ZTE B860AV1.1-T2 机顶盒改造项目

## 项目概述

将 ZTE B860AV1.1-T2 机顶盒改造为专用 Linux 服务器，通过逆向工程、内核补丁、系统裁剪等技术，实现了 Android 框架的禁用和系统资源的优化。

## 设备信息

```
设备型号: ZTE B860AV1.1-T2
处理器: ZX296716 (ARM Cortex-A53, 64位)
内存: 990MB RAM
存储: 8GB eMMC
系统: Android 4.4.2
网络: WiFi (RTL8189FS) + 有线以太网
```

## 目录结构

```
b860av1-t2/
├── README.md                    # 本文件
├── scripts/                     # 脚本目录
│   ├── kernel_analysis.py       # 内核分析脚本
│   └── patch_kernel.py          # 内核补丁脚本
├── docs/                        # 文档目录
│   ├── 09_ZTE_Boot_Image_逆向工程.md
│   ├── 10_ARM64_内核逆向与Patch技术.md
│   ├── 11_Android_系统裁剪与优化.md
│   ├── 12_网络持久化与启动脚本.md
│   ├── 13_完整工作流程与原理.md
│   └── ...
├── patches/                     # 补丁目录
│   ├── original/                # 原始 boot 镜像
│   │   └── boot_cma16_patched.bin
│   └── patched/                 # 补丁后的 boot 镜像
│       └── boot_cma16_patched_v3.bin
└── device/                      # 设备脚本
    ├── eth0.sh                  # 网络初始化脚本
    ├── install-recovery.sh      # 主初始化脚本
    └── wpa.conf                 # WiFi 配置文件
```

## 快速开始

### 1. 内核分析

```bash
# 提取内核
python3 scripts/kernel_analysis.py extract boot.img kernel.bin

# 查找字符串
python3 scripts/kernel_analysis.py strings kernel.bin "set_fs_safe_mode"

# 分析字符串引用
python3 scripts/kernel_analysis.py analyze kernel.bin 0x991d40
```

### 2. 内核补丁

```bash
# 应用补丁
python3 scripts/patch_kernel.py patch boot.img boot_patched.img

# 验证补丁
python3 scripts/patch_kernel.py verify boot_patched.img

# 验证文件完整性
python3 scripts/patch_kernel.py md5 boot_patched.img <expected_md5>
```

### 3. 刷入设备

```bash
# 推送文件到设备
adb push patches/patched/boot_cma16_patched_v3.bin /tmp/

# 刷入 boot 分区
adb shell "dd if=/tmp/boot_cma16_patched_v3.bin of=/dev/block/boot bs=4096"

# 验证刷入
adb shell "dd if=/dev/block/boot bs=12959159 count=1 | md5sum"

# 重启设备
adb reboot
```

### 4. 配置网络

```bash
# 推送脚本到设备
adb push device/eth0.sh /system/etc/
adb push device/install-recovery.sh /system/etc/
adb push device/wpa.conf /data/

# 设置权限
adb shell "chmod 755 /system/etc/eth0.sh"
adb shell "chmod 755 /system/etc/install-recovery.sh"

# 重启设备
adb reboot
```

## 补丁说明

### 补丁列表

| 偏移 | 描述 | 原始值 | 补丁值 |
|------|------|--------|--------|
| 0x4798E0 | 诊断函数 | ADRP | RET |
| 0x479910 | conf 写入调用 | BL | NOP |
| 0x47991C | set_fs_safe_mode | STP | RET |
| 0x478E70 | conf_fs_write | STP | RET |

### 补丁原理

**RET 指令:** `0xD65F03C0` - 返回到 X30 (链接寄存器)

**NOP 指令:** `0xD503201F` - 空操作

**函数禁用:** 替换函数序言为 RET 指令，使函数立即返回

## 系统状态

### 验证补丁

```bash
# 检查内核补丁
adb shell "dd if=/dev/block/boot bs=12959159 count=1 | md5sum"
# 应该返回: aeecc771612ac4c4ec22ac0d188d6d27

# 检查 conf 分区
adb shell "strings /dev/block/conf | grep MonitorFailedNum"
# 应该看到稳定的值，不再增加

# 检查 WiFi 连接
adb shell "ifconfig wlan0"
adb shell "ping -c 1 8.8.8.8"

# 检查 ADB 连接
adb shell "getprop service.adb.tcp.port"
```

### 系统信息

```bash
# 查看系统状态
adb shell "uptime"
adb shell "free"
adb shell "df -h"

# 查看网络状态
adb shell "ifconfig"
adb shell "route -n"

# 查看进程状态
adb shell "ps | grep wpa_supplicant"
```

## 故障排除

### 常见问题

**问题 1: 设备无法启动**
- 原因: boot.img 损坏
- 解决: 使用 OTA 恢复

**问题 2: WiFi 无法连接**
- 原因: 驱动未加载或配置错误
- 解决: 手动加载驱动并检查配置

**问题 3: ADB 无法连接**
- 原因: ADB over TCP 未启用
- 解决: 通过串口启用 ADB

**问题 4: conf 分区仍在写入**
- 原因: 补丁未生效
- 解决: 重新刷入 boot.img

### 恢复方法

```bash
# 使用 OTA 恢复
adb shell "dd if=/cache/upgrade/ota.zip of=/dev/block/boot bs=4096"

# 使用 fastboot
fastboot flash boot boot.img
```

## 技术文档

详细技术文档请参阅 `docs/` 目录：

- [ZTE Boot Image 逆向工程](docs/09_ZTE_Boot_Image_逆向工程.md)
- [ARM64 内核逆向与 Patch 技术](docs/10_ARM64_内核逆向与Patch技术.md)
- [Android 系统裁剪与优化](docs/11_Android_系统裁剪与优化.md)
- [网络持久化与启动脚本](docs/12_网络持久化与启动脚本.md)
- [完整工作流程与原理](docs/13_完整工作流程与原理.md)

## 后续计划

- [ ] Alpine Linux 迁移
- [ ] 系统优化
- [ ] 功能扩展
- [ ] 性能测试

## 许可证

本项目仅供学习和研究使用。

## 联系方式

如有问题或建议，请通过 GitHub Issues 联系。
