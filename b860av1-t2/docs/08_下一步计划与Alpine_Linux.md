# 阶段八：下一步计划与 Alpine Linux

## 8.1 当前系统状态

### 空间使用

```
/system    991.9MB 总量
           227.7MB 已用
           764.2MB 空闲

/data      5.2GB 总量
           可用于 Linux rootfs
```

### 文件统计

| 目录 | 文件数 | 说明 |
|------|--------|------|
| /system/bin/ | 116 | Linux 基础工具 |
| /system/lib/ | 351 | 动态链接库 |
| /system/xbin/ | 280 | busybox 符号链接 |
| /system/etc/ | ~20 | 精简配置 |
| /system/fonts/ | 0 | 已清空 |
| /system/media/ | 0 | 已清空 |

### 运行中的进程

```
servicemanager  — IPC 核心
vold            — 存储管理
adbd            — ADB 远程访问
daemonsu        — root 权限
busybox         — 基本工具
sh              — shell
```

### 内核状态

- set_fs_safe_mode 已禁用（二进制 Patch）
- CMA 已修改（336MB → 20MB）
- 内存可用：~970MB

## 8.2 Alpine Linux 方案

### 为什么选择 Alpine

| 特性 | Alpine | Debian | Arch |
|------|--------|--------|------|
| 最小大小 | ~5MB | ~150MB | ~30MB |
| 包管理 | apk | apt | xbps |
| libc | musl | glibc | glibc |
| init | OpenRC | systemd | systemd |
| 内存占用 | 低 | 中 | 中 |
| 嵌入式适合度 | ⭐⭐⭐ | ⭐⭐ | ⭐ |

**Alpine 优势：**
- 体积最小
- 内存占用低
- 适合嵌入式
- 包管理简单

### 下载

```bash
# ARM hard-float (推荐)
wget https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/armhf/alpine-minirootfs-3.19.1-armhf.tar.gz

# 或 ARM soft-float
wget https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/armhf/alpine-minirootfs-3.19.1-armhf.tar.gz
```

### 大小

约 2.6MB（压缩后），约 6MB（解压后）。

## 8.3 安装步骤

### 步骤 1：下载 rootfs

在电脑上：

```bash
cd /tmp
wget https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/armhf/alpine-minirootfs-3.19.1-armhf.tar.gz
```

### 步骤 2：传到设备

方案 A（USB）：

```bash
# 复制到 U 盘
cp alpine-minirootfs-3.19.1-armhf.tar.gz /media/a1/0073-E659/

# 在设备上挂载 U 盘
mount -t vfat /dev/block/sda1 /storage/usb0

# 创建目录
mkdir -p /data/alpine

# 解压
tar -xzf /storage/usb0/alpine-minirootfs-3.19.1-armhf.tar.gz -C /data/alpine
```

方案 B（adb）：

```bash
# 在电脑上
adb push alpine-minirootfs-3.19.1-armhf.tar.gz /data/

# 在设备上
mkdir -p /data/alpine
tar -xzf /data/alpine-minirootfs-3.19.1-armhf.tar.gz -C /data/alpine
```

### 步骤 3：挂载必要的文件系统

```bash
mount -t proc proc /data/alpine/proc
mount -t sysfs sysfs /data/alpine/sys
mount -o bind /dev /data/alpine/dev
mount -o bind /dev/pts /data/alpine/dev/pts
```

### 步骤 4：进入 chroot

```bash
chroot /data/alpine /bin/sh
```

### 步骤 5：初始化 Alpine

```bash
# 更新包管理器
apk update

# 安装基本工具
apk add bash openssh vim curl wget

# 配置 SSH
ssh-keygen -A
echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
echo "root:123456" | chpasswd

# 启动 SSH
/usr/sbin/sshd
```

### 步骤 6：配置网络

```bash
# 配置 DNS
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 配置网络接口
ip addr add 192.168.31.208/24 dev eth0
ip link set eth0 up
ip route add default via 192.168.31.1

# 或者用 DHCP
apk add dhcpcd
dhcpcd eth0
```

## 8.4 开机自动启动

### 创建启动脚本

