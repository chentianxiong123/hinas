#!/usr/bin/env python3
"""
ZTE B860AV1.1-T2 内核补丁脚本
用于补丁 ARM64 内核，禁用特定函数
"""

import struct
import sys
import hashlib


# 补丁定义
PATCHES = [
    # (偏移, 原始值, 补丁值, 描述)
    (0x4798E0, 0x900028C0, 0xD65F03C0, "诊断函数 -> RET"),
    (0x479910, 0x97EEF8E2, 0xD503201F, "conf 写入调用 -> NOP"),
    (0x47991C, 0xA9BA7BFD, 0xD65F03C0, "set_fs_safe_mode -> RET"),
    (0x478E70, 0xA9B87BFD, 0xD65F03C0, "conf_fs_write -> RET"),
]

# 内核起始偏移
KERNEL_OFFSET = 0x800


def verify_header(data):
    """验证 boot.img 头部"""
    if data[0:4] != b'\x55\x66\x77\x88':
        print("错误: 无效的 ZTE 魔数")
        return False
    
    if data[96:104] != b'ANDROID!':
        print("错误: 无效的 Android 魔数")
        return False
    
    return True


def apply_patches(input_file, output_file, patches=None):
    """应用补丁到 boot.img"""
    if patches is None:
        patches = PATCHES
    
    with open(input_file, 'rb') as f:
        data = bytearray(f.read())
    
    # 验证头部
    if not verify_header(data):
        return None
    
    print(f"输入文件: {input_file}")
    print(f"文件大小: {len(data)} 字节")
    print()
    
    print("应用补丁:")
    all_ok = True
    
    for offset, original, patched, desc in patches:
        file_offset = KERNEL_OFFSET + offset
        
        # 验证原始值
        actual = struct.unpack('<I', data[file_offset:file_offset+4])[0]
        if actual != original:
            if actual == patched:
                print(f"  ✓ 0x{offset:06x}: {desc} (已补丁)")
                continue
            else:
                print(f"  ✗ 0x{offset:06x}: {desc}")
                print(f"    警告: 原始值不匹配")
                print(f"    期望: 0x{original:08x}")
                print(f"    实际: 0x{actual:08x}")
                all_ok = False
                continue
        
        # 应用补丁
        struct.pack_into('<I', data, file_offset, patched)
        print(f"  ✓ 0x{offset:06x}: {desc}")
    
    # 保存补丁后的文件
    with open(output_file, 'wb') as f:
        f.write(data)
    
    # 计算 MD5
    md5 = hashlib.md5(data).hexdigest()
    print()
    print(f"输出文件: {output_file}")
    print(f"MD5: {md5}")
    
    return md5


def verify_patches(file_path, patches=None):
    """验证所有补丁"""
    if patches is None:
        patches = PATCHES
    
    with open(file_path, 'rb') as f:
        data = f.read()
    
    print(f"验证文件: {file_path}")
    print()
    
    all_ok = True
    for offset, _, patched, desc in patches:
        file_offset = KERNEL_OFFSET + offset
        actual = struct.unpack('<I', data[file_offset:file_offset+4])[0]
        
        if actual == patched:
            print(f"  ✓ 0x{offset:06x}: {desc}")
        else:
            print(f"  ✗ 0x{offset:06x}: {desc}")
            print(f"    期望: 0x{patched:08x}")
            print(f"    实际: 0x{actual:08x}")
            all_ok = False
    
    return all_ok


def verify_file_integrity(file_path, expected_md5):
    """验证文件完整性"""
    with open(file_path, 'rb') as f:
        data = f.read()
    
    actual_md5 = hashlib.md5(data).hexdigest()
    
    if actual_md5 == expected_md5:
        print(f"✓ MD5 匹配: {actual_md5}")
        return True
    else:
        print(f"✗ MD5 不匹配")
        print(f"  期望: {expected_md5}")
        print(f"  实际: {actual_md5}")
        return False


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print(f"  {sys.argv[0]} patch <input.img> <output.img>")
        print(f"  {sys.argv[0]} verify <boot.img>")
        print(f"  {sys.argv[0]} md5 <file> <expected_md5>")
        print()
        print("补丁列表:")
        for offset, _, _, desc in PATCHES:
            print(f"  0x{offset:06x}: {desc}")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'patch':
        if len(sys.argv) < 4:
            print("用法: python3 patch_kernel.py patch <input.img> <output.img>")
            sys.exit(1)
        apply_patches(sys.argv[2], sys.argv[3])
    
    elif command == 'verify':
        if len(sys.argv) < 3:
            print("用法: python3 patch_kernel.py verify <boot.img>")
            sys.exit(1)
        result = verify_patches(sys.argv[2])
        print()
        if result:
            print("✓ 所有补丁验证通过")
        else:
            print("✗ 部分补丁验证失败")
            sys.exit(1)
    
    elif command == 'md5':
        if len(sys.argv) < 4:
            print("用法: python3 patch_kernel.py md5 <file> <expected_md5>")
            sys.exit(1)
        result = verify_file_integrity(sys.argv[2], sys.argv[3])
        if not result:
            sys.exit(1)
    
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
