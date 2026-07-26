#!/bin/bash

# 检查是否安装了bc，如果没有安装，则进行安装
check_and_install_bc() {
    if ! command -v bc &> /dev/null; then
        echo "bc could not be found, attempting to install it..."
        sudo apt-get update
        if ! sudo apt-get install -y bc; then
            echo "Failed to install bc. Please install it manually and rerun the script."
            exit 1
        fi
    fi
}

# 运行检查和安装函数
check_and_install_bc

# 定义一个函数来测试镜像源的下载速度
test_speed() {
    local source=$1
    local image="xjxjin/alist-sync:1.0.1" # 使用一个很小的镜像来测试速度
    local start_time

    # 拉取镜像前记录当前时间
    start_time=$(date +%s.%N)

    # 使用指定的镜像源拉取hello-world镜像
    docker pull $source/$image > /dev/null 2>&1

    # 拉取镜像后记录当前时间
    local end_time=$(date +%s.%N)

    # 计算下载时间（秒）
    local download_time=$(echo "$end_time - $start_time" | bc -l)

    echo "$download_time"
}

# 镜像源列表
sources=(
    "https://docker.m.daocloud.io"
    "https://ghcr.io"
    "https://mirror.baidubce.com"
    "https://docker.nju.edu.cn"
)

# 初始化最快速度为最大值
min_time=999999999

# 初始化最快镜像源
fastest_source=""

# 遍历镜像源列表并测试速度
for source in "${sources[@]}"; do
    echo "Testing speed of $source"
    time=$(test_speed $source)
    echo "Download time: $time seconds"

    # 如果当前源的速度比已知的最快速度还快，则更新最快速度和镜像源
    if (( $(echo "$time < $min_time" | bc -l) )); then
        min_time=$time
        fastest_source=$source
    fi
done

# 输出最快的镜像源
echo "Fastest source is $fastest_source with a download time of $min_time seconds"

# 更新配置文件
if [ ! -z "$fastest_source" ]; then
    cat <<EOF > /etc/docker/daemon.json
{
    "registry-mirrors": [
        "$fastest_source"
    ]
}
EOF

    # 重启Docker服务以使配置生效
    # systemctl restart docker
    echo "Docker configuration updated and service restarted."
else
    echo "No valid source found."
fi