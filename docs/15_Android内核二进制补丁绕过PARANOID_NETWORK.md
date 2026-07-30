# Android 内核二进制补丁：绕过 CONFIG_ANDROID_PARANOID_NETWORK

## 背景

ZTE B860AV1.1-T2 (ZX296716) 的 Android 4.4.2 内核启用了 `CONFIG_ANDROID_PARANOID_NETWORK`，强制检查进程 GID：

```c
// 内核源码 net/socket.c
static inline int current_has_network(void)
{
    return in_egroup_p(AID_INET) || in_egroup_p(AID_NET_RAW);
}
```

- **GID 3003 (AID_INET)** → 允许创建 AF_INET/AF_INET6 socket
- **GID 3004 (AID_NET_RAW)** → 允许创建 raw socket（ping 需要）
- **GID 3005 (AID_NET_ADMIN)** → 允许配置网络接口和路由表

即使 root (UID=0)，GID 不是 3003 也会被拒绝。这是内核级检查，无法通过 userspace 配置绕过。

## 解决方案：二进制补丁

由于设备没有 kprobes/eBPF 支持，无法 hook 内核函数。直接对 boot 镜像中的内核进行二进制补丁。

### 补丁原理

`current_has_network()` 是 `static inline` 函数，在每个调用点被内联展开。编译后的模式：

```asm
movz w0, #0xbbb      ; 加载 AID_INET (3003)
bl   in_egroup_p     ; 调用组检查
cbz  w0, check_raw   ; 如果不在 inet 组，跳转检查 net_raw
; ... return 1 (有权限)
check_raw:
movz w0, #0xbbc      ; 加载 AID_NET_RAW (3004)
bl   in_egroup_p     ; 调用组检查
cbz  w0, no_network  ; 如果不在 raw 组，无权限
; ... return 1 (有权限)
```

### 补丁方法

将每个 `bl in_egroup_p` 指令替换为 `movz w0, #1`，使函数始终返回"有权限"：

```
原始: bl in_egroup_p   (97xxxxxx)
补丁: movz w0, #1      (52800020)
```

这样 `cbz` 检查 w0=1 不会跳转，直接走到"返回1"的路径。

### 扫描结果

全盘扫描内核镜像中所有加载 AID 常量的 `movz` 指令，找到 5 处匹配：

| 地址 | GID | 函数 | 补丁 |
|------|-----|------|------|
| 0x5c9210 | 3003 (AID_INET) | `current_has_network()` 调用点 1 | ✅ |
| 0x6107ec | 3003 (AID_INET) | `current_has_network()` 调用点 2 | ✅ |
| 0x23ec2c | 3004 (AID_NET_RAW) | `current_has_network_admin()` | ✅ |
| 0x23ec50 | 3005 (AID_NET_ADMIN) | `current_has_network_admin()` 第二段 | ✅ |
| 0x5fb754 | 3005 (AID_NET_ADMIN) | `capable(CAP_NET_ADMIN)` 调用 | ❌ 不补 |

**未补丁的第 5 处**（0x5fb754）是 `capable()` 类检查，使用 `w1` 而非 `w0`，且调用 0x19c84 而非 `in_egroup_p`，属于不同的权限检查路径，不属于 socket 权限。

### 补丁脚本

```python
import struct

with open('/tmp/boot_headless.bin', 'rb') as f:
    data = bytearray(f.read())

movz_w0_1 = struct.pack('<I', 0x52800020)  # movz w0, #1

patches = [
    0x5c9210,  # current_has_network → AID_INET
    0x6107ec,  # current_has_network → AID_INET
    0x23ec2c,  # current_has_network_admin → AID_NET_RAW
    0x23ec50,  # current_has_network_admin → AID_NET_ADMIN
]

for off in patches:
    data[off:off+4] = movz_w0_1

with open('/tmp/boot_patched.bin', 'wb') as f:
    f.write(data)
```

### Boot 镜像结构

```
偏移 0x000-0x05F: ZTE 私有头 (Ufw.norm, 版本, CRC)
偏移 0x060-0x085F: Android boot header (ANDROID!)
偏移 0x0860-0xB0C05F: Kernel (0xb0b790 bytes)
偏移 0xB0C060-0xC4285F: Ramdisk (0x136348 bytes)
偏移 0xC42860-0xC5B05F: Second stage (0x18140 bytes)
总大小: 0xC5B060 (12,955,744 bytes)
页大小: 0x800 (2048 bytes)
```

### 刷入方法

```bash
# 通过 ADB
adb push boot_patched.bin /data/local/tmp/
adb shell su -c "dd if=/data/local/tmp/boot_patched.bin of=/dev/block/mmcblk0p13"
adb shell su -c "reboot"

# 通过 SSH
scp boot_patched.bin zte-box:/tmp/
ssh zte-box "dd if=/tmp/boot_patched.bin of=/dev/block/mmcblk0p13 && reboot"
```

### 验证

```bash
# 无 inet 组也能创建 socket
ssh zte-box "sg nogroup -c 'python3 -c \"import socket; s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); print(\\\"OK\\\"); s.close()\"'"

# ping 正常工作
ssh zte-box "ping -c 1 8.8.8.8"

# TCP/HTTPS 正常
ssh zte-box "curl -s -o /dev/null -w '%{http_code}' https://baidu.com"
```

## 补充：ZRAM Swap 配置

补丁同时配置了 512MB zram swap（物理内存的 50%）：

```bash
# 手动启用
mknod /dev/zram0 b 254 0
echo 536870912 > /sys/block/zram0/disksize
mkswap /dev/zram0
chmod 0660 /dev/zram0
swapon /dev/zram0
```

已添加到 `/system/etc/init.zte.post_boot.sh`，开机自动启用。

## 注意事项

1. **major 号**：zram 设备的 major 号是 254（不是常见的 253），需要从 `/sys/block/zram0/dev` 读取
2. **boot 镜像对齐**：所有段相对 ANDROID! 头（偏移 0x60）按 0x800 页对齐
3. **ZTE 私有头**：boot 镜像前 0x60 字节是 ZTE 私有格式头，不可修改
4. **补丁安全**：只替换了 4 条 BL 指令为 MOVZ，不影响其他功能

---

**作者:** Xiaomi MiMo
**日期:** 2026-07-30
**版本:** 1.0
