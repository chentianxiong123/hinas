# 阶段五：OTA 分析与签名

## 5.1 OTA 包结构

### 文件位置

```
/tmp/ota.zip (258MB)
```

### 目录结构

```
META-INF/
├── CERT.RSA                    # PKCS#7 签名 (DER 格式)
├── CERT.SF                     # 签名文件
├── MANIFEST.MF                 # 清单文件
└── com/
    ├── android/
    │   ├── metadata            # 构建元数据
    │   └── otacert             # PEM 证书
    └── google/
        └── android/
            ├── update-binary   # 更新程序 (ARM ELF)
            └── updater-script  # 更新脚本

boot.img                        # 内核 + ramdisk + DTB
bootloader.img                  # U-boot
recovery/
└── recovery.img                # 恢复模式镜像

system/                         # 系统文件
├── app/                        # 应用 APK
├── bin/                        # 二进制
├── build.prop                  # 构建属性
├── etc/                        # 配置
├── fonts/                      # 字体
├── framework/                  # 框架 JAR
├── lib/                        # 动态库
├── media/                      # 媒体
├── preinstall/                 # 预装 APK
├── priv-app/                   # 系统应用
├── usr/                        # 用户数据
└── xbin/                       # 扩展二进制
```

## 5.2 updater-script 分析

### 完整脚本

```javascript
// 设备检查
getprop("ro.product.device") == "square" || abort("...");

// 进度显示
show_progress(1.000000, 0);

// 设置升级步骤
set_bootloader_env("upgrade_step", "3");

// 清除数据
delete_recursive("/data/dontpanic");
delete_recursive("/data/app-private");
delete_recursive("/data/internal-device");
delete_recursive("/data/dalvik-cache");
delete_recursive("/data/resource-cache");
delete_recursive("/data/lost+found");
delete_recursive("/data/drm");

set_progress(0.100000);

// 提取数据
package_extract_dir("data", "/data");

set_progress(0.200000);

// 格式化 system 分区
format("ext4", "EMMC", "/dev/block/system", "0", "/system");

// 挂载 system
mount("ext4", "EMMC", "/dev/block/system", "/system");

set_progress(0.300000);

// 提取 recovery
package_extract_dir("recovery", "/cache");

set_progress(0.400000);

// 提取 system
package_extract_dir("system", "/system");

set_progress(0.600000);

// 创建符号链接
symlink("Roboto-Bold.ttf", "/system/fonts/DroidSans-Bold.ttf");
symlink("Roboto-Regular.ttf", "/system/fonts/DroidSans.ttf");
symlink("busybox", "/system/xbin/[", "/system/xbin/[[", ...);
symlink("libGLESv2.so", "/system/lib/libGLESv3.so");
symlink("mksh", "/system/bin/sh");
symlink("toolbox", "/system/bin/cat", "/system/bin/chmod", ...);

set_progress(0.700000);
set_progress(0.800000);

// 设置权限
set_metadata_recursive("/system", "uid", 0, "gid", 0, ...);
set_metadata_recursive("/system/bin", "uid", 0, "gid", 2000, ...);
set_metadata("/system/bin/su", "uid", 0, "gid", 0, "mode", 06755, ...);

set_progress(0.900000);

// 刷入 boot.img
package_extract_file("boot.img", "/dev/block/boot");

// 刷入 bootloader
package_extract_file("bootloader.img", "/dev/block/mmcblk0boot0");

// 设置升级步骤
set_bootloader_env("upgrade_step", "1");
set_bootloader_env("force_auto_update", "false");

set_progress(1.000000);
```

### 关键操作

1. **格式化 /system** — 完全清除 system 分区
2. **提取 system 文件** — 从 OTA 复制到 /system
3. **创建符号链接** — busybox, toolbox 等
4. **设置权限** — 文件和目录权限
5. **刷入 boot.img** — 写入 boot 分区
6. **刷入 bootloader** — 写入 bootloader 分区

## 5.3 签名分析

### 签名结构

Android OTA 使用 JAR 签名格式：

```
META-INF/
├── MANIFEST.MF     # 清单：每个文件的 SHA-256 + SHA-1 摘要
├── CERT.SF         # 签名文件：MANIFEST.MF 的 SHA-256 摘要
└── CERT.RSA        # 签名：对 CERT.SF 的 PKCS#7 签名
```

