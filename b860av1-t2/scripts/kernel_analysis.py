#!/usr/bin/env python3
"""
ZTE B860AV1.1-T2 内核分析脚本
用于分析 ARM64 内核，定位函数和字符串
"""

import struct
import sys
import hashlib


def extract_kernel(boot_img, output_file):
    """从 boot.img 提取内核"""
    with open(boot_img, 'rb') as f:
        data = f.read()
    
    # 检查 ZTE 魔数
    if data[0:4] != b'\x55\x66\x77\x88':
        raise ValueError("无效的 ZTE 魔数")
    
    # 检查 Android 魔数
    if data[96:104] != b'ANDROID!':
        raise ValueError("无效的 Android 魔数")
    
    # 提取内核 (从偏移 0x800 开始)
    kernel_offset = 0x800
    kernel_data = data[kernel_offset:]
    
    # 保存内核
    with open(output_file, 'wb') as f:
        f.write(kernel_data)
    
    print(f"内核已提取到: {output_file}")
    print(f"内核大小: {len(kernel_data)} 字节")
    print(f"MD5: {hashlib.md5(kernel_data).hexdigest()}")
    
    return kernel_data


def find_strings(kernel_file, pattern):
    """查找内核中的字符串"""
    import subprocess
    
    result = subprocess.run(
        ['strings', '-t', 'x', kernel_file],
        capture_output=True,
        text=True
    )
    
    strings = []
    for line in result.stdout.split('\n'):
        if pattern.lower() in line.lower():
            parts = line.split(' ', 1)
            if len(parts) == 2:
                offset = int(parts[0], 16)
                string = parts[1]
                strings.append((offset, string))
    
    return strings


def find_string_references(kernel_data, string_offset):
    """查找引用特定字符串的代码"""
    target_page = string_offset & ~0xFFF
    target_offset = string_offset & 0xFFF
    
    refs = []
    i = 0
    while i < len(kernel_data) - 8:
        val = struct.unpack('<I', kernel_data[i:i+4])[0]
        
        # ADRP Xn, #target_page
        if (val & 0x9F000000) == 0x90000000:
            Rd = val & 0x1F
            immhi = (val >> 5) & 0x7FFFF
            immlo = (val >> 29) & 0x3
            imm = (immhi << 2) | immlo
            if imm & 0x100000:
                imm -= 0x200000
            adrp_page = ((i & ~0xFFF) + (imm << 12)) & 0xFFFFFFFF
            
            if adrp_page == target_page:
                # ADD Xn, Xn, #target_offset
                val2 = struct.unpack('<I', kernel_data[i+4:i+8])[0]
                if (val2 & 0xFFC00000) == 0x91000000:
                    imm12 = (val2 >> 10) & 0xFFF
                    if imm12 == target_offset:
                        refs.append(i)
        i += 4
    
    return refs


def find_function_prologue(kernel_data, start_offset):
    """向前查找函数序言"""
    i = start_offset
    while i > 0:
        val = struct.unpack('<I', kernel_data[i:i+4])[0]
        
        # STP X29, X30, [SP, #imm]!
        if (val & 0x7FC00000) == 0x29800000:
            return i
        
        i -= 4
    return None


def find_function_end(kernel_data, start_offset):
    """向后查找函数结束"""
    i = start_offset
    while i < len(kernel_data):
        val = struct.unpack('<I', kernel_data[i:i+4])[0]
        
        # RET 指令
        if val == 0xD65F03C0:
            return i
        
        i += 4
    return None


def disassemble_function(kernel_data, start, end):
    """反汇编函数"""
    print(f"\n函数反汇编 (0x{start:06x} - 0x{end:06x}):")
    print("-" * 60)
    
    i = start
    while i <= end:
        val = struct.unpack('<I', kernel_data[i:i+4])[0]
        
        if val == 0xD65F03C0:
            print(f"0x{i:06x}: RET")
        elif val == 0xD503201F:
            print(f"0x{i:06x}: NOP")
        elif (val & 0x7FC00000) == 0x29800000:
            Rt = val & 0x1F
            Rt2 = (val >> 10) & 0x1F
            imm7 = (val >> 15) & 0x7F
            if imm7 & 0x40:
                imm7 -= 0x80
            offset = imm7 * 8
            print(f"0x{i:06x}: STP X{Rt}, X{Rt2}, [SP, #{offset}]!")
        elif (val & 0x9F000000) == 0x90000000:
            Rd = val & 0x1F
            immhi = (val >> 5) & 0x7FFFF
            immlo = (val >> 29) & 0x3
            imm = (immhi << 2) | immlo
            if imm & 0x100000:
                imm -= 0x200000
            target = ((i & ~0xFFF) + (imm << 12)) & 0xFFFFFFFF
            print(f"0x{i:06x}: ADRP X{Rd}, #0x{target:08x}")
        elif (val & 0xFF000000) == 0x91000000:
            Rd = val & 0x1F
            Rn = (val >> 5) & 0x1F
            imm12 = (val >> 10) & 0xFFF
            print(f"0x{i:06x}: ADD X{Rd}, X{Rn}, #0x{imm12:x}")
        elif (val & 0xFC000000) == 0x94000000:
            imm26 = val & 0x03FFFFFF
            if imm26 & 0x2000000:
                imm26 -= 0x4000000
            target = i + 4 + imm26 * 4
            print(f"0x{i:06x}: BL #0x{target:x}")
        elif (val & 0xFC000000) == 0x14000000:
            imm26 = val & 0x03FFFFFF
            if imm26 & 0x2000000:
                imm26 -= 0x4000000
            target = i + 4 + imm26 * 4
            print(f"0x{i:06x}: B #0x{target:x}")
        else:
            print(f"0x{i:06x}: .word 0x{val:08x}")
        
        i += 4


def main():
    if len(sys.argv) < 3:
        print("用法:")
        print(f"  {sys.argv[0]} extract <boot.img> <output.bin>")
        print(f"  {sys.argv[0]} strings <kernel.bin> <pattern>")
        print(f"  {sys.argv[0]} analyze <kernel.bin> <string_offset>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'extract':
        if len(sys.argv) < 4:
            print("用法: python3 kernel_analysis.py extract <boot.img> <output.bin>")
            sys.exit(1)
        extract_kernel(sys.argv[2], sys.argv[3])
    
    elif command == 'strings':
        if len(sys.argv) < 4:
            print("用法: python3 kernel_analysis.py strings <kernel.bin> <pattern>")
            sys.exit(1)
        results = find_strings(sys.argv[2], sys.argv[3])
        print(f"\n找到 {len(results)} 个匹配:")
        for offset, string in results:
            print(f"  0x{offset:06x}: {string[:80]}")
    
    elif command == 'analyze':
        if len(sys.argv) < 4:
            print("用法: python3 kernel_analysis.py analyze <kernel.bin> <string_offset>")
            sys.exit(1)
        
        with open(sys.argv[2], 'rb') as f:
            kernel_data = f.read()
        
        string_offset = int(sys.argv[3], 16)
        
        print(f"分析字符串引用: 0x{string_offset:06x}")
        refs = find_string_references(kernel_data, string_offset)
        
        print(f"\n找到 {len(refs)} 个引用:")
        for ref in refs:
            prologue = find_function_prologue(kernel_data, ref)
            end = find_function_end(kernel_data, ref)
            
            print(f"\n  引用位置: 0x{ref:06x}")
            if prologue:
                print(f"  函数起始: 0x{prologue:06x}")
            if end:
                print(f"  函数结束: 0x{end:06x}")
            
            if prologue and end:
                disassemble_function(kernel_data, prologue, min(end, prologue + 100))
    
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
