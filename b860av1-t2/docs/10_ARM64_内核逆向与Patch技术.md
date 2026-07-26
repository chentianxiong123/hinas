# ARM64 内核逆向与 Patch 技术

## 概述

本文档详细介绍了 ARM64 内核的逆向分析方法和二进制补丁技术，以 ZTE B860AV1.1-T2 机顶盒为例。

## 1. ARM64 架构基础

### 1.1 寄存器

ARM64 有 31 个通用寄存器：

```assembly
X0-X7     ; 参数寄存器 (caller-saved)
X8        ; 间接结果寄存器
X9-X15    ; 临时寄存器 (caller-saved)
X16-X17   ; IP0/IP1 (过程内调用)
X18       ; 平台寄存器
X19-X28   ; callee-saved 寄存器
X29       ; 帧指针 (FP)
X30       ; 链接寄存器 (LR)
SP        ; 栈指针
PC        ; 程序计数器
```

### 1.2 指令格式

ARM64 指令固定 32 位长度：

```
31      24 23      16 15       8 7        0
+--------+--------+--------+--------+
| 操作码 | 操作数1 | 操作数2 | 操作数3 |
+--------+--------+--------+--------+
```

### 1.3 寻址模式

**立即数寻址：**
```assembly
MOV X0, #42          ; X0 = 42
ADD X0, X1, #10      ; X0 = X1 + 10
```

**寄存器寻址：**
```assembly
ADD X0, X1, X2       ; X0 = X1 + X2
```

**PC 相对寻址：**
```assembly
ADRP X0, #page       ; X0 = PC 页面地址
ADD X0, X0, #offset  ; X0 += 页面内偏移
```

## 2. 函数调用约定

### 2.1 AAPCS64 标准

ARM64 遵循 AAPCS64 调用约定：

```assembly
; 函数序言
STP X29, X30, [SP, #-0x60]!  ; 保存帧指针和返回地址
MOV X29, SP                  ; 设置帧指针
STP X19, X20, [SP, #0x10]   ; 保存 callee-saved 寄存器

; 函数体
MOV X0, #1                   ; 第一个参数
MOV X1, #2                   ; 第二个参数
BL #function                 ; 调用函数

; 函数尾声
LDP X19, X20, [SP, #0x10]   ; 恢复 callee-saved 寄存器
LDP X29, X30, [SP], #0x60   ; 恢复帧指针和返回地址
RET                          ; 返回
```

### 2.2 参数传递

```assembly
; 前 8 个参数通过 X0-X7 传递
MOV X0, #arg1        ; 第一个参数
MOV X1, #arg2        ; 第二个参数
MOV X2, #arg3        ; 第三个参数
; ...
MOV X7, #arg8        ; 第八个参数

; 返回值通过 X0 返回
; X0 = 返回值
```

### 2.3 栈帧结构

```
高地址
+------------------+
| 调用者的帧       |
+------------------+
| 返回地址 (X30)   |
+------------------+
| 帧指针 (X29)     |
+------------------+
| 本地变量         |
+------------------+
| callee-saved 寄存器|
+------------------+
低地址 (SP 指向这里)
```

## 3. 内核函数分析

### 3.1 函数识别

**方法 1: 查找函数序言**

```python
def find_function_prologue(data, start, end):
    """查找函数序言 (STP X29, X30, ...)"""
    i = start
    while i < end:
        val = struct.unpack('<I', data[i:i+4])[0]
        
        # STP X29, X30, [SP, #imm]!
        if (val & 0x7FC00000) == 0x29800000:
            return i
        
        i += 4
    return None
```

**方法 2: 查找字符串引用**

```python
def find_string_reference(data, string_addr):
    """查找引用特定字符串的代码"""
    target_page = string_addr & ~0xFFF
    target_offset = string_addr & 0xFFF
    
    refs = []
    i = 0
    while i < len(data) - 8:
        # 查找 ADRP Xn, #target_page
        val = struct.unpack('<I', data[i:i+4])[0]
        if (val & 0x9F000000) == 0x90000000:
            Rd = val & 0x1F
            immhi = (val >> 5) & 0x7FFFF
            immlo = (val >> 29) & 0x3
            imm = (immhi << 2) | immlo
            if imm & 0x100000:
                imm -= 0x200000
            adrp_page = ((i & ~0xFFF) + (imm << 12)) & 0xFFFFFFFF
            
            if adrp_page == target_page:
                # 查找 ADD Xn, Xn, #target_offset
                val2 = struct.unpack('<I', data[i+4:i+8])[0]
                if (val2 & 0xFFC00000) == 0x91000000:
                    imm12 = (val2 >> 10) & 0xFFF
                    if imm12 == target_offset:
                        refs.append(i)
        i += 4
    
    return refs
```

