# Hinas 机顶盒改造工具集

本仓库包含多个机顶盒设备的改造工具和脚本。

## 项目列表

### 1. himv3798-100-hinas (海纳思 Hi3798MV100)

海纳思(hinas)系统软件包管理工具，支持一键安装/卸载 FileBrowser、Nginx、Samba、Alist、Aria2、Transmission、Jellyfin、HomeAssistant 等 30+ 款软件。

**设备信息:**
- 处理器: Hi3798MV100
- 系统: 海纳思 (hinas)

**文件说明:**
- `hi3798mv100_hinas_wifi.tar.gz` - WiFi 版本软件包
- `hinas_install_uninstall.sh` - 安装卸载脚本
- `install_hi3798mv100_wifi.sh` - WiFi 安装脚本
- `check_docker_registry.sh` - Docker 镜像检查脚本

### 2. b860av1-t2 (ZTE B860AV1.1-T2)

ZTE B860AV1.1-T2 机顶盒改造项目，通过逆向工程、内核补丁、系统裁剪等技术，将机顶盒改造为专用 Linux 服务器。

**设备信息:**
- 处理器: ZX296716 (ARM Cortex-A53, 64位)
- 内存: 990MB RAM
- 存储: 8GB eMMC
- 系统: Android 4.4.2

**主要功能:**
- ✓ 内核补丁 (禁用 set_fs_safe_mode 和 conf_fs_write)
- ✓ 系统裁剪 (删除 APK、框架、系统库)
- ✓ 网络持久化 (WiFi 驱动自动加载)
- ✓ ADB over TCP 访问

**快速开始:**
```bash
# 克隆仓库
git clone https://github.com/chentianxiong123/hinas.git
cd hinas/b860av1-t2

# 查看文档
cat README.md

# 使用脚本
python3 scripts/kernel_analysis.py --help
python3 scripts/patch_kernel.py --help
```

## 目录结构

```
hinas/
├── README.md                    # 本文件
├── himv3798-100-hinas/          # 海纳思 Hi3798MV100 项目
│   ├── hi3798mv100_hinas_wifi.tar.gz
│   ├── hinas_install_uninstall.sh
│   └── ...
└── b860av1-t2/                  # ZTE B860AV1.1-T2 项目
    ├── README.md
    ├── scripts/
    ├── docs/
    ├── patches/
    └── device/
```

## 使用说明

### 海纳思项目

```bash
# 进入海纳思目录
cd himv3798-100-hinas

# 安装软件
./hinas_install_uninstall.sh

# 检查 Docker 镜像
./check_docker_registry.sh
```

### ZTE B860 项目

```bash
# 进入 ZTE B860 目录
cd b860av1-t2

# 查看文档
cat README.md

# 使用内核分析脚本
python3 scripts/kernel_analysis.py extract boot.img kernel.bin
python3 scripts/kernel_analysis.py strings kernel.bin "set_fs_safe_mode"

# 使用内核补丁脚本
python3 scripts/patch_kernel.py patch boot.img boot_patched.img
python3 scripts/patch_kernel.py verify boot_patched.img
```

## 技术文档

详细技术文档请参阅各项目的 `docs/` 目录。

## 许可证

本项目仅供学习和研究使用。

## 联系方式

如有问题或建议，请通过 GitHub Issues 联系。
