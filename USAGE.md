# Claude Code Dashboard 使用指南

## 🎉 Dashboard 已启动成功！

### 访问地址

- **主界面**: http://localhost:8765
- **API 文档**: http://localhost:8765/docs
- **健康检查**: http://localhost:8765/health

### 当前状态

✅ 服务器运行中 (PID: 89137)
✅ 已检测到 2 个活跃会话
✅ WebSocket 实时推送已启用

---

## 快速开始

### 1. 打开 Dashboard

在浏览器中访问: **http://localhost:8765**

你将看到：
- 📊 总览统计（活跃会话数、总 Token、总内存）
- 📋 实时会话列表
- 💬 每个会话的当前讨论主题
- 📈 Token 消耗详情（输入/输出/缓存）
- 🖥️ 资源使用情况（内存/CPU）

### 2. 实时监控

Dashboard 每秒自动刷新，无需手动刷新页面。

### 3. 停止服务器

```bash
# 查找进程
ps aux | grep dashboard.py

# 停止服务器
kill 89137
```

或者使用快捷命令：
```bash
pkill -f dashboard.py
```

---

## 功能说明

### 总览卡片

- **活跃会话**: 当前运行的 Claude Code 进程数量
- **总 Token 消耗**: 所有会话的累计 token 使用量
- **总内存占用**: 所有进程的内存使用总和

### 会话列表

每个会话显示：

1. **基本信息**
   - PID: 进程 ID
   - 项目名称: 当前工作目录的名称
   - 项目路径: 完整的工作目录路径
   - 运行时长: 会话已运行的时间

2. **当前主题**
   - 显示最后一条用户输入的消息（前 150 字符）

3. **Token 统计**
   - 总 Token: 输入 + 输出的总和
   - 输入 Token: 发送给模型的 token 数
   - 输出 Token: 模型生成的 token 数
   - 缓存读取: 从缓存读取的 token 数（节省成本）

4. **资源使用**
   - 内存: 进程占用的内存（超过 500MB 会标黄）
   - CPU: 当前 CPU 使用率

---

## 启动方式

### 方式 1: 使用启动脚本（推荐）

```bash
cd /Users/liwentao/Desktop/Research/claude/claude_tool
./start.sh
```

### 方式 2: 直接运行

```bash
cd /Users/liwentao/Desktop/Research/claude/claude_tool
/Users/liwentao/miniconda3/envs/py38/bin/python dashboard.py
```

### 方式 3: 后台运行

```bash
cd /Users/liwentao/Desktop/Research/claude/claude_tool
nohup /Users/liwentao/miniconda3/envs/py38/bin/python dashboard.py > dashboard.log 2>&1 &
```

---

## API 使用

### REST API

获取所有会话：
```bash
curl http://localhost:8765/api/sessions
```

获取单个会话：
```bash
curl http://localhost:8765/api/sessions/88378
```

### WebSocket

连接 WebSocket 接收实时更新：
```javascript
const ws = new WebSocket('ws://localhost:8765/ws');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('会话更新:', data.sessions);
    console.log('总览:', data.summary);
};
```

---

## 故障排除

### 问题 1: 端口被占用

如果 8765 端口被占用，编辑 `dashboard.py`：

```python
# 修改端口号
uvicorn.run(app, host="0.0.0.0", port=8888)  # 改为其他端口
```

### 问题 2: Token 统计为 0

可能原因：
- 会话刚启动，还没有对话
- 对话历史文件路径不正确
- 项目路径编码问题

运行测试命令检查：
```bash
/Users/liwentao/miniconda3/envs/py38/bin/python monitor.py
```

### 问题 3: 无法连接到服务器

检查服务器是否运行：
```bash
curl http://localhost:8765/health
```

如果返回 `{"status":"ok"}` 说明服务器正常。

### 问题 4: 会话列表为空

确认：
1. 有 Claude Code 会话正在运行
2. `~/.claude/sessions/` 目录存在
3. 进程名称为 `claude`

---

## 技术细节

### 数据来源

- **会话信息**: `~/.claude/sessions/{pid}.json`
- **对话历史**: `~/.claude/projects/{project}/{session_id}.jsonl`
- **Token 统计**: 从对话历史 JSONL 文件累加计算
- **进程信息**: 使用 `psutil` 库实时获取

### 更新频率

- WebSocket 推送: 每 1 秒
- 进程扫描: 每次推送时扫描
- Token 计算: 每次推送时重新计算

### 性能

- 内存占用: ~50MB
- CPU 占用: <1%（空闲时）
- 网络带宽: ~1KB/s（每个客户端）

---

## 下一步

### 可选扩展功能

1. **会话操作**: 添加终止会话按钮
2. **历史统计**: 显示每日/每周 token 消耗趋势图
3. **告警功能**: Token 超过阈值时桌面通知
4. **会话分组**: 按项目路径分组显示
5. **搜索过滤**: 按关键词搜索会话主题
6. **导出功能**: 导出会话统计报告

如需添加这些功能，请告诉我！

---

## 联系方式

如有问题或建议，请查看项目 README.md 文件。

**祝使用愉快！** 🎊