### 3.2 函数边界检测

```python
def find_function_end(data, start):
    """查找函数结束位置 (RET 指令)"""
    i = start
    while i < len(data):
        val = struct.unpack('<I', data[i:i+4])[0]
        
        # RET 指令
        if val == 0xD65F03C0:
            return i
        
        # 或者 LDP + RET 序列
        if (val & 0x7FC00000) == 0x28C00000:  # LDP
            next_val = struct.unpack('<I', data[i+4:i+8])[0]
            if next_val == 0xD65F03C0:  # RET
                return i + 4
        
        i += 4
    return None
```

### 3.3 反汇编输出

```python
def disassemble_arm64(data, start, end):
    """反汇编 ARM64 代码"""
    i = start
    while i < end:
        val = struct.unpack('<I', data[i:i+4])[0]
        
        # 解码指令
        if val == 0xD65F03C0:
            print(f"0x{i:06x}: RET")
        elif val == 0xD503201F:
            print(f"0x{i:06x}: NOP")
        elif (val & 0x7FC00000) == 0x29800000:
            # STP
            Rt = val & 0x1F
            Rt2 = (val >> 10) & 0x1F
            imm7 = (val >> 15) & 0x7F
            if imm7 & 0x40:
                imm7 -= 0x80
            offset = imm7 * 8
            print(f"0x{i:06x}: STP X{Rt}, X{Rt2}, [SP, #{offset}]!")
        elif (val & 0x9F000000) == 0x90000000:
            # ADRP
            Rd = val & 0x1F
            immhi = (val >> 5) & 0x7FFFF
            immlo = (val >> 29) & 0x3
            imm = (immhi << 2) | immlo
            if imm & 0x100000:
                imm -= 0x200000
            target = ((i & ~0xFFF) + (imm << 12)) & 0xFFFFFFFF
            print(f"0x{i:06x}: ADRP X{Rd}, #0x{target:08x}")
        elif (val & 0xFF000000) == 0x91000000:
            # ADD
            Rd = val & 0x1F
            Rn = (val >> 5) & 0x1F
            imm12 = (val >> 10) & 0xFFF
            print(f"0x{i:06x}: ADD X{Rd}, X{Rn}, #0x{imm12:x}")
        elif (val & 0xFC000000) == 0x94000000:
            # BL
            imm26 = val & 0x03FFFFFF
            if imm26 & 0x2000000:
                imm26 -= 0x4000000
            target = i + 4 + imm26 * 4
            print(f"0x{i:06x}: BL #0x{target:x}")
        else:
            print(f"0x{i:06x}: .word 0x{val:08x}")
        
        i += 4
```

## 4. 二进制补丁技术

### 4.1 补丁类型

**类型 1: 函数禁用 (RET)**

```python
def patch_function_disable(data, offset):
    """禁用函数 - 替换序言为 RET"""
    # 保存原始值
    original = struct.unpack('<I', data[offset:offset+4])[0]
    
    # 替换为 RET
    struct.pack_into('<I', data, offset, 0xD65F03C0)
    
    return original
```

**类型 2: 调用禁用 (NOP)**

```python
def patch_call_disable(data, offset):
    """禁用函数调用 - 替换 BL 为 NOP"""
    original = struct.unpack('<I', data[offset:offset+4])[0]
    
    # 替换为 NOP
    struct.pack_into('<I', data, offset, 0xD503201F)
    
    return original
```

**类型 3: 条件跳转修改**

