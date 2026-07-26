# 总结：ZTE B860AV1.1-T2 改造成果

## 已完成

### 1. WiFi 连接

- 加载 8189fs 驱动
- wpa_supplicant 连接 WPA2
- dhcpcd 获取 IP

### 2. SSH 远程管理

- dropbear v0.52 监听端口 22
- root 密码已配置

### 3. 内存优化（运行时）

- 原始：733 MB 已用，280 MB 空闲
- Kill Android 后：300 MB 已用，714 MB 空闲

### 4. CMA 内存回收（永久）

- DTB 修改：multimedia_region 272 MB → 16 MB
- 效果：CmaTotal 从 336 MB 降到 36 MB
- 总空闲内存：714 MB（运行时 kill + CMA 优化）

### 5. 开机自启（install-recovery.sh）

通过 `/system/etc/install-recovery.sh` 钩子，开机自动：
- 加载 WiFi 驱动
- 连接 WiFi
- 启动 SSH

## 未完成

### 1. Init.rc 改造

分析了 init.rc 结构，制定了改造方案（删除 Android 服务，添加 linux_init 服务），但未实际刷入验证。原因：改 ramdisk 大小会导致 DTB 偏移变化，需要精确控制。

### 2. CMA=0 测试

CMA 设为 0 导致内核 panic。最小可用值约 16 MB。

### 3. TFTP 网络刷机

u-boot 的 tftpboot 命令传输超时，未解决。使用 recovery + dd 方案替代。

## 关键教训

1. **Boot.img 改动必须保持文件大小一致** — DTB 偏移是固定的
2. **DTB 没有 CRC32** — offset 4-7 是 totalsize
3. **CMA 不能为 0** — 驱动初始化需要最小内存
4. **u-boot 的 bootsys 不展开环境变量** — `${othbootargs}` 是死字符串
5. **TFTP 在 u-boot 下可能不稳定** — 用 recovery + dd 更可靠
6. **init 会自动重启服务** — 必须用 `stop` 命令，不能只 `kill`
