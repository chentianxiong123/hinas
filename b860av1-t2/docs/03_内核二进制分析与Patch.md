# 阶段三：内核二进制分析与 Patch

## 3.1 分析工具准备

### 安装 ARM64 反汇编工具

```bash
sudo apt-get install binutils-aarch64-linux-gnu
```

### 提取内核

```bash
# 从 boot.img 提取内核（偏移 0x800，大小 0x00B0B790）
dd if=/tmp/ota/boot.img of=/tmp/kernel.bin bs=1 skip=2048 count=11581328
```

## 3.2 字符串分析

### 查找关键字符串

```bash
strings -t x /tmp/ota/boot.img | grep -i "set_fs_safe_mode\|SafeErrCode\|MonitorFailedNum"
```

### 找到的字符串

| 偏移 | 内容 |
|------|------|
| 0x93c291 | "1_____%d > %s goto set_fs_safe_mode" |
| 0x9923d8 | "[set_fs_safe_mode  %d]" |
| 0x992540 | "set_fs_safe_mode at LINE =%d iLen =%d" |
| 0x992568 | "set_fs_safe_mode at LINE =%d " |
| 0x9925b0 | "set_fs_safe_mode at LINE =%d LastErrCode[%c]" |
| 0x9926a8 | "set_misc_safe_mode, %p" |
| 0x9926c0 | "set_misc_safe_mode, %p, %c" |
| 0x9926e0 | "****** set_misc_safe_mode not enter ******" |
| 0x992710 | "set_misc_safe_mode after, %p, %c" |
| 0x992738 | "set_fs_safe_mode at LINE =%d pffd =0x%llx" |
| 0x992780 | "ALERT:File system panic, system will enter safemode..." |
| 0x9927b9 | "0Restarting system from safe_mode." |

### 其他相关字符串

```
"previous I/O error to superblock detected"
"I/O error while writing superblock"
"EXT4-fs (device %s): panic forced after error"
"EXT4-fs error"
"ALERT: normmode rootfs fs is destroyed !"
```

## 3.3 ADRP 指令扫描

### 原理

ARM64 使用 ADRP+ADD 指令对来加载字符串地址：
- ADRP 加载页面地址（4KB 对齐）
- ADD 加载页面内偏移

### 扫描脚本

```python
#!/usr/bin/env python3
"""扫描内核中引用特定页面的 ADRP 指令"""

import struct

# 读取内核
with open('/tmp/kernel.bin', 'rb') as f:
    kernel = f.read()

# 目标页面（字符串所在页面）
target_pages = [0x93B000, 0x991000, 0x992000]

results = []

for i in range(0, len(kernel) - 4, 4):
    word = struct.unpack_from('<I', kernel, i)[0]
    
    # 检查是否是 ADRP 指令
    if (word & 0x9F000000) == 0x90000000:
        rd = word & 0x1F
        immhi = (word >> 5) & 0x7FFFF
        immlo = (word >> 29) & 0x3
        imm = (immhi << 2) | immlo
        if imm & 0x100000:
            imm |= ~0x1FFFFF
        
        pc_page = i & ~0xFFF
        target_page = pc_page + (imm << 12)
        
        for tp in target_pages:
            if target_page == tp:
                # 检查下一条是否是 ADD
                if i + 4 < len(kernel):
                    next_word = struct.unpack_from('<I', kernel, i+4)[0]
                    if (next_word & 0xFFC00000) == 0x91000000:
                        imm12 = (next_word >> 10) & 0xFFF
                        shift = (next_word >> 22) & 0x3
                        if shift == 0:
                            full_addr = target_page + imm12
                            results.append((i, rd, full_addr))

# 输出结果
for offset, reg, addr in sorted(results):
    print(f"ADRP+ADD at 0x{offset:X}: x{reg}, addr 0x{addr:X}")
```

### 关键发现

找到大量引用 0x991000 和 0x992000 页面的代码，这些是 set_fs_safe_mode 相关函数。

## 3.4 定位 set_fs_safe_mode 函数

### 方法

1. 找到引用 "ALERT:File system panic" 字符串的代码
2. 该字符串在 0x991F80（文件偏移 0x992780）
3. 找到引用页面 0x991000 的 ADRP 指令
4. 追踪代码流，找到函数入口

### 找到的函数

```
0x4798E0: ALERT 处理函数
  - 打印 "ALERT:File system panic, system will enter safemode..."
  - 调用 panic/restart

0x47991C: set_fs_safe_mode 主函数
  - 打印 "Restarting system from safe_mode"
  - 读取 conf 分区
  - 递增 SafeErrCode
  - 设置 WorkMode=1
  - 触发重启
```

### 反汇编分析

#### ALERT 处理函数 (0x4798E0)

```asm
4798e0: 900028c0    adrp x0, 0x991000      ; 加载字符串页面
4798e4: 910003fd    mov x29, sp             ; 设置帧指针
4798e8: 913c8000    add x0, x0, #0xf20     ; 字符串偏移
4798ec: 940af7ac    bl 0x73779c             ; 调用 printk
4798f0: b0002fe1    adrp x1, 0xa76000
4798f4: 900028c0    adrp x0, 0x991000
4798f8: 52800082    mov w2, #0x4
4798fc: 913d6000    add x0, x0, #0xf58
479900: b9064422    str w2, [x1, #1604]
479904: 940af7a6    bl 0x73779c             ; 调用 printk
479908: 900028c0    adrp x0, 0x991000
47990c: 913e0000    add x0, x0, #0xf80     ; "ALERT:File system panic"
479910: 97eef8e2    bl 0x37c98              ; 调用 panic/restart ← 关键！
479914: a8c17bfd    ldp x29, x30, [sp], #16
479918: d65f03c0    ret                     ; 返回
```