### MANIFEST.MF 格式

```
Manifest-Version: 1.0
Created-By: 1.0 (Android SignApk)

Name: system/framework/am.jar
SHA-256-Digest: 22E0GwlAwXsmxRxijr5gjiS/3JZ4fXEKdMyHFZKBdGI=
SHA1-Digest: 46ymbSOrphOFavZx/tUEO9ZQ+28=

Name: system/xbin/ash
SHA-256-Digest: +hq9ljxeFImylXNIAvn1XzICGmWu6VdOpKP/K1ZCWrk=
SHA1-Digest: nEA3wVMmQNLYe7agvmLNi65s2OA=
...
```

### CERT.SF 格式

```
Signature-Version: 1.0
SHA-256-Digest-Manifest: LJFuQbxKgXKn6lTe61Kt+GV59+Fos17gWHf/dM+hMNU=
Created-By: 1.0 (Android SignApk)

Name: system/framework/am.jar
SHA-256-Digest: HMZCMwsXubERtryJ/gDCnmdNVZoKT46svkabcWWdGy0=

Name: system/xbin/ash
SHA-256-Digest: fd2srET58mhKOgjIGzW2BkK3In0t5STj8+ZUSxljiOw=
...
```

### CERT.RSA 格式

PKCS#7 SignedData，DER 编码。

### 原始签名信息

```
Subject: C=CN, ST=sccd, L=sccd, O=server, OU=server, CN=laoli
Issuer:  C=CN, ST=sccd, L=sccd, O=server, OU=server, CN=laoli
Serial:  0x1D9459AE
Valid:   2018-03-27 to 2237-04-08
```

## 5.4 OTA 修改

### 修改方法

1. 解压 OTA
2. 修改文件
3. 重新打包
4. 重新签名

### 签名方案

#### 方案 1: 使用 signapk.jar (需要 Java)

```bash
# 生成密钥
openssl genrsa -out testkey.pem 2048
openssl req -new -x509 -key testkey.pem -out testkey.x509.pem -days 10000

# 签名
java -jar signapk.jar -w testkey.x509.pem testkey.pem update.zip update_signed.zip
```

#### 方案 2: 使用 OpenSSL

```bash
# 生成 MANIFEST.MF
# 计算每个文件的 SHA-256 和 SHA-1

# 生成 CERT.SF
# 计算 MANIFEST.MF 的 SHA-256

# 生成 CERT.RSA
openssl smime -sign -in CERT.SF -out CERT.RSA -outform DER \
    -inkey testkey.pem -signer testkey.x509.pem -noattr -md sha256
```

#### 方案 3: 不签名

某些设备（特别是 userdebug 版本）接受未签名的 OTA。

### 实际尝试

由于没有 Java 环境，尝试了：
1. 不签名直接刷 — 被 recovery 拒绝
2. 使用 adb sideload — 需要 ADB 连接
3. 直接 dd 刷分区 — 最终采用的方案

## 5.5 直接刷分区

### 为什么选择直接刷

1. OTA 有签名验证，修改后无法通过
2. 直接 dd 绕过签名验证
3. 可以单独刷每个分区

### 刷入方法

```bash
# 刷入 boot
dd if=/storage/usb0/boot_cma16_patched.bin of=/dev/block/boot bs=4096 conv=fsync

# 刷入 conf
dd if=/storage/usb0/conf_fixed.bin of=/dev/block/conf bs=4096

# 刷入 system（如果需要）
# 需要先制作 system.img
```

### 制作 system.img

```bash
# 在电脑上
mkdir -p /tmp/system_clean
cd /tmp/ota && unzip -o /tmp/ota.zip 'system/*' -d /tmp/system_clean/

# 修改 system 文件（删除 APK 等）
# ...

# 制作 ext4 镜像
make_ext4fs -l 1G /tmp/system.img /tmp/system_clean/system/

# 刷入
dd if=/storage/usb0/system.img of=/dev/block/system bs=4096
```

## 5.6 更新二进制

### update-binary

```
/tmp/ota/META-INF/com/google/android/update-binary
```

ARM ELF 格式的更新程序，由 recovery 加载执行。

### 工作流程

1. recovery 加载 update-binary
2. update-binary 解析 updater-script
3. 执行更新操作（格式化、提取、刷入等）

---

*阶段五完成：OTA 分析与签名*
