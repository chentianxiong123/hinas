# Android Chroot 网络权限问题完全解决指南

## 问题描述

在 Android 设备上 chroot 进入 Linux 发行版（如 Debian/Ubuntu）后，网络相关程序（apt-get、ping、curl 等）报错：

```
Could not create a socket for x.x.x.x (f=2 t=1 p=6) - socket (13: Permission denied)
ping: socket: Permission denied
```

但普通 TCP/UDP socket（如 wget、curl）可能正常工作。

## 根本原因

Android 内核启用了 `CONFIG_ANDROID_PARANOID_NETWORK` 补丁，强制检查进程的 GID：

```c
// 内核源码 net/socket.c
static inline int current_has_network(void)
{
    return in_egroup_p(AID_INET) || in_egroup_p(AID_NET_RAW);
}
```

- **GID 3003 (inet)** → 允许创建 AF_INET/AF_INET6 socket
- **GID 3004 (net_raw)** → 允许创建 raw socket（ping 需要）

即使你是 root (UID=0)，GID 不对也不行。这是内核级检查，与 SELinux 无关。

## 为什么 chroot 会有这个问题？

Android 的 shell 进程 GID 是 2000 (shell)：
```
uid=0(root) gid=2000(shell) groups=1000(system),1007(log)
```

chroot 继承父进程的 GID，所以 chroot 里的进程也是 GID 2000，没有 inet (3003) 组。

## 为什么 Termux 没这个问题？

Termux 是 Android 应用，安装时 Android 自动给它分配 inet 组：
```
Termux进程: uid=10129(u0_a129) gid=10129 groups=10129,3003(inet),9997
```

Termux 不用 chroot，直接在 Android 环境里跑，继承了 inet 组。

## 解决方案

### 方案一：`su - root` 重新登录（推荐，最干净）

```bash
chroot /data/debian /bin/su - root -c 'apt-get update'
chroot /data/debian /bin/su - root -c 'ping 8.8.8.8'
```

**原理：** `su - root` 读取 chroot 里的 `/etc/passwd` 和 `/etc/group`，给进程分配正确的 GID。

**前提配置：**

```bash
# /etc/passwd - root 的 GID 改成 3003
root:x:0:3003:root:/root:/bin/bash

# /etc/group - 添加 inet 和 net_raw 组，root 加入
inet:x:3003
net_raw:x:3004
root:x:0:root,inet,net_raw
```

### 方案二：`sg inet` 切换组

```bash
chroot /data/debian /usr/bin/sg inet -c 'ping 8.8.8.8'
```

**缺点：** 需要包装每个命令。

### 方案三：改 `_apt` 用户 GID（只修 apt-get）

```bash
# 编辑 /etc/passwd，把 _apt 的 GID 从 65534 改成 3003
_apt:x:42:3003::/nonexistent:/usr/sbin/nologin

# 设置 APT 沙箱
echo 'APT::Sandbox::User "root";' > /etc/apt/apt.conf.d/99sandbox
```

**缺点：** 只解决 apt-get，ping 还是不行。

## 完整配置步骤

### 1. 修改 /etc/passwd

```bash
# root 的 GID 改成 3003
sed -i 's/^root:x:0:0:/root:x:0:3003:/' /etc/passwd

# _apt 的 GID 改成 3003（解决 apt-get）
sed -i 's/^_apt:x:.*:65534:/_apt:x:42:3003:/' /etc/passwd
```

### 2. 修改 /etc/group

```bash
cat >> /etc/group << 'EOF'
inet:x:3003
net_raw:x:3004
root:x:0:root,inet,net_raw
EOF
```

### 3. 配置 APT 沙箱

```bash
echo 'APT::Sandbox::User "root";' > /etc/apt/apt.conf.d/99sandbox
```

### 4. 验证

```bash
chroot /data/debian /bin/su - root -c 'id'
# 期望: uid=0(root) gid=3003(inet) groups=3003(inet),0(root)

chroot /data/debian /bin/su - root -c 'ping -c 1 8.8.8.8'
# 期望: PING 成功

chroot /data/debian /bin/su - root -c 'apt-get update'
# 期望: 正常下载包列表
```

## 技术细节

### Android 的 GID 硬编码

```
AID_INET = 3003    # 可以创建 AF_INET/AF_INET6 socket
AID_NET_RAW = 3004 # 可以创建 raw socket
AID_NET_ADMIN = 3005 # 可以配置网络接口和路由表
AID_NET_BT = 3002  # 蓝牙 socket
AID_NET_BT_ADMIN = 3001 # 蓝牙管理
```

### 为什么 `su - root` 能解决？

1. `su - root` 读取 `/etc/passwd` → root:x:0:3003
2. `su - root` 读取 `/etc/group` → inet:x:3003, net_raw:x:3004
3. `su` 调用 `setgid(3003)` 设置进程 GID
4. 内核检查 `in_egroup_p(AID_INET)` → true → 允许创建 socket

### 为什么直接 `chroot` 不行？

1. `chroot` 继承父进程的 UID/GID
2. 父进程是 Android shell，GID=2000
3. chroot 不读取 `/etc/passwd` 或 `/etc/group`
4. 内核检查 `in_egroup_p(AID_INET)` → false → 拒绝

## 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `socket (13: Permission denied)` | 缺少 inet 组 (3003) | 用 `su - root` 或改 GID |
| `socket (1: Operation not permitted)` | 缺少 net_raw 组 (3004) | 用 `su - root` 或加 net_raw 组 |
| `Temporary failure resolving` | DNS 配置错误 | 检查 `/etc/resolv.conf` |
| `Could not create a socket` | apt-get 的 _apt 用户 GID 错误 | 改 `_apt` GID 为 3003 |

## 参考资料

- [Android filesystem_config.h](https://android.googlesource.com/platform/system/core/+/08c370c/include/private/android_filesystem_config.h)
- [StackOverflow: apt-get fails on chroot](https://stackoverflow.com/questions/43724042/apt-get-update-fails-on-chroot-ubuntu-16-04-on-android)
- [StackOverflow: socket Permission denied](https://stackoverflow.com/questions/36451444/what-can-cause-a-socket-permission-denied-error)
- [GitHub: linuxdeploy issue #1158](https://github.com/meefik/linuxdeploy/issues/1158)

---

**作者:** Xiaomi MiMo  
**日期:** 2026-07-29  
**版本:** 1.0
