# ZTE Boot Image 逆向工程

## 概述

本文档详细记录了 ZTE B860AV1.1-T2 机顶盒 boot.img 的逆向分析过程，包括 ZTE 特有格式解析、ARM64 内核分析、以及内核补丁技术。

## 1. ZTE Boot Image 格式

### 1.1 文件结构

ZTE B860AV1.1-T2 的 boot.img 使用非标准格式，与标准 Android boot.img 不同：

```
偏移量      大小      描述
0x00-0x5F   96 字节   ZTE 自定义头部
0x60-0x7FF  416 字节  Android 标准头部
0x800-结束   可变      内核 + Ramdisk + DTB
```

### 1.2 ZTE 头部格式

```c
struct zte_header {
    uint32_t magic;          // 0x55667788 (Ufw\x88)
    uint32_t version;        // 版本号
    uint32_t reserved[22];   // 保留字段
};
```

**魔数验证：** `0x55667788` 是 ZTE 特有的标识符。

### 1.3 Android 头部格式

标准 Android boot.img 头部位于偏移 0x60：

```c
struct android_header {
    char magic[8];           // "ANDROID!"
    uint32_t kernel_size;    // 内核大小
    uint32_t kernel_addr;    // 内核加载地址
    uint32_t ramdisk_size;   // Ramdisk 大小
    uint32_t ramdisk_addr;   // Ramdisk 加载地址
    uint32_t second_size;    // 第二阶段大小
    uint32_t second_addr;    // 第二阶段加载地址
    // ... 其他字段
};
```

**注意：** ZTE 设备的头部字段顺序可能与标准不同。

### 1.4 实际文件布局

```
文件大小: 12,959,159 字节 (12.36 MB)
ZTE 魔数: 0x55667788
Android 魔数: "ANDROID!"
内核加载地址: 0x40008000
```

## 2. ARM64 内核分析

### 2.1 ARM64 Image 格式

内核位于偏移 0x800，使用 ARM64 Image 格式：

```c
struct arm64_image_header {
    uint32_t code0;          // 0x00: 跳转指令
    uint32_t code1;          // 0x04
    uint64_t text_offset;    // 0x08: 文本段偏移
    uint64_t image_size;     // 0x10: 镜像大小
    uint64_t flags;          // 0x18: 标志位
    uint64_t res2;           // 0x20: 保留
    uint64_t res3;           // 0x28: 保留
    uint64_t res4;           // 0x30: 保留
    uint32_t magic;          // 0x38: "ARM\x64"
    uint32_t res5;           // 0x3C: 保留
};
```

### 2.2 关键参数

```
ARM64 魔数: 0x41524D64 ("ARM\x64")
文本偏移: 0x8000
镜像大小: 0xBC5000
内核入口: 0x40008000
```

### 2.3 ARM64 指令集基础

ARM64 使用固定 32 位指令长度，关键指令：

```assembly
; 函数序言 (保存帧指针和链接寄存器)
STP X29, X30, [SP, #-0x60]!  ; 保存 X29 (帧指针) 和 X30 (返回地址)
MOV X29, SP                  ; 设置帧指针

; 函数尾声
LDP X29, X30, [SP], #0x60    ; 恢复寄存器
RET                          ; 返回 (跳转到 X30)

; 分支指令
BL #offset                   ; 调用子程序 (保存返回地址到 X30)
B #offset                    ; 无条件跳转

; 数据加载
ADRP X0, #page               ; 加载页面地址 (4KB 对齐)
ADD X0, X0, #offset          ; 加载页面内偏移

; 立即数加载
MOVZ X0, #imm16, LSL #shift  ; 加载 16 位立即数
MOVK X0, #imm16, LSL #shift  ; 保存并加载高 16 位
```

## 3. 内核字符串分析

### 3.1 字符串定位

使用 `strings` 命令查找关键字符串：

```bash
strings -t x kernel.bin | grep -i "set_fs_safe_mode"
```

**结果：**
```
93ba91 1_____%d > %s goto set_fs_safe_mode
991bd8 [set_fs_safe_mode  %d]
991cb0 MonitorFailedNum=%d
991d40 set_fs_safe_mode at LINE =%d iLen =%d
991d68 set_fs_safe_mode at LINE =%d
991db0 set_fs_safe_mode at LINE =%d LastErrCode[%c]
991e00 MonitorFailedNum=
991e18 old MonitorFailedNum[%d] LastErrCode[%c],cErrCode[%c]
991e50 MonitorFailedNum=%d
991f38 set_fs_safe_mode at LINE =%d pffd =0x%llx
```

### 3.2 字符串寻址机制

ARM64 使用 PC 相对寻址加载字符串：

```assembly
ADRP X0, #0x991000          ; 加载字符串页面地址
ADD X0, X0, #0xD40          ; 加载页面内偏移
; X0 现在包含字符串地址 0x991D40
```

**问题：** ZTE 内核使用 GOT (全局偏移表) 或间接引用，ADRP+ADD 对无法直接找到。

### 3.3 函数定位方法

