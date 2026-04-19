# 快速开始

一键安装并启动 Claude Code Dashboard。

## 安装

```bash
# 克隆仓库
git clone https://github.com/littlepeachs/claude-code-dashboard.git
cd claude-code-dashboard

# 运行安装脚本
./install.sh
```

安装脚本会自动：
1. 检查并安装 Homebrew（如果需要）
2. 安装 iTerm2（如果需要）
3. 安装 Tmux（如果需要）
4. 安装 Python 依赖
5. 创建配置文件

## 启动

```bash
python3 dashboard.py
```

然后在浏览器中打开: http://localhost:8765

## 配置

编辑 `config.json` 文件自定义配置：

```json
{
  "billing": {
    "base_path": "/path/to/your/claude/projects"
  },
  "server": {
    "host": "0.0.0.0",
    "port": 8765
  },
  "iterm": {
    "window_bounds": {
      "x": 0,
      "y": 0,
      "width": 1920,
      "height": 1080
    }
  }
}
```

详细文档请查看 [README.md](README.md)