```python
def patch_conditional_branch(data, offset, always_jump=False):
    """修改条件跳转"""
    val = struct.unpack('<I', data[offset:offset+4])[0]
    
    if always_jump:
        # 将条件跳转改为无条件跳转
        # CBZ/CBNZ -> B
        imm19 = (val >> 5) & 0x7FFFF
        if imm19 & 0x40000:
            imm19 -= 0x80000
        target = offset + 4 + imm19 * 4
        
        # 计算新的 B 指令
        imm26 = (target - offset - 4) // 4
        if imm26 < 0:
            imm26 += 0x4000000
        new_val = 0x14000000 | (imm26 & 0x03FFFFFF)
        
        struct.pack_into('<I', data, offset, new_val)
    
    return val
```

### 4.2 高级补丁

**类型 4: 函数钩子**

```python
def patch_function_hook(data, target_offset, hook_offset):
    """
    钩子函数 - 将函数调用重定向到钩子函数
    
    参数:
        data: 内核数据
        target_offset: 目标函数偏移
        hook_offset: 钩子函数偏移
    """
    # 计算相对偏移
    rel_offset = (hook_offset - target_offset - 4) // 4
    
    # 生成 BL 指令
    if rel_offset < 0:
        rel_offset += 0x4000000
    bl_insn = 0x94000000 | (rel_offset & 0x03FFFFFF)
    
    # 保存原始指令
    original = struct.unpack('<I', data[target_offset:target_offset+4])[0]
    
    # 应用钩子
    struct.pack_into('<I', data, target_offset, bl_insn)
    
    return original
```

### 4.3 补丁验证

```python
def verify_patch(data, offset, expected):
    """验证补丁是否正确应用"""
    actual = struct.unpack('<I', data[offset:offset+4])[0]
    return actual == expected

def verify_all_patches(data, patches):
    """验证所有补丁"""
    all_ok = True
    for offset, expected, desc in patches:
        if verify_patch(data, offset, expected):
            print(f"✓ 0x{offset:06x}: {desc}")
        else:
            print(f"✗ 0x{offset:06x}: {desc}")
            all_ok = False
    return all_ok
```

## 5. 内核模块分析

### 5.1 模块加载

```bash
# 查看已加载模块
lsmod

# 加载模块
insmod /system/lib/modules/8189fs.ko

# 卸载模块
rmmod 8189fs
```

### 5.2 模块依赖

```python
def analyze_module_dependencies(module_file):
    """分析模块依赖关系"""
    import subprocess
    
    # 使用 modinfo 查看模块信息
    result = subprocess.run(
        ['modinfo', module_file],
        capture_output=True,
        text=True
    )
    
    # 解析依赖
    for line in result.stdout.split('\n'):
        if line.startswith('depends:'):
            deps = line.split(':')[1].strip()
            if deps:
                return deps.split(',')
    
    return []
```

### 5.3 模块符号表

```python
def extract_module_symbols(module_file):
    """提取模块符号表"""
    import subprocess
    
    # 使用 nm 查看符号
    result = subprocess.run(
        ['nm', module_file],
        capture_output=True,
        text=True
    )
    
    symbols = {}
    for line in result.stdout.split('\n'):
        if line:
            parts = line.split()
            if len(parts) >= 3:
                addr, type, name = parts[0], parts[1], parts[2]
                symbols[name] = {
                    'address': int(addr, 16),
                    'type': type
                }
    
    return symbols
```

## 6. 调试技术

### 6.1 内核日志

```bash
# 查看内核日志
dmesg

# 实时查看日志
logcat -s kernel

# 查看特定模块日志
dmesg | grep 8189fs
```

### 6.2 内存分析

```python
def analyze_kernel_memory(dump_file):
    """分析内核内存转储"""
    with open(dump_file, 'rb') as f:
        data = f.read()
    
    # 查找内核符号
    symbols = {}
    
    # 查找字符串表
    strtab_start = data.find(b'.strtab')
    if strtab_start != -1:
        # 解析字符串表
        pass
    
    # 查找符号表
    symtab_start = data.find(b'.symtab')
    if symtab_start != -1:
        # 解析符号表
        pass
    
    return symbols
```

### 6.3 寄存器分析

```python
def analyze_registers(reg_dump):
    """分析寄存器转储"""
    registers = {}
    
    # 解析寄存器值
    for i in range(31):
        reg_name = f'X{i}'
        if reg_name in reg_dump:
            registers[reg_name] = reg_dump[reg_name]
    
    # 特殊寄存器
    if 'SP' in reg_dump:
        registers['SP'] = reg_dump['SP']
    if 'PC' in reg_dump:
        registers['PC'] = reg_dump['PC']
    if 'X29' in reg_dump:
        registers['FP'] = reg_dump['X29']
    if 'X30' in reg_dump:
        registers['LR'] = reg_dump['X30']
    
    return registers
```