创建 `/system/bin/start_linux.sh`：

```bash
#!/system/bin/sh

# 挂载必要的文件系统
mount -t proc proc /data/alpine/proc
mount -t sysfs sysfs /data/alpine/sys
mount -o bind /dev /data/alpine/dev
mount -o bind /dev/pts /data/alpine/dev/pts

# 配置网络
chroot /data/alpine /bin/sh -c "
    echo 'nameserver 8.8.8.8' > /etc/resolv.conf
    ip addr add 192.168.31.208/24 dev eth0
    ip link set eth0 up
    ip route add default via 192.168.31.1
"

# 启动 SSH
chroot /data/alpine /usr/sbin/sshd

echo "Linux started successfully"
```

### 设置执行权限

```bash
chmod 755 /system/bin/start_linux.sh
```

### 创建 init 服务

在 `/system/etc/init.zte.post_boot.sh` 中添加：

```bash
#!/system/bin/sh
/system/bin/start_linux.sh
```

或在 init.rc 中添加：

```
service start_linux /system/bin/start_linux.sh
    class core
    oneshot
    disabled

on property:sys.boot_completed=1
    start start_linux
```

## 8.5 进一步裁剪 Android

### 删除剩余无用二进制

```bash
# 网络工具（如果不需要 Android 网络）
rm -rf /system/bin/netcfg /system/bin/netd /system/bin/netstat
rm -rf /system/bin/ping /system/bin/ping6 /system/bin/iftop /system/bin/iperf
rm -rf /system/bin/ip /system/bin/ip6tables /system/bin/iptables
rm -rf /system/bin/dnsmasq /system/bin/mdnsd
rm -rf /system/bin/dhcp6c /system/bin/dhcpd /system/bin/dhcpcd
rm -rf /system/bin/wpa_cli /system/bin/wpa_supplicant

# 文件系统工具（如果用 Alpine 的）
rm -rf /system/bin/e2fsck /system/bin/mkswap

# 其他工具
rm -rf /system/bin/top /system/bin/vmstat /system/bin/uptime
```

**注意：** 删除这些后，Android 的网络功能将不可用。需要确保 Alpine Linux 的网络正常工作。

### 删除库子目录

```bash
rm -rf /system/lib/hw
rm -rf /system/lib/modules/dwc2.ko
```

### 最终 /system 大小

预计约 150MB。

## 8.6 使用场景

### 场景 1：轻量级服务器

```bash
# 安装 nginx
apk add nginx

# 配置并启动
rc-service nginx start
```

### 场景 2：下载服务器

```bash
# 安装 aria2
apk add aria2

# 配置并启动
aria2c --daemon --enable-rpc --rpc-listen-all
```

### 场景 3：家庭自动化

```bash
# 安装 Home Assistant
apk add python3 py3-pip
pip3 install homeassistant

# 启动
hass
```

### 场景 4：Docker 容器

```bash
# 安装 Docker
apk add docker

# 启动 Docker
rc-service docker start
```

## 8.7 性能优化

### 内存优化

```bash
# 在 Android 中禁用不必要的服务
stop servicemanager
stop vold

# 或者在 Alpine 中使用更轻量的 init
apk add openrc
```

### 存储优化

```bash
# 使用压缩文件系统
# 或者删除不需要的包
apk cache clean
```

### 网络优化

```bash
# 配置 TCP 参数
echo "net.core.somaxconn = 65535" >> /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65535" >> /etc/sysctl.conf
sysctl -p
```

## 8.8 监控与维护

### 系统监控

```bash
# 查看内存使用
free -h

# 查看磁盘使用
df -h

# 查看进程
top

# 查看网络
netstat -tuln
```

### 日志管理

```bash
# 查看系统日志
dmesg
tail -f /var/log/messages

# 查看 SSH 日志
tail -f /var/log/auth.log
```

### 备份

```bash
# 备份 Alpine rootfs
tar -czf /storage/usb0/alpine-backup.tar.gz -C /data/alpine .

# 备份配置
cp -r /data/alpine/etc /storage/usb0/alpine-etc-backup/
```

---

*阶段八完成：下一步计划与 Alpine Linux*
