# Claude Code Dashboard

一个本地 Dashboard 工具，用于实时监控和管理多个 Claude Code 会话。支持 Mac + iTerm2 + Tmux 环境。

## 功能特性

- 🔍 **实时监控**: 自动发现并监控所有运行中的 Claude Code 进程
- 💬 **当前主题**: 展示每个会话正在讨论的内容
- 📈 **资源监控**: 实时显示内存和 CPU 使用情况
- 🖥️ **Tmux 集成**: 支持在 iTerm2 中打开和管理 tmux 会话
- ⚡ **实时更新**: 通过 WebSocket 每秒自动刷新数据

## 系统要求

- **操作系统**: macOS
- **终端**: iTerm2
- **会话管理**: Tmux
- **Python**: 3.8+
- **Claude Code**: 已安装并配置

## 快速开始

### 1. 安装依赖

#### 安装 Homebrew（如果未安装）

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### 安装 iTerm2

```bash
brew install --cask iterm2
```

#### 安装 Tmux

```bash
brew install tmux
```

#### 安装 Python 依赖

```bash
pip3 install -r requirements.txt
```

### 2. 配置

#### 创建配置文件

复制示例配置文件并根据你的环境修改：

```bash
cp config.example.json config.json
```

#### 编辑 config.json

```json
{
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
```

**配置说明：**

- `server.host`: 服务器监听地址，`0.0.0.0` 表示允许局域网访问
- `server.port`: 服务器端口，默认 8765
- `iterm.window_bounds`: iTerm2 窗口的位置和大小（x, y, width, height）

### 3. 启动 Dashboard

```bash
python3 dashboard.py
```

启动成功后，你会看到：

```
============================================================
Claude Code Dashboard 启动成功！
访问地址: http://localhost:8765
API 文档: http://localhost:8765/docs
按 Ctrl+C 停止服务器
============================================================
```

### 4. 访问界面

在浏览器中打开: http://localhost:8765

## 使用指南

### 监控会话

Dashboard 会自动检测所有运行中的 Claude Code 会话，包括：

- **普通会话**: 直接在终端运行的 Claude Code
- **Tmux 会话**: 在 tmux 中运行的 Claude Code

每个会话卡片显示：
- 项目名称和路径
- 进程 PID 和运行时长
- Token 使用统计
- 内存和 CPU 占用
- 当前对话主题

### 管理 Tmux 会话

对于 Tmux 会话，你可以：

1. **双击会话卡片** 或 **点击 iTerm2 按钮**: 在 iTerm2 中打开该会话
   - 如果窗口已存在，会自动切换到该窗口
   - 如果窗口不存在，会创建新窗口并附加到 tmux 会话

2. **终止会话**: 点击"终止"按钮停止会话

## 项目结构

```
claude_tool/
├── dashboard.py           # FastAPI 后端服务
├── monitor.py             # 会话数据采集模块
├── tmux_manager.py        # Tmux 会话管理
├── session_monitor.py     # 会话状态监控
├── requirements.txt       # Python 依赖
├── config.example.json    # 配置文件示例
├── config.json           # 配置文件（需自行创建）
├── static/
│   ├── index.html        # Vue 3 前端界面
│   └── chat.html         # 对话界面
└── README.md             # 本文件
```

## 技术栈

- **后端**: Python + FastAPI + WebSocket
- **前端**: Vue 3 (CDN)
- **数据源**: ~/.claude/ 目录
- **进程监控**: psutil
- **会话管理**: Tmux
- **终端集成**: iTerm2 + AppleScript

## 数据来源

Dashboard 从以下位置读取数据：

- `~/.claude/sessions/` - 活跃会话信息
- `~/.claude/projects/` - 对话历史
- `~/.claude/history.jsonl` - 命令历史
- `~/.claude/backups/` - 备份和统计数据

## API 文档

启动服务后访问: http://localhost:8765/docs

主要 API 端点：

- `GET /` - 主页面
- `GET /api/sessions` - 获取所有会话
- `GET /api/summary` - 获取统计摘要
- `POST /api/sessions/{session_id}/open-iterm` - 在 iTerm2 中打开会话
- `DELETE /api/sessions/{session_id}` - 终止会话
- `WebSocket /ws` - 实时数据推送

## 故障排除

### 无法连接到服务器

1. 确认 Dashboard 服务已启动
2. 检查端口 8765 是否被占用：`lsof -i :8765`
3. 查看终端输出的错误信息

### 没有显示会话

1. 确认有 Claude Code 会话正在运行
2. 检查 `~/.claude/sessions/` 目录是否存在
3. 运行 `python3 monitor.py` 测试数据采集

### iTerm2 无法打开会话

1. 确认 iTerm2 已安装
2. 确认 Tmux 已安装并且会话存在：`tmux ls`
3. 检查系统是否允许 AppleScript 控制 iTerm2

### Token 统计不准确

Token 数据从对话历史文件累加计算，如果文件不完整可能导致统计偏差。

### 配置文件未找到

如果启动时提示找不到配置文件，程序会使用默认配置。建议创建 `config.json` 文件以自定义配置。

## 开发

### 修改前端

编辑 `static/index.html`，刷新浏览器即可看到效果。

### 修改后端

修改 `dashboard.py` 或其他 Python 文件后，需要重启服务：

```bash
# 停止服务（Ctrl+C）
# 重新启动
python3 dashboard.py
```

### 测试数据采集

```bash
python3 monitor.py
```

## 贡献

欢迎提交 Issue 和 Pull Request！

## License

MIT
