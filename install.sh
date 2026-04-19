#!/bin/bash

# Claude Code Dashboard 一键安装脚本
# 适用于 macOS + iTerm2 + Tmux

set -e

echo "============================================================"
echo "Claude Code Dashboard 安装脚本"
echo "============================================================"
echo ""

# 检查操作系统
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ 错误: 此脚本仅支持 macOS"
    exit 1
fi

echo "✓ 操作系统检查通过"

# 检查 Homebrew
if ! command -v brew &> /dev/null; then
    echo "⚠️  未检测到 Homebrew，正在安装..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "✓ Homebrew 已安装"
fi

# 检查 iTerm2
if ! [ -d "/Applications/iTerm.app" ]; then
    echo "⚠️  未检测到 iTerm2，正在安装..."
    brew install --cask iterm2
else
    echo "✓ iTerm2 已安装"
fi

# 检查 Tmux
if ! command -v tmux &> /dev/null; then
    echo "⚠️  未检测到 Tmux，正在安装..."
    brew install tmux
else
    echo "✓ Tmux 已安装"
fi

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未检测到 Python3，请先安装 Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Python $PYTHON_VERSION 已安装"

# 安装 Python 依赖
echo ""
echo "正在安装 Python 依赖..."
pip3 install -r requirements.txt

echo "✓ Python 依赖安装完成"

# 创建配置文件
if [ ! -f "config.json" ]; then
    echo ""
    echo "正在创建配置文件..."

    # 询问用户 Claude 项目路径
    echo ""
    echo "请输入你的 Claude 项目根目录路径"
    echo "（例如: /Users/yourname/Desktop/Research/claude）"
    read -p "路径: " CLAUDE_PATH

    # 验证路径
    if [ ! -d "$CLAUDE_PATH" ]; then
        echo "⚠️  警告: 路径不存在，将使用默认路径"
        CLAUDE_PATH="$HOME/Desktop/Research/claude"
    fi

    # 创建配置文件
    cat > config.json <<EOF
{
  "billing": {
    "base_path": "$CLAUDE_PATH",
    "description": "Claude 项目的基础路径"
  },
  "server": {
    "host": "0.0.0.0",
    "port": 8765,
    "description": "Dashboard 服务器配置"
  },
  "iterm": {
    "window_bounds": {
      "x": 0,
      "y": 0,
      "width": 1920,
      "height": 1080
    },
    "description": "iTerm2 窗口大小配置"
  }
}
EOF

    echo "✓ 配置文件创建完成: config.json"
else
    echo "✓ 配置文件已存在"
fi

# 完成
echo ""
echo "============================================================"
echo "✅ 安装完成！"
echo "============================================================"
echo ""
echo "启动 Dashboard:"
echo "  python3 dashboard.py"
echo ""
echo "访问地址:"
echo "  http://localhost:8765"
echo ""
echo "如需修改配置，请编辑 config.json 文件"
echo "============================================================"
