# 阶段六：init.rc 钩子与启动流程

## 6.1 init.rc 文件结构

### 文件位置

```
/tmp/boot_plan/ramdisk/
├── init.rc              # 主配置
├── init.zxic.rc         # ZTE 平台配置
├── init.product.rc      # 产品配置（导入 zte_init.rc）
├── zte_init.rc          # ZTE 初始化
├── zte_middleware.rc    # ZTE 中间件
├── init.usb.rc          # USB 配置
├── init.environ.rc      # 环境变量
├── init.trace.rc        # 跟踪配置
├── fstab.zxic           # 文件系统表
└── ...
```

## 6.2 完整启动链

### 启动顺序

```
内核启动
  ↓
/init (PID 1)
  ↓
读取 /init.rc
  ↓
导入 /init.environ.rc
导入 /init.usb.rc
导入 /init.${ro.hardware}.rc (= init.zxic.rc)
导入 /init.trace.rc
  ↓
on early-init
  → write /proc/1/oom_adj -16
  → setcon u:r:init:s0
  → start ueventd
  ↓
on init
  → sysclktz 0
  → loglevel 3
  → 创建符号链接 (/system/etc → /etc, /d → /sys/kernel/debug, /vendor → /system/vendor)
  → 创建 cgroup 挂载点
  → 创建目录 (/system, /data, /cache, /config)
  → 设置内核参数
  ↓
on post-fs
  → mount rootfs rootfs / ro remount
  → 设置 /cache 权限
  → 恢复 /cache SELinux 上下文
  ↓
on fs
  → mount_all /fstab.zxic (挂载所有分区)
  → swapon_all /fstab.zxic (启用 swap)
  ↓
on post-fs-data
  → 设置 /data 权限
  → 创建各种目录
  → 设置各种权限
  ↓
on boot
  → ifup lo
  → hostname localhost
  → 设置 RLIMIT
  → 设置内存管理参数
  → 设置网络参数
  → class_start core ← 启动核心服务
  ↓
on nonencrypted
  → class_start late_start ← 启动延迟服务
  ↓
on charger
  → class_start charger ← 充电模式
```

## 6.3 class 分组详解

### core class

启动时机：`on boot` → `class_start core`

| 服务 | 可执行文件 | 说明 |
|------|-----------|------|
| ueventd | /sbin/ueventd | 设备事件守护进程 |
| healthd | /sbin/healthd | 健康监控 |
| adbd | /sbin/adbd | ADB 守护进程 |
| servicemanager | /system/bin/servicemanager | IPC 服务管理 |
| vold | /system/bin/vold | 存储管理 |
| console | /system/bin/sh | 控制台 shell |

### main class

启动时机：`class_start main`（被删除）

| 服务 | 可执行文件 | 说明 |
|------|-----------|------|
| netd | /system/bin/netd | 网络守护进程 |
| debuggerd | /system/bin/debuggerd | 调试守护进程 |
| surfaceflinger | /system/bin/surfaceflinger | 显示合成 |
| zygote | /system/bin/app_process | Java 虚拟机 |
| drm | /system/bin/drmserver | DRM 服务 |
| media | /system/bin/mediaserver | 媒体服务 |
| bootanim | /system/bin/bootanimation | 开机动画 |
| installd | /system/bin/installd | 安装守护进程 |
| keystore | /system/bin/keystore | 密钥存储 |
| flash_recovery | /system/etc/install-recovery.sh | 恢复更新 |

### late_start class

启动时机：`on nonencrypted` → `class_start late_start`

| 服务 | 可执行文件 | 说明 |
|------|-----------|------|
| sdcard | /system/bin/sdcard | SD 卡服务 |
| ethernet | /system/bin/sh /system/etc/eth0.sh | 以太网配置 |

### charger class

启动时机：`on charger` → `class_start charger`

| 服务 | 可执行文件 | 说明 |
|------|-----------|------|
| healthd-charger | /sbin/healthd -n | 充电健康监控 |

## 6.4 属性触发器

### sys.boot_completed

```
on property:sys.boot_completed=1
    start preinstall
```

**触发条件：** 系统启动完成
**触发动作：** 启动 preinstall 服务

### sys.zte.sshd

```
on property:sys.zte.sshd=stop
    stop ssh_start
    start ssh_stop

on property:sys.zte.sshd=start
    stop ssh_stop
    start ssh_start
```

**触发条件：** 设置 sys.zte.sshd 属性
**触发动作：** 启动/停止 SSH 服务

### sys.evtmanager.started

```
on property:sys.evtmanager.started=1
    start middwareShell
    start ys-service
```

**触发条件：** 事件管理器启动完成
**触发动作：** 启动中间件 shell 和云服务

### wifi.ap

```
on property:wifi.ap=1
    start seteth0ap

on property:wifi.ap=0
    start setppp0ap
```

**触发条件：** WiFi AP 模式切换
**触发动作：** 设置以太网/PPP0 路由

### sys.zte.cleanData

```
on property:sys.zte.cleanData=1
    start zte-clean-data
```

**触发条件：** 请求清除数据
**触发动作：** 启动数据清除服务

### vold.decrypt