通过反汇编找到函数序言：

```assembly
; set_fs_safe_mode 函数入口 (偏移 0x47991C)
0x47991C: STP X29, X30, [SP, #-0x60]!  ; 保存寄存器，分配栈空间
0x479920: MOV X29, SP                  ; 设置帧指针
0x479924: STP X19, X20, [SP, #0x10]   ; 保存 callee-saved 寄存器
; ... 函数体 ...
0x479A3C: LDP X29, X30, [SP], #0x60   ; 恢复寄存器
0x479A40: RET                          ; 返回
```

## 4. 内核补丁技术

### 4.1 补丁策略

**目标：** 阻止 `set_fs_safe_mode` 和 `conf_fs_write` 执行，防止写入 conf 分区。

**方法：** 在函数入口替换为 `RET` 指令，使函数立即返回。

### 4.2 关键补丁位置

#### 补丁 1: 诊断函数 (0x4798E0)

```assembly
; 原始代码
0x4798E0: ADRP X0, #0x991000    ; 加载字符串地址
0x4798E4: ADD X0, X0, #0xF20    ; 字符串偏移
0x4798E8: BL #printk             ; 打印诊断信息

; 补丁后
0x4798E0: RET                    ; 立即返回
```

**作用：** 阻止诊断信息打印，减少日志输出。

#### 补丁 2: NOP (0x479910)

```assembly
; 原始代码
0x479910: BL #conf_write         ; 调用 conf 写入函数

; 补丁后
0x479910: NOP                    ; 空操作
```

**作用：** 阻止特定的 conf 写入调用。

#### 补丁 3: set_fs_safe_mode 入口 (0x47991C)

```assembly
; 原始代码
0x47991C: STP X29, X30, [SP, #-0x60]!  ; 函数序言

; 补丁后
0x47991C: RET                           ; 立即返回
```

**作用：** 完全阻止 set_fs_safe_mode 函数执行。

#### 补丁 4: conf_fs_write 入口 (0x478E70)

```assembly
; 原始代码
0x478E70: STP X29, X30, [SP, #-0x80]!  ; 函数序言

; 补丁后
0x478E70: RET                           ; 立即返回
```

**作用：** 完全阻止 conf_fs_write 函数执行，防止所有 conf 分区写入。

### 4.3 补丁验证

使用 Python 验证补丁：

```python
import struct

def verify_patch(data, offset, expected):
    """验证指定偏移的补丁"""
    actual = struct.unpack('<I', data[offset:offset+4])[0]
    if actual == expected:
        print(f"✓ 0x{offset:06x}: 0x{actual:08x}")
        return True
    else:
        print(f"✗ 0x{offset:06x}: 期望 0x{expected:08x}, 实际 0x{actual:08x}")
        return False

# 验证所有补丁
patches = [
    (0x4798E0, 0xD65F03C0),  # RET
    (0x479910, 0xD503201F),  # NOP
    (0x47991C, 0xD65F03C0),  # RET
    (0x478E70, 0xD65F03C0),  # RET
]

for offset, expected in patches:
    verify_patch(kernel_data, offset, expected)
```

## 5. 二进制补丁实现

### 5.1 Python 补丁脚本

```python
import struct
import hashlib

def patch_boot_image(input_file, output_file, patches):
    """
    补丁 boot.img 文件
    
    参数:
        input_file: 输入 boot.img 路径
        output_file: 输出 boot.img 路径
        patches: 补丁列表 [(offset, original, patched), ...]
    """
    with open(input_file, 'rb') as f:
        data = bytearray(f.read())
    
    # 内核起始偏移
    kernel_offset = 0x800
    
    for offset, original, patched in patches:
        file_offset = kernel_offset + offset
        
        # 验证原始值
        actual = struct.unpack('<I', data[file_offset:file_offset+4])[0]
        if actual != original:
            print(f"警告: 0x{offset:06x} 原始值不匹配")
            print(f"  期望: 0x{original:08x}")
            print(f"  实际: 0x{actual:08x}")
        
        # 应用补丁
        struct.pack_into('<I', data, file_offset, patched)
        print(f"已补丁: 0x{offset:06x} -> 0x{patched:08x}")
    
    # 保存补丁后的文件
    with open(output_file, 'wb') as f:
        f.write(data)
    
    # 计算 MD5
    md5 = hashlib.md5(data).hexdigest()
    print(f"输出文件: {output_file}")
    print(f"MD5: {md5}")

# 定义补丁
patches = [
    (0x4798E0, 0x900028C0, 0xD65F03C0),  # 诊断函数 -> RET
    (0x479910, 0x97EEF8E2, 0xD503201F),  # conf 写入调用 -> NOP
    (0x47991C, 0xA9BA7BFD, 0xD65F03C0),  # set_fs_safe_mode -> RET
    (0x478E70, 0xA9B87BFD, 0xD65F03C0),  # conf_fs_write -> RET
]

# 执行补丁
patch_boot_image(
    '/tmp/boot_cma16_patched.bin',
    '/tmp/boot_cma16_patched_v3.bin',
    patches
)
```

