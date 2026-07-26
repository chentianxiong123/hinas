# Boot.img 结构与 DTB 修改

## Boot.img 结构

ZTE 自定义头 + Android 标准格式：

```
0x0000-0x005F  ZTE 头 (magic: 55667788, name: norm, version: V815001)
0x0060-0x085F  Android 头 (magic: ANDROID!, kernel_size, ramdisk_size, page_size, SHA256 id)
0x0860-0xB0BFEF  内核 (11.3MB)
0xB0BFF0-0xC4399F  Ramdisk (1.2MB, gzip 压缩的 cpio)
0xC439A0-0xC5399F  DTB ×3 (设备树, 每个约29KB)
```

## DTB（设备树）

DTB 格式：FDT (Flattened Device Tree)
- Magic: 0xd00dfeed
- 结构：FDT_BEGIN_NODE → FDT_PROP → FDT_END_NODE

Boot.img 包含 3 个 DTB（不同硬件配置）：
- DTB1 @ 0xC439A0 (29803 bytes)
- DTB2 @ 0xC4B9A0 (29880 bytes)
- DTB3 @ 0xC539A0 (29744 bytes)

## CMA 内存预留

DTB 的 `reserved-memory` 节点定义了 CMA 区域：

```dts
reserved-memory {
    multimedia_region {
        compatible = "shared-dma-pool";
        reusable;
        size = <0x11000000>;  // 272 MB
        linux,phandle = <0x05>;
        phandle = <0x05>;
    };
};
```

## 踩坑：改 DTB 导致 u-boot 卡死

**第一次尝试：** 改了 ramdisk 大小，导致 DTB 偏移改变，u-boot 找不到 DTB 卡死。

**原因：** u-boot 用固定的偏移读取 DTB。ramdisk 大小变了，DTB 位置变了，但 u-boot 还是读原来的偏移。

**解决：** 只改 DTB 内容，不改 ramdisk 大小。文件大小必须和原版一致。

## 踩坑：DTB 没有 CRC32

DTB 的 offset 4-7 是 totalsize（总大小），不是 CRC32。第一次误认为是 CRC，写错了值导致 DTB 坏了。

正确格式：
```
0x00-0x03: magic (0xd00dfeed)
0x04-0x07: totalsize
0x08-0x0B: off_struct
0x0C-0x0F: off_strings
```

## 踩坑：CMA=0 导致内核 panic

设置 `multimedia_region size = 0` 后内核启动 panic：
```
Kernel panic - not syncing: Attempted to kill init! exitcode=0x0000000b
```

exitcode 0x0b = signal 11 (SIGSEGV)，init 段错误。某些驱动初始化需要 CMA 内存，分配失败导致崩溃。

**结论：** CMA 不能设为 0。最小可用值约 16MB。

## 最终方案

只改 DTB 的 `multimedia_region size`，其他不动：
- 原版：0x11000000 (272 MB)
- 改后：0x01000000 (16 MB)

差异仅 35 字节（3个 DTB 的 size 字段 + SHA256 hash）。

## 验证方法

```python
# 对比原版和改后的差异
python3 -c "
with open('original.img','rb') as f: orig = f.read()
with open('patched.img','rb') as f: patched = f.read()
diff = [(i,orig[i],patched[i]) for i in range(len(orig)) if orig[i]!=patched[i]]
print(f'差异: {len(diff)} 字节')
"
```
