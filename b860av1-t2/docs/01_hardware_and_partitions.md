# ZTE B860AV1.1-T2 硬件与分区分析

## 设备信息

| 项目 | 值 |
|---|---|
| SoC | ZX296716 (中兴微电子) |
| CPU | 4核 Cortex-A53, ARMv8 |
| 内存 | 990 MB (1014156 kB) |
| 存储 | 8GB eMMC (mmcblk0) |
| 系统 | Android 4.4.2 |
| Root | SuperSU v2.78 |

## 分区表

```
mmcblk0p1   bootloader   4MB     u-boot
mmcblk0p2   (unknown)    64MB
mmcblk0p3   conf         4MB     配置分区(INI格式)
mmcblk0p4   cache        768MB
mmcblk0p5   env          8MB     u-boot环境变量
mmcblk0p6   logo         32MB    开机logo
mmcblk0p7   (unknown)    32MB
mmcblk0p8   misc         8MB     boot模式标志
mmcblk0p9   (unknown)    8MB
mmcblk0p10  boot         32MB    内核+ramdisk+DTB
mmcblk0p11  (unknown)    32MB
mmcblk0p12  (unknown)    32MB
mmcblk0p13  system       1GB     Android系统分区
mmcblk0p14  data         5.2GB   用户数据
mmcblk0rpmb              512KB   RPMB
mmcblk0boot0             4MB     eMMC boot0
mmcblk0boot1             4MB     eMMC boot1
```

## 内存状态（原始）

```
MemTotal:    1014156 kB (990 MB)
MemFree:      280648 kB (274 MB)
CmaTotal:     282624 kB (276 MB)  ← GPU/视频解码器预留
CmaFree:      265780 kB (259 MB)  ← 259MB空闲未使用
```

## 串口信息

- 设备：FTDI FT232R USB-to-Serial
- 波特率：115200
- 设备路径：`/dev/ttyUSB0`
- 连接命令：`screen /dev/ttyUSB0 115200`

## conf 分区格式

INI 格式，存储 safe_mode 监控数据：

```ini
[System]
SafeErrCode=0
MonitorFailedNum=0
[Common]
KeyControlTime=0
[QOS]
ErrorCodeStr=10000
```

内核驱动 `set_fs_safe_mode` 读写此分区，用于触发 safe_mode 重启保护。