### 5.2 补丁原理

**RET 指令编码：** `0xD65F03C0`

```assembly
; ARM64 RET 指令格式
; 31-25: 1101011 (固定)
; 24-21: 0110 (RET)
; 20-16: 11111 (Rn = X30)
; 15-10: 000000 (保留)
; 9-5: 00000 (保留)
; 4-0: 00000 (保留)
; 总计: 0xD65F03C0
```

**NOP 指令编码：** `0xD503201F`

```assembly
; ARM64 NOP 指令
; 实际是 HINT #0 指令的别名
; 编码: 0xD503201F
```

## 6. 验证方法

### 6.1 文件完整性验证

```python
import hashlib

def verify_boot_image(file_path, expected_md5):
    """验证 boot.img 文件完整性"""
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # 检查 ZTE 魔数
    if data[0:4] != b'\x55\x66\x77\x88':
        print("错误: 无效的 ZTE 魔数")
        return False
    
    # 检查 Android 魔数
    if data[96:104] != b'ANDROID!':
        print("错误: 无效的 Android 魔数")
        return False
    
    # 验证 MD5
    actual_md5 = hashlib.md5(data).hexdigest()
    if actual_md5 != expected_md5:
        print(f"错误: MD5 不匹配")
        print(f"  期望: {expected_md5}")
        print(f"  实际: {actual_md5}")
        return False
    
    print("✓ 验证通过")
    return True
```

### 6.2 补丁验证

```python
def verify_patches(file_path, patches):
    """验证所有补丁是否正确应用"""
    with open(file_path, 'rb') as f:
        data = f.read()
    
    kernel_offset = 0x800
    all_ok = True
    
    for offset, expected, desc in patches:
        file_offset = kernel_offset + offset
        actual = struct.unpack('<I', data[file_offset:file_offset+4])[0]
        
        if actual == expected:
            print(f"✓ 0x{offset:06x}: {desc}")
        else:
            print(f"✗ 0x{offset:06x}: {desc}")
            print(f"  期望: 0x{expected:08x}")
            print(f"  实际: 0x{actual:08x}")
            all_ok = False
    
    return all_ok
```

## 7. 刷入方法

### 7.1 通过 ADB 刷入

```bash
# 1. 推送文件到设备
adb push boot_cma16_patched_v3.bin /tmp/

# 2. 刷入 boot 分区
adb shell "dd if=/tmp/boot_cma16_patched_v3.bin of=/dev/block/boot bs=4096"

# 3. 验证刷入
adb shell "dd if=/dev/block/boot bs=12959159 count=1 | md5sum"

# 4. 重启设备
adb reboot
```

### 7.2 通过 fastboot 刷入

```bash
# 1. 进入 fastboot 模式
adb reboot bootloader

# 2. 刷入 boot 分区
fastboot flash boot boot_cma16_patched_v3.bin

# 3. 重启设备
fastboot reboot
```

## 8. 故障排除

### 8.1 常见问题

**问题 1: MD5 不匹配**
- 原因: boot 分区大小与文件不同
- 解决: 使用 `dd` 读取相同字节数进行比较

**问题 2: 设备无法启动**
- 原因: 补丁位置错误或内核损坏
- 解决: 使用备份的 boot.img 恢复

**问题 3: 补丁未生效**
- 原因: 内核缓存或重启后丢失
- 解决: 确认补丁已正确应用并重启

### 8.2 恢复方法

```bash
# 使用 OTA 恢复
adb shell "dd if=/cache/upgrade/ota.zip of=/dev/block/boot bs=4096"
```

## 9. 技术要点

### 9.1 ARM64 指令编码

| 指令 | 编码 | 描述 |
|------|------|------|
| RET | 0xD65F03C0 | 返回到 X30 |
| NOP | 0xD503201F | 空操作 |
| STP | 可变 | 保存寄存器对 |
| LDP | 可变 | 加载寄存器对 |
| ADRP | 可变 | 加载页面地址 |
| BL | 可变 | 调用子程序 |

### 9.2 内存布局

```
内核加载地址: 0x40008000
文本偏移: 0x8000
内核入口: 0x40008000 + 0x8000 = 0x40010000
```

### 9.3 分区布局

```
/dev/block/boot      - 启动分区 (内核 + Ramdisk)
/dev/block/system    - 系统分区
/dev/block/conf      - 配置分区
/dev/block/recovery  - 恢复分区
```

## 10. 总结

本文档详细记录了 ZTE B860AV1.1-T2 boot.img 的逆向工程过程，包括：

1. ZTE 特有格式解析
2. ARM64 内核分析
3. 字符串定位技术
4. 函数识别方法
5. 二进制补丁技术
6. 验证和刷入方法

通过这些技术，成功禁用了 `set_fs_safe_mode` 和 `conf_fs_write` 函数，防止了 conf 分区的写入操作。

---

**作者:** Xiaomi MiMo  
**日期:** 2026-07-26  
**版本:** 1.0
