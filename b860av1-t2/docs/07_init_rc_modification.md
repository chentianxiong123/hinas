# Init.rc 改造与 Ramdisk 解包

## 目标

修改 init.rc，删除 Android 服务，添加纯 Linux 启动钩子。

## Ramdisk 解包

```bash
# 提取 ramdisk（从 boot.img）
python3 -c "
import struct
with open('boot.img','rb') as f: data = f.read()
idx = 0x60  # ANDROID! header
ramdisk_size = struct.unpack('<I', data[idx+16:idx+20])[0]
page_size = struct.unpack('<I', data[idx+36:idx+40])[0]
kernel_size = struct.unpack('<I', data[idx+8:idx+12])[0]
ramdisk_off = idx + page_size + kernel_size
open('ramdisk.img','wb').write(data[ramdisk_off:ramdisk_off+ramdisk_size])
"

# 解压 gzip
python3 -c "
import zlib
with open('ramdisk.img','rb') as f: data = f.read()
dec = zlib.decompressobj(-zlib.MAX_WBITS)
open('ramdisk.cpio','wb').write(dec.decompress(data[12:]))
"

# 解包 cpio
mkdir ramdisk_work && cd ramdisk_work
cpio -idm < ../ramdisk.cpio
```

## Ramdisk 重打包

```bash
find . | cpio -o -H newc > ../ramdisk_new.cpio
gzip -9 < ../ramdisk_new.cpio > ../ramdisk_new.img
```

## 踩坑：DTB 偏移变化

重打包 ramdisk 后大小变了，导致 DTB 偏移改变，u-boot 找不到 DTB。

**解决：** 不改 ramdisk，只改 DTB。或者保持 ramdisk 原大小（补零）。

## Init.rc 关键修改

### 注释掉 class_start

```
# 原版
class_start core
class_start main

# 改后
class_start core
# class_start main
```

`class_start main` 启动所有 class=main 的服务（zygote、surfaceflinger 等）。注释掉就全部不启动。

### 注释掉 Android 服务

```
# service servicemanager /system/bin/servicemanager
# service surfaceflinger /system/bin/surfaceflinger
# service zygote /system/bin/app_process ...
# service drm /system/bin/drmserver
# service media /system/bin/mediaserver
# service bootanim /system/bin/bootanimation
# service installd /system/bin/installd
# service keystore /system/bin/keystore
```

### 添加 Linux 服务

```
service linux_init /system/bin/sh /system/bin/linux_init.sh
    class core
    oneshot
```

### 清理 ZTE 文件

```
# zte_init.rc - 清空，不再导入 zte_middleware.rc
# zte_middleware.rc - 清空
```

### 删除 GPU 驱动加载

```
# insmod /boot/mali.ko mali_debug_level=1
```

## linux_init.sh 脚本

脚本放在 `/system/bin/`（system 分区），不在 ramdisk 里：

```bash
#!/system/bin/sh
sleep 10
insmod /system/lib/modules/8189fs.ko
ifconfig wlan0 up
wpa_supplicant -B -i wlan0 -c /data/wpa.conf
dhcpcd wlan0
dropbear -p 22
```

## 未完成

init.rc 改造方案未实际验证。最终采用 DTB-only 方案（只改 CMA，不改 ramdisk）。
