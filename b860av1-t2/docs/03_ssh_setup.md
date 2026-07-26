# SSH 服务配置

## Dropbear

系统自带 dropbear v0.52（2012年版本），路径 `/system/xbin/dropbear`。

## 启动

```bash
# 生成主机密钥
mkdir -p /data/ssh
dropbearkey -t rsa -f /data/ssh/dropbear_rsa_host_key

# 启动（端口22）
dropbear -p 22
```

## 踩坑：SSH 端口默认22

用户要求用22端口，不是2222。dropbear 默认就是22，直接 `dropbear -p 22` 即可。

## 踩坑：旧版加密算法

Dropbear v0.52 只支持旧版密钥交换算法 `diffie-hellman-group1-sha1`，新版 OpenSSH 默认禁用。

客户端连接需要加参数：
```bash
ssh -oKexAlgorithms=+diffie-hellman-group1-sha1 -oHostKeyAlgorithms=+ssh-rsa root@192.168.31.208
```

或者写入 `~/.ssh/config`：
```
Host 192.168.31.208
    KexAlgorithms +diffie-hellman-group1-sha1
    HostKeyAlgorithms +ssh-rsa
    PubkeyAcceptedKeyTypes +ssh-rsa
```

## Root 密码

默认密码 hash 存在 `/etc/passwd`。用 `openssl passwd -1` 生成新密码 hash，通过 system 分区 bind mount 写入。
