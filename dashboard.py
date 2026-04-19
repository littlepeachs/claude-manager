"""
Claude Code Dashboard 后端服务
提供 WebSocket 实时推送和 HTTP API
支持 tmux 会话管理
"""

import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel
import uvicorn
import httpx

from monitor import ClaudeMonitor
from tmux_manager import TmuxManager
from session_monitor import SessionMonitor

# 加载配置
def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        # 如果没有配置文件，使用默认配置
        return {
            "billing": {
                "base_path": str(Path.home() / "Desktop/Research/claude")
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

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_config()

app = FastAPI(title="Claude Code Dashboard")

# 挂载静态文件目录
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)

monitor = ClaudeMonitor()
tmux_manager = TmuxManager()
session_monitor = SessionMonitor()


# 请求模型
class SendMessageRequest(BaseModel):
    session_id: str
    message: str
    mode: str = None  # 可选：ask, autoedit, plan
    image: str = None  # base64 编码的图片


class CreateSessionRequest(BaseModel):
    project_path: str
    session_name: str = None
    mode: str = "ask"  # ask, autoedit, plan


class StopSessionRequest(BaseModel):
    session_id: str


@app.get("/")
async def get_index():
    """返回前端页面"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    else:
        return HTMLResponse("""
        <html>
            <head><title>Claude Dashboard</title></head>
            <body>
                <h1>Claude Code Dashboard</h1>
                <p>前端页面未找到，请创建 static/index.html</p>
            </body>
        </html>
        """)


@app.get("/chat/{session_id}")
async def get_chat_page(session_id: str):
    """返回对话页面"""
    chat_file = static_dir / "chat.html"
    if chat_file.exists():
        return FileResponse(chat_file)
    else:
        raise HTTPException(status_code=404, detail="Chat page not found")


@app.get("/api/sessions")
async def get_sessions():
    """获取所有会话列表（REST API）"""
    sessions = monitor.get_all_sessions()
    summary = monitor.get_summary(sessions)

    return {
        "sessions": sessions,
        "summary": summary
    }


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取单个会话详情"""
    sessions = monitor.get_all_sessions()

    for session in sessions:
        # 支持通过 session_id, pid 或 tmux_session 查找
        if (session['session_id'] == session_id or
            str(session['pid']) == session_id or
            session.get('tmux_session') == session_id):
            return session

    raise HTTPException(status_code=404, detail="Session not found")


@app.get("/api/folders")
async def get_folders():
    """获取可用的项目文件夹列表"""
    base_path = Path(config["billing"]["base_path"])

    try:
        if not base_path.exists():
            return {"folders": []}

        folders = []
        for item in base_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                folders.append(item.name)

        folders.sort()
        return {"folders": folders}
    except Exception as e:
        return {"folders": [], "error": str(e)}


@app.post("/api/sessions/create")
async def create_session(request: CreateSessionRequest):
    """创建新的 tmux Claude 会话"""
    project_path = Path(request.project_path)

    # 如果目录不存在，创建它
    if not project_path.exists():
        try:
            project_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"创建目录失败: {str(e)}")

    # 根据模式构建 Claude 命令
    mode_flags = {
        "ask": "",
        "autoedit": "--autoedit",
        "plan": "--plan"
    }

    mode_flag = mode_flags.get(request.mode, "")
    claude_cmd = f"claude {mode_flag}".strip()

    result = tmux_manager.create_session(
        project_path=str(project_path),
        session_name=request.session_name,
        claude_command=claude_cmd
    )

    if result['success']:
        result['mode'] = request.mode
        return result
    else:
        raise HTTPException(status_code=500, detail=result.get('error', 'Failed to create session'))


