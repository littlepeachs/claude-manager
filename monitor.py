"""
Claude Code 会话监控模块
从 ~/.claude/ 目录读取会话数据、token 统计、对话主题等信息
支持普通会话和 tmux 会话
"""

import json
import os
import time
from pathlib import Path
from typing import List, Dict, Optional
import psutil

from tmux_manager import TmuxManager


class ClaudeMonitor:
    def __init__(self):
        self.claude_dir = Path.home() / ".claude"
        self.sessions_dir = self.claude_dir / "sessions"
        self.projects_dir = self.claude_dir / "projects"
        self.backups_dir = self.claude_dir / "backups"
        self.history_file = self.claude_dir / "history.jsonl"
        self.tmux_manager = TmuxManager()

    def get_all_sessions(self) -> List[Dict]:
        """获取所有活跃的 Claude 会话（包括普通会话和 tmux 会话）"""
        sessions = []
        tmux_pids = set()

        # 1. 先获取所有 tmux 会话，记录它们的 PID
        tmux_sessions = self.tmux_manager.find_claude_sessions()
        for tmux_session in tmux_sessions:
            tmux_pids.add(tmux_session['pane_pid'])

        # 2. 获取普通会话（排除 tmux 会话的 PID）
        if self.sessions_dir.exists():
            for session_file in self.sessions_dir.glob("*.json"):
                try:
                    with open(session_file, 'r') as f:
                        session_data = json.load(f)

                    pid = session_data.get('pid')

                    # 检查进程是否还在运行
                    if not self._is_process_running(pid):
                        continue

                    # 如果这个 PID 在 tmux 中，跳过（稍后作为 tmux 会话处理）
                    if pid in tmux_pids:
                        continue

                    # 获取进程信息
                    process_info = self._get_process_info(pid)

                    # 获取项目路径
                    cwd = session_data.get('cwd', '')

                    # 获取 token 统计
                    tokens = self._get_token_stats(cwd, session_data.get('sessionId'))

                    # 获取当前主题
                    topic = self._get_current_topic(cwd, session_data.get('sessionId'))

                    # 计算运行时长
                    started_at = session_data.get('startedAt', 0) / 1000  # 转换为秒
                    runtime_seconds = int(time.time() - started_at)

                    # 获取最近对话
                    recent_qa = self._get_recent_qa(cwd, session_data.get('sessionId'))

                    sessions.append({
                        'pid': pid,
                        'session_id': session_data.get('sessionId'),
                        'cwd': cwd,
                        'project_name': Path(cwd).name if cwd else 'Unknown',
                        'started_at': started_at,
                        'runtime_seconds': runtime_seconds,
                        'runtime_display': self._format_runtime(runtime_seconds),
                        'current_topic': topic,
                        'recent_qa': recent_qa,
                        'tokens': tokens,
                        'memory_mb': process_info['memory_mb'],
                        'cpu_percent': process_info['cpu_percent'],
                        'session_type': 'normal',
                        'tmux_session': None
                    })
                except Exception as e:
                    print(f"Error processing session {session_file}: {e}")
                    continue

        # 3. 添加 tmux 会话
        for tmux_session in tmux_sessions:
            try:
                pid = tmux_session['pane_pid']
                cwd = tmux_session['current_path']

                # 获取进程信息
                process_info = self._get_process_info(pid)

                # 尝试从 ~/.claude/ 获取 session_id 和 token 信息
                session_id = None
                tokens = {'input': 0, 'output': 0, 'cache_read': 0, 'total': 0}
                recent_qa = []

                # 检查是否有对应的 session 文件
                session_file = self.sessions_dir / f"{pid}.json"
                if session_file.exists():
                    try:
                        with open(session_file, 'r') as f:
                            session_data = json.load(f)
                            session_id = session_data.get('sessionId')
                            # 获取 token 统计
                            tokens = self._get_token_stats(cwd, session_id)
                            # 获取最近对话
                            recent_qa = self._get_recent_qa(cwd, session_id)
                    except:
                        pass

                # 如果没有从文件获取到对话，尝试从 tmux 捕获
                if not recent_qa:
                    pane_content = self.tmux_manager.get_pane_content(tmux_session['session_name'])
                    recent_qa = pane_content.get('recent_qa', [])

                # 计算运行时长
                started_at = tmux_session['created']
                runtime_seconds = int(time.time() - started_at)

                # 获取当前主题
                if recent_qa:
                    topic = recent_qa[-1].get('question', '无活动')[:150]
                else:
                    topic = '无活动'

                sessions.append({
                    'pid': pid,
                    'session_id': session_id or tmux_session['session_name'],
                    'cwd': cwd,
                    'project_name': Path(cwd).name if cwd else 'Unknown',
                    'started_at': started_at,
                    'runtime_seconds': runtime_seconds,
                    'runtime_display': self._format_runtime(runtime_seconds),
                    'current_topic': topic,
                    'recent_qa': recent_qa[-2:] if len(recent_qa) >= 2 else recent_qa,
                    'tokens': tokens,
                    'memory_mb': process_info['memory_mb'],
                    'cpu_percent': process_info['cpu_percent'],
                    'session_type': 'tmux',
                    'tmux_session': tmux_session['session_name'],
                    'window_index': tmux_session.get('window_index', 0)
                })
            except Exception as e:
                print(f"Error processing tmux session: {e}")
                continue

        return sessions

    def _is_process_running(self, pid: int) -> bool:
        """检查进程是否还在运行"""
        try:
            process = psutil.Process(pid)
            return process.is_running() and process.name() == 'claude'
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _get_process_info(self, pid: int) -> Dict:
        """获取进程的资源使用信息"""
        try:
            process = psutil.Process(pid)
            return {
                'memory_mb': round(process.memory_info().rss / 1024 / 1024, 1),
                'cpu_percent': round(process.cpu_percent(interval=0.1), 1)
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {'memory_mb': 0, 'cpu_percent': 0}

    def _encode_project_path(self, path: str) -> str:
        """将项目路径编码为目录名格式"""
        return path.replace('/', '-')

    def _get_token_stats(self, cwd: str, session_id: str) -> Dict:
        """获取会话的 token 统计"""
        if not cwd or not session_id:
            return {'input': 0, 'output': 0, 'cache_read': 0, 'total': 0}

        # 编码项目路径
        encoded_path = self._encode_project_path(cwd)
        project_dir = self.projects_dir / encoded_path

        if not project_dir.exists():
            return {'input': 0, 'output': 0, 'cache_read': 0, 'total': 0}

        # 读取对话历史文件
        jsonl_file = project_dir / f"{session_id}.jsonl"

        if not jsonl_file.exists():
            return {'input': 0, 'output': 0, 'cache_read': 0, 'total': 0}

        total_input = 0
        total_output = 0
        cache_read = 0

        try:
            with open(jsonl_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if 'usage' in data:
                            usage = data['usage']
                            total_input += usage.get('input_tokens', 0)
                            total_output += usage.get('output_tokens', 0)
                            cache_read += usage.get('cache_read_input_tokens', 0)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading token stats: {e}")

        return {
            'input': total_input,
            'output': total_output,
            'cache_read': cache_read,
            'total': total_input + total_output
        }

    def _get_current_topic(self, cwd: str, session_id: str) -> str:
        """获取当前讨论的主题（最后一条用户消息）"""
        if not cwd or not session_id:
            return "无活动"

        # 编码项目路径
        encoded_path = self._encode_project_path(cwd)
        project_dir = self.projects_dir / encoded_path

        if not project_dir.exists():
            return "无活动"

        # 读取对话历史文件
        jsonl_file = project_dir / f"{session_id}.jsonl"

        if not jsonl_file.exists():
            return "无活动"

        last_user_message = None

        try:
            with open(jsonl_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if data.get('type') == 'user':
                            # 提取消息内容
                            message = data.get('message', {})
                            if isinstance(message, dict):
                                content = message.get('content', '')
                            else:
                                content = str(message)

                            # 如果是列表，提取文本内容
                            if isinstance(content, list):
                                text_parts = []
                                for item in content:
                                    if isinstance(item, dict) and item.get('type') == 'text':
                                        text_parts.append(item.get('text', ''))
                                content = ' '.join(text_parts)

                            if content:
                                last_user_message = content
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading topic: {e}")

        if last_user_message:
            # 截取前 150 字符
            return last_user_message[:150] + ('...' if len(last_user_message) > 150 else '')

        return "无活动"

    def _get_recent_qa(self, cwd: str, session_id: str, limit: int = 2) -> List[Dict]:
        """获取最近的问答对话"""
        if not cwd or not session_id:
            return []

        encoded_path = self._encode_project_path(cwd)
        project_dir = self.projects_dir / encoded_path

        if not project_dir.exists():
            return []

        jsonl_file = project_dir / f"{session_id}.jsonl"

        if not jsonl_file.exists():
            return []

        qa_pairs = []
        current_question = None

        try:
            with open(jsonl_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        msg_type = data.get('type')

                        if msg_type == 'user':
                            # 保存当前问题
                            message = data.get('message', {})
                            if isinstance(message, dict):
                                content = message.get('content', '')
                            else:
                                content = str(message)

                            if isinstance(content, list):
                                text_parts = []
                                for item in content:
                                    if isinstance(item, dict) and item.get('type') == 'text':
                                        text_parts.append(item.get('text', ''))
                                content = ' '.join(text_parts)

                            current_question = content

                        elif msg_type == 'assistant' and current_question:
                            # 保存问答对
                            message = data.get('message', {})
                            if isinstance(message, dict):
                                content = message.get('content', '')
                            else:
                                content = str(message)

                            if isinstance(content, list):
                                text_parts = []
                                for item in content:
                                    if isinstance(item, dict) and item.get('type') == 'text':
                                        text_parts.append(item.get('text', ''))
                                content = ' '.join(text_parts)

                            qa_pairs.append({
                                'question': current_question[:200],
                                'answer': content[:500]
                            })
                            current_question = None

                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading recent QA: {e}")

        # 返回最近的 N 对
        return qa_pairs[-limit:] if len(qa_pairs) > limit else qa_pairs

    def _format_runtime(self, seconds: int) -> str:
        """格式化运行时长"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    def get_summary(self, sessions: List[Dict]) -> Dict:
        """获取总览统计"""
        total_tokens = sum(s['tokens']['total'] for s in sessions)
        total_memory = sum(s['memory_mb'] for s in sessions)

        return {
            'active_sessions': len(sessions),
            'total_tokens': total_tokens,
            'total_memory_mb': round(total_memory, 1)
        }


if __name__ == '__main__':
    # 测试代码
    monitor = ClaudeMonitor()
    sessions = monitor.get_all_sessions()

    print(f"找到 {len(sessions)} 个活跃会话:\n")

    for session in sessions:
        print(f"PID: {session['pid']}")
        print(f"项目: {session['project_name']}")
        print(f"路径: {session['cwd']}")
        print(f"运行时长: {session['runtime_display']}")
        print(f"Token: {session['tokens']['total']:,}")
        print(f"内存: {session['memory_mb']} MB")
        print(f"CPU: {session['cpu_percent']}%")
        print(f"当前主题: {session['current_topic']}")
        print("-" * 80)

    summary = monitor.get_summary(sessions)
    print(f"\n总览:")
    print(f"活跃会话: {summary['active_sessions']}")
    print(f"总 Token: {summary['total_tokens']:,}")
    print(f"总内存: {summary['total_memory_mb']} MB")
