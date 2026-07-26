# ZTE B860AV1.1-T2 机顶盒改造项目文档

## 项目概述

本项目将 ZTE B860AV1.1-T2 机顶盒改造为专用 Linux 服务器，通过逆向工程、内核补丁、系统裁剪等技术，实现了 Android 框架的禁用和系统资源的优化。

## 设备信息

```
设备型号: ZTE B860AV1.1-T2
处理器: ZX296716 (ARM Cortex-A53, 64位)
内存: 990MB RAM
存储: 8GB eMMC
系统: Android 4.4.2
网络: WiFi (RTL8189FS) + 有线以太网
```

## 文档目录

### 基础文档 (01-08)

| 文档 | 描述 | 状态 |
|------|------|------|
| 01_初始探索与串口连接.md | 串口连接和初始探索 | ✓ |
| 02_恢复机制探索与破解.md | 恢复模式分析和破解 | ✓ |
| 03_内核二进制分析与Patch.md | 内核逆向和补丁技术 | ✓ |
| 04_系统裁剪.md | Android 系统裁剪 | ✓ |
| 05_OTA分析与签名.md | OTA 包分析和签名 | ✓ |
| 06_init_rc钩子与启动流程.md | init.rc 分析和钩子 | ✓ |
| 07_关键教训与踩坑记录.md | 经验教训和问题解决 | ✓ |
| 08_下一步计划与Alpine_Linux.md | Alpine Linux 迁移计划 | ✓ |

### 高级文档 (09-13)

| 文档 | 描述 | 状态 |
|------|------|------|
| 09_ZTE_Boot_Image_逆向工程.md | ZTE boot.img 格式分析 | ✓ |
| 10_ARM64_内核逆向与Patch技术.md | ARM64 内核分析和补丁 | ✓ |
| 11_Android_系统裁剪与优化.md | 系统裁剪和优化技术 | ✓ |
| 12_网络持久化与启动脚本.md | 网络配置和脚本持久化 | ✓ |
| 13_完整工作流程与原理.md | 完整工作流程和原理 | ✓ |

### 参考文档

| 文档 | 描述 | 状态 |
|------|------|------|
| 01_hardware_and_partitions.md | 硬件和分区信息 | ✓ |
| 02_wifi_driver_debugging.md | WiFi 驱动调试 | ✓ |
| 03_ssh_setup.md | SSH 配置 | ✓ |
| 04_android_service_stripping.md | Android 服务裁剪 | ✓ |
| 05_boot_img_and_dtb.md | boot.img 和 DTB 分析 | ✓ |
| 06_uboot_bootargs_exploration.md | U-Boot 启动参数 | ✓ |
| 07_init_rc_modification.md | init.rc 修改 | ✓ |
| 08_tftp_and_recovery.md | TFTP 和恢复模式 | ✓ |
| 09_summary.md | 项目总结 | ✓ |
| ZTE_B860AV1_T2_完整探索记录.md | 完整探索记录 | ✓ |

## 技术成果

### 已实现功能

1. **内核补丁** - 成功禁用 set_fs_safe_mode 和 conf_fs_write
2. **系统裁剪** - 删除所有 APK、框架、系统库
3. **服务禁用** - 禁用 zygote、media 等服务
4. **网络持久化** - WiFi 驱动自动加载，自动连接
5. **ADB 访问** - 启用 ADB over TCP

### 关键补丁

```
补丁 1: 0x4798E0 - 诊断函数 RET (0xD65F03C0)
补丁 2: 0x479910 - conf 写入调用 NOP (0xD503201F)
补丁 3: 0x47991C - set_fs_safe_mode RET (0xD65F03C0)
补丁 4: 0x478E70 - conf_fs_write RET (0xD65F03C0)
```

### 系统状态

```
Boot MD5: aeecc771612ac4c4ec22ac0d188d6d27
WiFi 状态: 已连接 (Xiaomi_F5A3)
设备 IP: 192.168.31.209
ADB 端口: 5555
MonitorFailedNum: 稳定 (不再增加)
```

## 使用方法

### 快速开始

