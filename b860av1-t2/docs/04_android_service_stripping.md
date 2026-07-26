# Android 服务裁剪与内存优化

## 目标

将盒子从 Android 系统变为纯 Linux 服务器，释放被 Java 框架占用的内存。

## 内存占用分析

| 进程 | RSS | 说明 |
|---|---|---|
| zygote | 43 MB | Java 虚拟机 |
| system_server | 50 MB | Android 系统服务 |
| com.android.systemui | 30 MB | 系统UI |
| com.dangbei.tvlauncher | 150 MB | 当贝桌面(含子进程) |
| ZTE 中间件群 | 300+ MB | 十多个进程 |
| mediaserver | 9 MB | 媒体服务 |

## 运行时 Kill 方案

### 问题：init 会自动重启服务

直接 `kill -9` 没用，Android init 会自动拉起服务。

### 解决：用 `stop` 命令

```bash
stop zygote
stop surfaceflinger
stop servicemanager
stop mediaserver
stop drm
stop installd
stop keystore
stop bootanim
stop netd
```

`stop` 告诉 init 不再重启该服务。之后再 `kill -9` 杀残留进程。

### 杀残留进程

```bash
killall -9 com.zte. com.ztestb. com.stbmc. com.mcsp. com.dangbei. com.android. zteplayer com.itv. com.talkingdata
killall -9 MainCenter hgAgent zte_probe zteKlog autotest netaccess wirelesskey depconfig
```

## 效果

| 项目 | Kill 前 | Kill 后 |
|---|---|---|
| 内存占用 | 733 MB | 300 MB |
| 空闲内存 | 280 MB | 714 MB |
| 用户进程数 | 60+ | 15 |

## 启动 WiFi + SSH

Kill 后系统只剩内核 + 基础服务。手动启动：

```bash
insmod /system/lib/modules/8189fs.ko
ifconfig wlan0 up
wpa_supplicant -B -i wlan0 -c /data/wpa.conf
dhcpcd wlan0
dropbear -p 22
```