## 7. 实战案例

### 7.1 案例 1: 禁用 set_fs_safe_mode

**目标：** 阻止 set_fs_safe_mode 函数执行

**分析：**
1. 找到函数入口: 0x47991C
2. 函数序言: `STP X29, X30, [SP, #-0x60]!`
3. 补丁: 替换为 `RET`

**实现：**
```python
# 原始指令
original = 0xA9BA7BFD  # STP X29, X30, [SP, #-0x60]!

# 补丁指令
patched = 0xD65F03C0   # RET

# 应用补丁
struct.pack_into('<I', kernel_data, 0x47991C, patched)
```

**验证：**
```bash
# 检查补丁是否生效
dd if=/dev/block/boot bs=12959159 count=1 | md5sum
# 应该返回: aeecc771612ac4c4ec22ac0d188d6d27
```

### 7.2 案例 2: 禁用 conf_fs_write

**目标：** 阻止所有 conf 分区写入

**分析：**
1. 找到函数入口: 0x478E70
2. 函数序言: `STP X29, X30, [SP, #-0x80]!`
3. 补丁: 替换为 `RET`

**实现：**
```python
# 原始指令
original = 0xA9B87BFD  # STP X29, X30, [SP, #-0x80]!

# 补丁指令
patched = 0xD65F03C0   # RET

# 应用补丁
struct.pack_into('<I', kernel_data, 0x478E70, patched)
```

**验证：**
```bash
# 检查 MonitorFailedNum 是否还在增加
strings /dev/block/conf | grep MonitorFailedNum
# 应该看到稳定的值，不再增加
```

## 8. 工具推荐

### 8.1 逆向工程工具

| 工具 | 用途 | 命令 |
|------|------|------|
| objdump | 反汇编 | `objdump -d kernel.bin` |
| strings | 字符串提取 | `strings kernel.bin` |
| radare2 | 交互式分析 | `r2 kernel.bin` |
| Ghidra | 反编译 | GUI 工具 |
| IDA Pro | 专业逆向 | 商业工具 |

### 8.2 二进制工具

| 工具 | 用途 | 命令 |
|------|------|------|
| dd | 二进制操作 | `dd if=file bs=1 skip=offset` |
| xxd | 十六进制查看 | `xxd file` |
| hexdump | 十六进制转储 | `hexdump -C file` |
| python | 脚本处理 | `python3 script.py` |

### 8.3 调试工具

| 工具 | 用途 | 命令 |
|------|------|------|
| gdb | 调试器 | `gdb ./program` |
| strace | 系统调用跟踪 | `strace ./program` |
| ltrace | 库调用跟踪 | `ltrace ./program` |
| dmesg | 内核日志 | `dmesg` |

## 9. 最佳实践

### 9.1 安全注意事项

1. **备份原始文件** - 始终保留未修改的备份
2. **验证补丁** - 刷入前验证所有补丁
3. **测试恢复** - 确保有恢复方法
4. **记录更改** - 详细记录所有修改

### 9.2 工作流程

```
1. 分析目标
   ├── 提取内核
   ├── 查找字符串
   ├── 定位函数
   └── 分析调用链

2. 设计补丁
   ├── 确定补丁点
   ├── 选择补丁类型
   ├── 计算指令编码
   └── 验证逻辑

3. 实现补丁
   ├── 编写脚本
   ├── 应用补丁
   ├── 验证结果
   └── 生成文件

4. 测试部署
   ├── 刷入设备
   ├── 验证功能
   ├── 检查稳定性
   └── 记录结果
```

## 10. 总结

本文档介绍了 ARM64 内核逆向和补丁技术，包括：

1. ARM64 架构基础
2. 函数调用约定
3. 内核函数分析方法
4. 二进制补丁技术
5. 调试和验证方法

通过这些技术，可以深入理解内核行为并进行精确的二进制修改。

---

**作者:** Xiaomi MiMo  
**日期:** 2026-07-26  
**版本:** 1.0