```bash
# 1. 连接设备
adb connect 192.168.31.209:5555

# 2. 检查状态
adb shell "lsmod | grep 8189"
adb shell "ping -c 1 8.8.8.8"

# 3. 查看系统信息
adb shell "uptime"
adb shell "free"
adb shell "df -h"
```

### 刷入 boot.img

```bash
# 1. 推送文件
adb push boot_cma16_patched_v3.bin /tmp/

# 2. 刷入 boot 分区
adb shell "dd if=/tmp/boot_cma16_patched_v3.bin of=/dev/block/boot bs=4096"

# 3. 验证刷入
adb shell "dd if=/dev/block/boot bs=12959159 count=1 | md5sum"

# 4. 重启设备
adb reboot
```

### 创建网络脚本

```bash
# 创建 eth0.sh
adb shell "cat > /system/etc/eth0.sh << 'EOF'
#!/system/bin/sh
insmod /system/lib/modules/8189fs.ko
sleep 2
wpa_supplicant -B -iwlan0 -c /data/wpa.conf
sleep 3
dhcpcd wlan0
EOF"

# 设置权限
adb shell "chmod 755 /system/etc/eth0.sh"

# 更新 install-recovery.sh
adb shell "cat > /system/etc/install-recovery.sh << 'EOF'
#!/system/bin/sh
/system/etc/eth0.sh
EOF"

# 设置权限
adb shell "chmod 755 /system/etc/install-recovery.sh"
```

## 技术原理

### ARM64 指令

```
RET:  0xD65F03C0 - 返回到 X30
NOP:  0xD503201F - 空操作
STP:  保存寄存器对
LDP:  加载寄存器对
ADRP: 加载页面地址
BL:   调用子程序
```

### 补丁原理

1. **函数禁用** - 替换函数序言为 RET 指令
2. **调用禁用** - 替换 BL 调用为 NOP 指令
3. **逻辑修改** - 修改条件跳转或数据

### 启动流程

```
Bootloader → Linux 内核 → init 进程 → 服务启动 → 用户空间
```

## 故障排除

### 常见问题

**问题 1: 设备无法启动**
- 解决: 使用 OTA 恢复

**问题 2: WiFi 无法连接**
- 解决: 手动加载驱动并检查配置

**问题 3: ADB 无法连接**
- 解决: 通过串口启用 ADB

**问题 4: conf 分区仍在写入**
- 解决: 重新刷入 boot.img

### 恢复方法

```bash
# 使用 OTA 恢复
adb shell "dd if=/cache/upgrade/ota.zip of=/dev/block/boot bs=4096"

# 使用 fastboot
fastboot flash boot boot.img
```

## 后续计划

### Alpine Linux 迁移

1. 下载 Alpine Linux ARM64 rootfs
2. 推送到设备
3. 配置 chroot 环境
4. 迁移系统服务
5. 测试功能

### 系统优化

1. 内核参数优化
2. 内存使用优化
3. 文件系统优化
4. 网络配置优化

### 功能扩展

1. Docker 支持
2. Web 服务器
3. 数据库系统
4. 监控工具

## 贡献指南

### 文档规范

1. 使用 Markdown 格式
2. 包含代码示例
3. 添加验证步骤
4. 记录故障排除

### 代码规范

1. 使用 Python 3
2. 添加注释说明
3. 包含错误处理
4. 提供测试用例

## 许可证

本项目文档仅供学习和研究使用。

## 联系方式

如有问题或建议，请通过以下方式联系：

- 项目 Issues
- 技术论坛
- 邮件联系

## 更新日志

### 2026-07-26

- ✓ 完成内核补丁 (4个补丁)
- ✓ 实现系统裁剪
- ✓ 配置网络持久化
- ✓ 创建启动脚本
- ✓ 编写完整文档

### 后续更新

- [ ] Alpine Linux 迁移
- [ ] 系统优化
- [ ] 功能扩展
- [ ] 性能测试

---

**项目状态:** 进行中  
**最后更新:** 2026-07-26  
**维护者:** Xiaomi MiMo
