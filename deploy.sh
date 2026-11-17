#!/bin/bash
set -e

echo "========================================================================="
echo "  赛博天眼 · 足球量化终端 (CYBER-EYE QUANTUM TERMINAL) 国内云服务器一键部署"
echo "========================================================================="

# 1. 检查并设置时区为北京时间
echo "[1/5] 校准服务器时区为 Asia/Shanghai (北京时间)..."
if command -v timedatectl >/dev/null 2>&1; then
    timedatectl set-timezone Asia/Shanghai || true
else
    ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime || true
fi

# 2. 检查操作系统并安装必要依赖 (Git, Python3, Pip)
echo "[2/5] 检查系统环境并安装基础依赖 (Python3, Git, Curl)..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y git python3 python3-pip python3-numpy python3-scipy curl
elif command -v yum >/dev/null 2>&1; then
    yum install -y git python3 python3-pip curl
    pip3 install numpy scipy || true
fi

# 3. 部署或拉取最新代码
INSTALL_DIR="/root/football-quant-terminal"
echo "[3/5] 拉取最新项目源码至 $INSTALL_DIR ..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git fetch --all
    git reset --hard origin/main
else
    git clone https://github.com/18352505718/football-quant-terminal.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# 安装 pip 依赖 (保证 numpy/scipy 可用)
pip3 install -r requirements.txt || true

# 4. 执行一次即时数据抓取与模型计算 (国内原生网络直连体彩网关)
echo "[4/5] 执行首次体彩数据直连抓取与量化模型推演..."
python3 -c "import sys; sys.path.append('$INSTALL_DIR'); sys.path.append('$INSTALL_DIR/web_dashboard'); import daily_updater; daily_updater.run_update_now()" || true

# 5. 配置并启动 Systemd 守护进程 (开机自启 + 进程守护)
echo "[5/5] 配置 Systemd 后台自启守护进程 (端口 8888)..."
cat << 'EOF' > /etc/systemd/system/football-quant.service
[Unit]
Description=CyberEye Football Quant Terminal
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/football-quant-terminal/web_dashboard
ExecStart=/usr/bin/python3 server.py 8888
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable football-quant
systemctl restart football-quant

# 获取本机公网 IP
SERVER_IP=$(curl -s4 ifconfig.me || curl -s4 ip.sb || curl -s4 icanhazip.com || echo "您的服务器公网IP")

echo ""
echo "========================================================================="
echo "🎉 部署大功告成！赛博天眼足球量化终端已在后台全速运行！"
echo "========================================================================="
echo "🌐 访问地址: http://${SERVER_IP}:8888"
echo "🛡️ 守护状态: 已启用 Systemd 开机自启与进程守护"
echo "🔄 自动更新: 后台每 15 分钟全自动轮询国家体彩网关"
echo "📋 查看日志命令: journalctl -u football-quant -f"
echo "========================================================================="