```
on property:vold.decrypt=trigger_reset_main
    class_reset main

on property:vold.decrypt=trigger_load_persist_props
    load_persist_props

on property:vold.decrypt=trigger_post_fs_data
    trigger post-fs-data

on property:vold.decrypt=trigger_restart_min_framework
    class_start main

on property:vold.decrypt=trigger_restart_framework
    class_start main
    class_start late_start

on property:vold.decrypt=trigger_shutdown_framework
    class_reset late_start
    class_reset main
```

**触发条件：** vold 解密事件
**触发动作：** 框架重启/关闭

### sys.powerctl

```
on property:sys.powerctl=*
    powerctl ${sys.powerctl}
```

**触发条件：** 电源控制请求
**触发动作：** 执行电源操作（重启/关机）

### selinux.reload_policy

```
on property:selinux.reload_policy=1
    restart ueventd
    restart installd
```

**触发条件：** SELinux 策略重载
**触发动作：** 重启 ueventd 和 installd

### ro.debuggable

```
on property:ro.debuggable=1
    start console
```

**触发条件：** 可调试模式
**触发动作：** 启动控制台 shell

## 6.5 服务 onrestart 链

### servicemanager

```
service servicemanager /system/bin/servicemanager
    class core
    user system
    group system
    critical
    onrestart restart healthd
    onrestart restart zygote
    onrestart restart media
    onrestart restart surfaceflinger
    onrestart restart drm
```

**如果 servicemanager 重启：**
1. 重启 healthd
2. 重启 zygote
3. 重启 media
4. 重启 surfaceflinger
5. 重启 drm

### surfaceflinger

```
service surfaceflinger /system/bin/surfaceflinger
    class main
    user system
    group graphics drmrpc
    onrestart restart zygote
```

**如果 surfaceflinger 重启：**
1. 重启 zygote

### zygote

```
service zygote /system/bin/app_process -Xzygote /system/bin --zygote --start-system-server
    class main
    disabled
    socket zygote stream 660 root system
    onrestart write /sys/android_power/request_state wake
    onrestart write /sys/power/state on
    onrestart restart media
    onrestart restart netd
```

**如果 zygote 重启：**
1. 唤醒电源
2. 重启 media
3. 重启 netd

## 6.6 关键服务定义

### preinstall

```
service preinstall /system/bin/preinstall.sh
    disabled
    oneshot
```

**触发：** `on property:sys.boot_completed=1`
**作用：** 预装 APK（已清空）

### ssh_start / ssh_stop

```
service ssh_start /system/xbin/ssh_control 1
    class main
    disabled
    oneshot

service ssh_stop /system/xbin/ssh_control 0
    class main
    disabled
    oneshot
```

**触发：** `on property:sys.zte.sshd=start/stop`
**作用：** 启动/停止 SSH 服务

### zte_post_boot

```
service zte_post_boot /system/bin/sh /system/etc/init.zte.post_boot.sh
    class core
    oneshot
```

**触发：** class core 启动时
**作用：** 启动后配置（已删除）

### middwareShell

```
service middwareShell /system/bin/zte_middleware.sh
    disabled
    oneshot
```

**触发：** `on property:sys.evtmanager.started=1`
**作用：** 中间件 shell（已删除）

### monitor_e2fs

```
service monitor_e2fs /system/bin/monitor_e2fs
    class main
    oneshot
```

**触发：** class main 启动时
**作用：** ext4 文件系统监控（已删除）

### dhcpcd_eth0

```
service dhcpcd_eth0 /system/bin/dhcpcd -ABKL
    class main
    disabled
    oneshot
```

**触发：** 手动启动
**作用：** DHCP 客户端

### ethernet

```
service ethernet /system/bin/sh /system/etc/eth0.sh
    class late_start
    oneshot
```

**触发：** class late_start 启动时
**作用：** 以太网配置

## 6.7 服务标志

### class

指定服务所属的 class，决定何时启动。

### critical

标记为关键服务。如果关键服务崩溃，系统会重启。

### disabled

服务不会自动启动，需要手动 start。

### oneshot

服务只启动一次，退出后不会自动重启。

### socket

创建 socket 文件。

### user / group

指定服务运行的用户和组。

### onrestart

服务重启时执行的操作。

### seclabel

指定 SELinux 标签。

## 6.8 自定义钩子

### 最佳钩子点

1. **sys.boot_completed=1** — 启动完成触发
2. **class core** — 核心服务启动时
3. **sys.zte.sshd=start** — SSH 启动触发

### 创建自定义服务

在 init.rc 或 init.zxic.rc 中添加：

```
service my_service /system/bin/my_script.sh
    class core
    oneshot
    disabled
```

然后通过属性触发：

```
on property:sys.boot_completed=1
    start my_service
```

### 示例：开机自动启动 SSH

```
on property:sys.boot_completed=1
    setprop sys.zte.sshd start
```

### 示例：开机自动配置网络

```
service setup_network /system/bin/sh /system/bin/setup_network.sh
    class core
    oneshot

on property:sys.boot_completed=1
    start setup_network
```

---

*阶段六完成：init.rc 钩子与启动流程*