@app.post("/api/sessions/{session_id}/send")
async def send_message(session_id: str, request: SendMessageRequest):
    """向会话发送消息"""
    # 查找会话
    sessions = monitor.get_all_sessions()
    target_session = None

    for session in sessions:
        if session['session_id'] == session_id or session.get('tmux_session') == session_id:
            target_session = session
            break

    if not target_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 只有 tmux 会话才能发送消息
    if target_session['session_type'] != 'tmux':
        raise HTTPException(
            status_code=400,
            detail="只有 tmux 会话支持远程发送消息。请在 Dashboard 中创建新的 tmux 会话。"
        )

    # 如果有模式切换命令，先发送模式切换
    # 注意：ask 是默认模式，不需要切换命令
    if request.mode and request.mode != 'ask':
        mode_commands = {
            'autoedit': '/autoedit',
            'plan': '/plan'
        }
        if request.mode in mode_commands:
            tmux_manager.send_keys(target_session['tmux_session'], mode_commands[request.mode])
            await asyncio.sleep(0.5)

    # 如果有图片，保存并发送路径
    if request.image:
        import base64
        import tempfile
        try:
            # 解码 base64 图片
            image_data = base64.b64decode(request.image.split(',')[1] if ',' in request.image else request.image)

            # 保存到临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as f:
                f.write(image_data)
                image_path = f.name

            # 发送图片路径
            message_with_image = f"{request.message}\n[Image: {image_path}]"
            success = tmux_manager.send_keys(target_session['tmux_session'], message_with_image)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"图片处理失败: {str(e)}")
    else:
        # 发送普通消息
        success = tmux_manager.send_keys(target_session['tmux_session'], request.message)

    if success:
        return {"success": True, "message": "消息已发送"}
    else:
        raise HTTPException(status_code=500, detail="发送消息失败")


@app.post("/api/sessions/{session_id}/respond")
async def respond_to_interaction(session_id: str, request: dict):
    """响应会话的交互请求（如 yes/no 确认）"""
    sessions = monitor.get_all_sessions()
    target_session = None

    for session in sessions:
        if session['session_id'] == session_id or session.get('tmux_session') == session_id:
            target_session = session
            break

    if not target_session:
        raise HTTPException(status_code=404, detail="Session not found")

    if target_session['session_type'] != 'tmux':
        raise HTTPException(status_code=400, detail="只有 tmux 会话支持远程响应")

    # 发送用户的选择
    response_text = request.get('response', '')
    success = tmux_manager.send_keys(target_session['tmux_session'], response_text)

    # 重置该会话的监控状态
    session_monitor.reset_session(session_id)

    if success:
        return {"success": True, "message": "响应已发送"}
    else:
        raise HTTPException(status_code=500, detail="发送响应失败")


@app.delete("/api/sessions/{session_id}")
async def kill_session(session_id: str):
    """终止会话"""
    sessions = monitor.get_all_sessions()
    target_session = None

    for session in sessions:
        if session['session_id'] == session_id or session.get('tmux_session') == session_id:
            target_session = session
            break

    if not target_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 如果是 tmux 会话，使用 tmux kill
    if target_session['session_type'] == 'tmux':
        success = tmux_manager.kill_session(target_session['tmux_session'])
        if success:
            return {"success": True, "message": "会话已终止"}
        else:
            raise HTTPException(status_code=500, detail="终止会话失败")
    else:
        # 普通会话，使用 kill 命令
        import signal
        import psutil
        try:
            process = psutil.Process(target_session['pid'])
            process.send_signal(signal.SIGTERM)
            return {"success": True, "message": "会话已终止"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"终止会话失败: {str(e)}")


