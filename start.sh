#!/bin/bash

echo "======================================"
echo "Claude Code Dashboard 启动脚本"
echo "======================================"

# 使用 py38 环境
PYTHON=/Users/liwentao/miniconda3/envs/py38/bin/python
PIP=/Users/liwentao/miniconda3/envs/py38/bin/pip

# 检查 Python 版本
$PYTHON --version

# 检查依赖是否安装
if ! $PYTHON -c "import fastapi" 2>/dev/null; then
    echo ""
    echo "正在安装依赖..."
    $PIP install -r requirements.txt
fi

echo ""
echo "启动 Dashboard 服务器..."
echo "访问地址: http://localhost:8765"
echo ""

$PYTHON dashboard.py
