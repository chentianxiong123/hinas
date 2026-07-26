# U-Boot 启动参数探索

## U-Boot 环境变量

通过 `printenv` 查看：

```
arch=arm
board=zx296716_square
bootcmd=bootsys
bootdelay=0
cpu=armv8
ethact=dwmac.5200000
ipaddr=192.168.1.22
serverip=192.168.1.24
loadaddr=0x40008000
fdtcontroladdr=0x48000000
```

## Bootargs 构建机制

`bootsys` 是 C 函数，不是 u-boot 命令。它用 `sprintf` 拼接 bootargs：

```c
// u-boot 二进制中的字符串模板
"setenv bootargs root=/dev/ram0 rw initrd=0x%x,0x%x boardtype=0x%x \
  console=ttyS0,115200n8 ${othbootargs} stmmaceth=chain_mode:1 \
  kgdboc=ttyS0,115200 loglevel=3 swiotlb=0x800"
```

后续追加参数（从 conf 分区和硬件读取）：
```
androidboot.hardware=zxic
androidboot.selinux=disabled
boot_revision=0006
LogoDataAddr=0x74000000
WorkMode=
```

## 踩坑：othbootargs 是死字符串

`${othbootargs}` 在 u-boot 命令行中会展开变量，但在 C 代码的 `sprintf` 中是字面量。

**测试：** 在 u-boot 中 `setenv othbootargs cma=64M`，启动后 `/proc/cmdline` 中显示 `${othbootargs}` 而不是 `cma=64M`。

**原因：** `bootsys` 函数用 `sprintf` 拼接字符串，不调用 `getenv("othbootargs")`。

**结论：** env 分区的 `othbootargs` 无法影响 bootargs。

## 踩坑：env 分区格式

标准 u-boot env 格式：
```
[4字节 CRC32] [key=value\0 key=value\0 ... \0\0]
```

ZTE 的 env 分区（mmcblk0p5）内容：
```
bootcmd=bootp; setenv bootargs root=/dev/nfs ...
bootdelay=5
baudrate=115200
upgrade_step=1
force_auto_update=false
```

`setenv`/`printenv` 在 u-boot 控制台能用，但 `bootsys` 不读 env 变量。

## U-Boot 可用命令

```
bootsys    - 正常启动
safe       - 进入 safe mode (recovery)
upgrade    - 刷写分区
tftpboot   - TFTP 下载到内存
mmc        - eMMC 读写
bootm      - 从内存启动镜像
```

## 网络配置

u-boot 网络需要和电脑在同一网段：

```bash
setenv ipaddr 192.168.1.22
setenv serverip 192.168.1.24
setenv gatewayip 192.168.1.1
setenv netmask 255.255.255.0
```

电脑有线网卡需要配置到 192.168.1.x 网段：
```bash
sudo ip addr add 192.168.1.24/24 dev enxdc3262cf0be6
```