#### set_fs_safe_mode 主函数 (0x47991C)

```asm
47991c: a9ba7bfd    stp x29, x30, [sp, #-96]!  ; 保存寄存器
479920: 2a0003e1    mov w1, w0
479924: 910003fd    mov x29, sp
479928: a90363f7    stp x23, x24, [sp, #48]
47992c: 2a0003f7    mov w23, w0
479930: 900028c0    adrp x0, 0x991000
479934: 913e4000    add x0, x0, #0xf90     ; "Restarting system from safe_mode"
479938: f90023f9    str x25, [sp, #64]
47993c: a90153f3    stp x19, x20, [sp, #16]
479940: a9025bf5    stp x21, x22, [sp, #32]
479944: 940af796    bl 0x73779c             ; 调用 printk
479948: d2900000    mov x0, #0x8000
47994c: 52801a01    mov w1, #0xd0
479950: 52800062    mov w2, #0x3
479954: 97f184ab    bl 0xdac00              ; 分配内存
479958: aa0003f3    mov x19, x0
47995c: b40021e0    cbz x0, 0x479d98        ; 检查分配是否成功
...
```

## 3.5 Patch 方案

### Patch 点选择

| 地址 | 原始指令 | Patch | 原因 |
|------|----------|-------|------|
| 0x4798E0 | ADRP x0, 0x991000 | RET | ALERT 函数直接返回 |
| 0x479910 | BL 0x37C98 | NOP | 去掉 panic/restart 调用 |
| 0x47991C | STP x29, x30, [sp,-96]! | RET | set_fs_safe_mode 直接返回 |

### 编码

```
ARM64 指令编码:
- RET:  0xD65F03C0
- NOP:  0xD503201F
```

### Patch 脚本

```python
#!/usr/bin/env python3
"""Patch set_fs_safe_mode 函数"""

import struct

RET = 0xD65F03C0      # ARM64 RET 指令
NOP = 0xD503201F      # ARM64 NOP 指令

# 读取原始 boot.img
with open('/tmp/boot_cma16.img', 'rb') as f:
    boot = bytearray(f.read())

# 验证原始指令
func_offset = 0x800 + 0x47991C
call_offset = 0x800 + 0x479910
alert_offset = 0x800 + 0x4798E0

orig1 = struct.unpack_from('<I', boot, func_offset)[0]
orig2 = struct.unpack_from('<I', boot, call_offset)[0]
orig3 = struct.unpack_from('<I', boot, alert_offset)[0]

assert orig1 == 0xA9BA7BFD, f"Unexpected: 0x{orig1:08X}"
assert orig2 == 0x97EEF8E2, f"Unexpected: 0x{orig2:08X}"
assert orig3 == 0x900028C0, f"Unexpected: 0x{orig3:08X}"

# 应用 Patch
struct.pack_into('<I', boot, func_offset, RET)
struct.pack_into('<I', boot, call_offset, NOP)
struct.pack_into('<I', boot, alert_offset, RET)

# 保存
with open('/tmp/boot_cma16_patched.bin', 'wb') as f:
    f.write(boot)

print("Patch 完成！")
```

## 3.6 验证 Patch

### 反汇编验证

```bash
aarch64-linux-gnu-objdump -D -b binary -m aarch64 \
    --start-address=0x47A0E0 --stop-address=0x47A130 \
    /tmp/boot_cma16_patched.bin
```

### 预期输出

```
47a0e0: d65f03c0    ret                    ; Patch 1: ALERT 函数直接返回
47a0e4: 910003fd    mov x29, sp
47a0e8: 913c8000    add x0, x0, #0xf20
47a0ec: 940af7ac    bl 0x737f9c
...
47a110: d503201f    nop                    ; Patch 2: 去掉 panic 调用
47a114: a8c17bfd    ldp x29, x30, [sp], #16
47a118: d65f03c0    ret
47a11c: d65f03c0    ret                    ; Patch 3: set_fs_safe_mode 直接返回
```

### 功能验证

```bash
# 刷入 patched boot
dd if=/storage/usb0/boot_cma16_patched.bin of=/dev/block/boot bs=4096 conv=fsync

# 重启
reboot

# 验证
# 1. 删除 framework JAR
rm -rf /system/framework/services.jar

# 2. 等待 3 分钟
# 3. 系统应该稳定运行，不会重启
```

## 3.7 CMA 修改

### 背景

设备默认 CMA（连续内存分配器）为 336MB，占了大量内存。

### 修改方法

CMA 大小在 DTB 中定义。修改 DTB 中的 `CmaTotal` 值。

### DTB 偏移

```
DTB 0: 0xC439A0
DTB 1: 0xC4B9A0
DTB 2: 0xC539A0
```

### 修改

```python
# 找到 CmaTotal 字符串并修改值
# 原始: CmaTotal = 336MB
# 修改: CmaTotal = 20MB
```

### 结果

内存从 654MB 增加到 970MB。

---

*阶段三完成：内核二进制分析与 Patch*
