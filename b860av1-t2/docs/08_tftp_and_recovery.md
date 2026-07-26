# TFTP 刷机与 Recovery 恢复

## TFTP 网络刷机尝试

### 目的

通过 u-boot 的 `tftpboot` 命令从电脑下载 boot.img 到内存，然后写入 eMMC。

### 环境准备

1. 电脑安装 TFTP 服务器：`sudo apt install tftpd-hpa`
2. 配置 `/etc/default/tftpd-hpa`：`TFTP_DIRECTORY="/srv/tftp"`
3. 放入 boot.img：`cp boot.img /srv/tftp/`
4. 启动：`sudo systemctl start tftpd-hpa`

### 踩坑：TFTP 传输超时

u-boot 输出：
```
Loading: T #T #T ##T ##########T ########T ###T ######T ######T ##T #########
Retry count exceeded; starting again
```

`T` 表示超时重传。传输失败。

### 原因分析

1. **防火墙**：TFTP 使用 UDP 69 端口，数据传输用随机高端口，防火墙可能拦截
2. **权限**：`in.tftpd` 需要 root 权限绑定 69 端口
3. **服务冲突**：systemd 的 tftpd-hpa 和手动启动的 in.tftpd 冲突

### 尝试的解决方案

- `sudo iptables -F` 清防火墙 — 无效
- 手动启动 `sudo in.tftpd --listen --secure /srv/tftp` — 端口冲突
- Python 实现 TFTP 服务器 — 同样超时

### 结论

TFTP 方案未成功。原因可能是网络驱动在 u-boot 下不稳定，或 TFTP 协议实现问题。

## Recovery 恢复

### 方法

u-boot 中执行 `safe` 命令进入 recovery 模式。

### 恢复步骤

```bash
# 在 recovery shell 中
dd if=/data/local/boot_patched.img of=/dev/block/boot bs=4096
sync
reboot
```

### 关键点

- `/data/local/boot_patched.img` 在 data 分区，不会被 boot.img 覆盖
- `dd` 直接写 boot 分区，偏移由分区表决定
- `sync` 确保写入完成

### 成功恢复

使用 CMA32MB 版本的 boot_patched.img 恢复成功，系统正常启动。
