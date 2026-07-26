#!/system/bin/sh
# install-recovery.sh - 主初始化脚本
# ZTE B860AV1.1-T2 机顶盒

# 调用 eth0.sh 进行网络初始化
/system/etc/eth0.sh

# 可以添加其他初始化任务
# 例如:
# - 启动自定义服务
# - 配置系统参数
# - 挂载文件系统