@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """停止当前响应（发送 Ctrl+C）"""
    # 查找会话
    sessions = monitor.get_all_sessions()
    target_session = None

    for session in sessions:
        if session['session_id'] == session_id or session.get('tmux_session') == session_id:
            target_session = session
            break

    if not target_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 只有 tmux 会话才能停止
    if target_session['session_type'] != 'tmux':
        raise HTTPException(
            status_code=400,
            detail="只有 tmux 会话支持远程停止。"
        )

    # 发送 Ctrl+C
    import subprocess
    try:
        subprocess.run(
            ['tmux', 'send-keys', '-t', target_session['tmux_session'], 'C-c'],
            capture_output=True,
            timeout=5
        )
        return {"success": True, "message": "已发送停止信号"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止失败: {str(e)}")


@app.get("/api/sessions/{session_id}/summary")
async def get_session_summary(session_id: str):
    """获取会话主题总结（不超过100字）"""
    sessions = monitor.get_all_sessions()
    target_session = None

    for session in sessions:
        if session['session_id'] == session_id:
            target_session = session
            break

    if not target_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 如果是 tmux 会话，从 tmux 捕获最近的对话
    if target_session['session_type'] == 'tmux':
        result = tmux_manager.capture_pane_incremental(target_session['tmux_session'], start_line=0)
        messages = result.get('messages', [])

        # 提取最近的用户消息作为主题
        user_messages = [msg['content'] for msg in messages if msg['type'] == 'user']

        if user_messages:
            # 取最后3条用户消息，总结会话主题
            recent_topics = user_messages[-3:]
            summary = "、".join([msg[:30] + "..." if len(msg) > 30 else msg for msg in recent_topics])
            summary = summary[:100]  # 限制100字
        else:
            summary = target_session.get('current_topic', '暂无对话内容')[:100]
    else:
        # 普通会话，使用 current_topic
        summary = target_session.get('current_topic', '暂无对话内容')[:100]

    return {
        "session_id": session_id,
        "summary": summary
    }


@app.get("/api/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """获取会话的完整对话历史"""
    sessions = monitor.get_all_sessions()
    target_session = None

    for session in sessions:
        if session['session_id'] == session_id:
            target_session = session
            break

    if not target_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 如果是 tmux 会话，从 tmux 捕获
    if target_session['session_type'] == 'tmux':
        content = tmux_manager.get_pane_content(target_session['tmux_session'])
        return {
            "session_id": session_id,
            "history": content.get('full_qa', []),
            "raw_content": content.get('raw_content', '')
        }
    else:
        # 普通会话，从文件读取
        return {
            "session_id": session_id,
            "history": target_session.get('recent_qa', []),
            "message": "完整历史需要从 ~/.claude/projects/ 读取"
        }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 端点，实时推送会话数据"""
    await websocket.accept()

    try:
        while True:
            # 采集所有会话数据
            sessions = monitor.get_all_sessions()
            summary = monitor.get_summary(sessions)

            # 检测每个会话的状态
            session_states = {}
            interactions = []
            for session in sessions:
                if session.get('session_type') == 'tmux' and session.get('tmux_session'):
                    # 获取会话输出
                    output = tmux_manager.capture_pane(session['tmux_session'], lines=50)

                    # 分析输出，传入session_name和window_index
                    tmux_session = session['tmux_session']
                    window_index = session.get('window_index', 0)
                    analysis = session_monitor.analyze_output(
                        session['session_id'],
                        output,
                        session_name=tmux_session,
                        window_index=window_index
                    )

                    # 记录所有会话的状态
                    session_states[session['session_id']] = analysis['status']

                    # 只有需要交互的才加入 interactions 列表
                    if analysis['needs_interaction']:
                        interactions.append(analysis)

            # 推送给客户端
            await websocket.send_json({
                'type': 'update',
                'sessions': sessions,
                'summary': summary,
                'interactions': interactions,  # 需要交互的会话列表
                'session_states': session_states,  # 所有会话的状态
                'timestamp': asyncio.get_event_loop().time()
            })

            # 每0.3秒更新一次，提高刷新速度
            await asyncio.sleep(0.3)

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")


@app.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """WebSocket 端点，实时推送 tmux 会话输出"""
    await websocket.accept()
    print(f"WebSocket 连接: session_id={session_id}")

    # 查找会话
    sessions = monitor.get_all_sessions()
    target_session = None

    for session in sessions:
        if (session['session_id'] == session_id or
            session.get('tmux_session') == session_id or
            str(session['pid']) == session_id):
            target_session = session
            print(f"找到会话: {session['project_name']}, tmux={session.get('tmux_session')}")
            break

    if not target_session:
        print(f"未找到会话: {session_id}")
        await websocket.send_json({
            'type': 'error',
            'message': f'Session not found: {session_id}'
        })
        await websocket.close()
        return

    if target_session['session_type'] != 'tmux':
        print(f"会话不是 tmux 类型: {target_session['session_type']}")
        await websocket.send_json({
            'type': 'error',
            'message': 'Not a tmux session'
        })
        await websocket.close()
        return

    tmux_session_name = target_session['tmux_session']
    print(f"开始监控 tmux 会话: {tmux_session_name}")

    try:
        last_line = 0
        while True:
            # 增量捕获 tmux 输出
            result = tmux_manager.capture_pane_incremental(
                tmux_session_name,
                start_line=last_line
            )

            if result['new_lines'] > 0:
                print(f"捕获到新内容: {result['new_lines']} 条消息")
                # 发送解析后的消息
                for msg in result.get('messages', []):
                    await websocket.send_json({
                        'type': 'message',
                        'message': msg
                    })
                last_line = result['total_lines']

            # 每 500ms 检查一次
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        print(f"Chat client disconnected from session {session_id}")
    except Exception as e:
        print(f"Chat WebSocket error: {e}")
        import traceback
        traceback.print_exc()


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}


@app.post("/api/sessions/{session_id}/open-iterm")
async def open_in_iterm(session_id: str):
    """在 iTerm2 中打开 tmux 会话"""
    # 查找会话
    sessions = monitor.get_all_sessions()
    target_session = None

    for session in sessions:
        if (session['session_id'] == session_id or
            session.get('tmux_session') == session_id):
            target_session = session
            break

    if not target_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 只有 tmux 会话才能在 iTerm2 中打开
    if target_session['session_type'] != 'tmux':
        raise HTTPException(
            status_code=400,
            detail="只有 tmux 会话支持在 iTerm2 中打开。"
        )

    # 使用 AppleScript 打开 iTerm2 并附加到 tmux 会话
    tmux_session_name = target_session['tmux_session']

    # 获取窗口大小配置
    bounds = config["iterm"]["window_bounds"]
    window_bounds = f"{{{bounds['x']}, {bounds['y']}, {bounds['width']}, {bounds['height']}}}"

    # 先检查是否已经有窗口打开了这个 tmux 会话
    applescript = f'''
    tell application "iTerm"
        activate

        -- 检查是否已经有窗口打开了这个 tmux 会话
        set foundWindow to false
        set foundTab to missing value
        set targetWindow to missing value

        repeat with aWindow in windows
            repeat with aTab in tabs of aWindow
                repeat with aSession in sessions of aTab
                    try
                        set sessionTTY to tty of aSession
                        -- 检查这个 tty 是否属于目标 tmux 会话
                        set checkCmd to "tmux list-panes -a -F '#{{session_name}} #{{pane_tty}}' | grep '" & sessionTTY & "' | awk '{{print $1}}'"
                        set tmuxSession to do shell script checkCmd
                        if tmuxSession is equal to "{tmux_session_name}" then
                            set foundWindow to true
                            set targetWindow to aWindow
                            set foundTab to aTab
                            exit repeat
                        end if
                    end try
                end repeat
                if foundWindow then exit repeat
            end repeat
            if foundWindow then exit repeat
        end repeat

        -- 如果找到了，切换到那个窗口
        if foundWindow then
            select targetWindow
            tell targetWindow
                select foundTab
            end tell
        else
            -- 如果没找到，创建新窗口
            create window with default profile
            tell current session of current window
                write text "tmux attach -t {tmux_session_name}"
            end tell
            tell current window
                set bounds to {window_bounds}
            end tell
        end if
    end tell
    '''

    try:
        import subprocess
        subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            timeout=10
        )
        return {"success": True, "message": f"已在 iTerm2 中打开会话 {tmux_session_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开 iTerm2 失败: {str(e)}")


def main():
    """启动服务器"""
    print("=" * 60)
    print("Claude Code Dashboard 启动中...")
    print("=" * 60)
    print(f"访问地址: http://localhost:8765")
    print(f"API 文档: http://localhost:8765/docs")
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8765,
        log_level="info"
    )


if __name__ == "__main__":
    main()
