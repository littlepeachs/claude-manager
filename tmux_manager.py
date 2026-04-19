"""
Tmux 会话管理器
用于创建、控制和监控 tmux 中的 Claude Code 会话
"""

import subprocess
import time
import re
from typing import List, Dict, Optional


class TmuxManager:
    def __init__(self):
        self.session_prefix = "claude-"

    def list_sessions(self) -> List[Dict]:
        """列出所有 tmux 会话"""
        try:
            result = subprocess.run(
                ['tmux', 'list-sessions', '-F', '#{session_name}:#{session_created}:#{session_attached}'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return []

            sessions = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                parts = line.split(':')
                if len(parts) >= 3:
                    sessions.append({
                        'name': parts[0],
                        'created': int(parts[1]),
                        'attached': parts[2] == '1'
                    })

            return sessions
        except Exception as e:
            print(f"Error listing tmux sessions: {e}")
            return []

    def create_session(self, project_path: str, session_name: Optional[str] = None, claude_command: str = "claude") -> Dict:
        """创建新的 Claude tmux 会话"""
        if not session_name:
            timestamp = int(time.time())
            session_name = f"{self.session_prefix}{timestamp}"

        try:
            # 创建 tmux 会话并启动 Claude
            cmd = [
                'tmux', 'new-session', '-d',
                '-s', session_name,
                '-c', project_path,
                claude_command
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return {
                    'success': True,
                    'session_name': session_name,
                    'project_path': project_path,
                    'command': claude_command,
                    'message': f'会话 {session_name} 创建成功'
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def send_keys(self, session_name: str, text: str) -> bool:
        """向 tmux 会话发送文本"""
        try:
            # 发送文本
            subprocess.run(
                ['tmux', 'send-keys', '-t', session_name, text],
                capture_output=True,
                timeout=5
            )

            # 发送回车
            subprocess.run(
                ['tmux', 'send-keys', '-t', session_name, 'Enter'],
                capture_output=True,
                timeout=5
            )

            return True
        except Exception as e:
            print(f"Error sending keys to {session_name}: {e}")
            return False

    def capture_pane(self, session_name: str, lines: int = 100) -> str:
        """捕获 tmux 会话的输出"""
        try:
            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', session_name, '-p', '-S', f'-{lines}'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                return result.stdout
            else:
                return ""
        except Exception as e:
            print(f"Error capturing pane from {session_name}: {e}")
            return ""

    def capture_pane_incremental(self, session_name: str, start_line: int = 0) -> Dict:
        """增量捕获 tmux 会话输出（用于实时流式传输），过滤界面元素并解析对话"""
        try:
            # 捕获更多历史内容（-S -2000 表示从倒数 2000 行开始）
            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', session_name, '-p', '-S', '-2000'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return {'content': '', 'total_lines': 0, 'new_lines': 0, 'messages': []}

            content = result.stdout
            lines = content.split('\n')

            # 解析对话消息
            messages = []
            current_message = None

            for line in lines:
                stripped = line.strip()

                # 跳过完全空行
                if not stripped:
                    continue

                # 跳过欢迎界面和边框
                if any(char in line for char in ['╭', '╰', '│']) and 'Claude Code' in line:
                    continue
                if all(c in '│╭╰─┤├┬┴ ' for c in line):
                    continue

                # 跳过底部状态栏
                if '? for shortcuts' in line or 'Update available' in line:
                    continue
                if '[✦_✦] Moth' in line or 'Opus 4.6' in line:
                    continue

                # 检测用户输入（❯ 开头）
                if stripped.startswith('❯'):
                    # 保存之前的消息
                    if current_message and current_message['content'].strip():
                        messages.append(current_message)

                    # 开始新的用户消息
                    user_text = stripped[1:].strip()
                    if user_text:
                        current_message = {
                            'type': 'user',
                            'content': user_text
                        }
                    else:
                        current_message = None

                # 检测助手回复（⏺ 开头）
                elif stripped.startswith('⏺'):
                    # 保存之前的消息
                    if current_message and current_message['content'].strip():
                        messages.append(current_message)

                    # 开始新的助手消息
                    assistant_text = stripped[1:].strip()
                    current_message = {
                        'type': 'assistant',
                        'content': assistant_text if assistant_text else ''
                    }

                # 多行内容（既不是 ❯ 也不是 ⏺ 开头，且有当前消息）
                elif current_message:
                    # 跳过纯边框行
                    if all(c in '─ ' for c in stripped):
                        continue
                    # 添加到当前消息
                    if stripped:
                        if current_message['content']:
                            current_message['content'] += '\n' + stripped
                        else:
                            current_message['content'] = stripped

            # 保存最后一条消息
            if current_message and current_message['content'].strip():
                messages.append(current_message)

            total_messages = len(messages)

            # 返回新消息
            if total_messages > start_line:
                new_messages = messages[start_line:]
                return {
                    'content': '',
                    'total_lines': total_messages,
                    'new_lines': total_messages - start_line,
                    'start_line': start_line,
                    'messages': new_messages
                }

            return {
                'content': '',
                'total_lines': total_messages,
                'new_lines': 0,
                'start_line': start_line,
                'messages': []
            }
        except Exception as e:
            print(f"Error capturing incremental pane from {session_name}: {e}")
            import traceback
            traceback.print_exc()
            return {'content': '', 'total_lines': 0, 'new_lines': 0, 'messages': []}

    def get_pane_content(self, session_name: str) -> Dict:
        """获取会话的当前内容（解析后的）"""
        content = self.capture_pane(session_name, lines=200)

        # 简单解析：提取最后的问答
        lines = content.strip().split('\n')

        # 查找最近的用户输入和 Claude 回复
        recent_qa = []
        current_q = None
        current_a = []

        for line in lines:
            # 检测用户输入（通常以 > 或提示符开始）
            if line.strip().startswith('>') or '❯' in line:
                if current_q and current_a:
                    recent_qa.append({
                        'question': current_q,
                        'answer': '\n'.join(current_a)
                    })
                current_q = line.strip()
                current_a = []
            elif current_q:
                current_a.append(line)

        # 添加最后一个问答
        if current_q and current_a:
            recent_qa.append({
                'question': current_q,
                'answer': '\n'.join(current_a)
            })

        return {
            'raw_content': content,
            'recent_qa': recent_qa[-2:] if len(recent_qa) >= 2 else recent_qa,  # 最近 2 轮
            'full_qa': recent_qa
        }

    def kill_session(self, session_name: str) -> bool:
        """终止 tmux 会话"""
        try:
            result = subprocess.run(
                ['tmux', 'kill-session', '-t', session_name],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error killing session {session_name}: {e}")
            return False

    def session_exists(self, session_name: str) -> bool:
        """检查会话是否存在"""
        try:
            result = subprocess.run(
                ['tmux', 'has-session', '-t', session_name],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            return False

    def get_session_info(self, session_name: str) -> Optional[Dict]:
        """获取会话详细信息"""
        try:
            result = subprocess.run(
                ['tmux', 'display-message', '-t', session_name, '-p',
                 '#{session_name}:#{session_created}:#{pane_pid}:#{pane_current_path}:#{window_index}'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return None

            parts = result.stdout.strip().split(':')
            if len(parts) >= 5:
                return {
                    'session_name': parts[0],
                    'created': int(parts[1]),
                    'pane_pid': int(parts[2]),
                    'current_path': parts[3],
                    'window_index': int(parts[4])
                }
            return None
        except Exception as e:
            print(f"Error getting session info: {e}")
            return None

    def find_claude_sessions(self) -> List[Dict]:
        """查找所有运行 Claude 的 tmux 会话"""
        sessions = self.list_sessions()
        claude_sessions = []

        for session in sessions:
            info = self.get_session_info(session['name'])
            if info:
                # 检查是否是 Claude 进程
                try:
                    result = subprocess.run(
                        ['ps', '-p', str(info['pane_pid']), '-o', 'comm='],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )

                    if 'claude' in result.stdout.lower():
                        claude_sessions.append({
                            **session,
                            **info,
                            'is_claude': True
                        })
                except:
                    pass

        return claude_sessions


if __name__ == '__main__':
    # 测试代码
    manager = TmuxManager()

    print("=== Tmux 会话管理器测试 ===\n")

    # 列出现有会话
    sessions = manager.list_sessions()
    print(f"现有 tmux 会话: {len(sessions)}")
    for s in sessions:
        print(f"  - {s['name']} (attached: {s['attached']})")

    print("\n查找 Claude 会话:")
    claude_sessions = manager.find_claude_sessions()
    print(f"找到 {len(claude_sessions)} 个 Claude 会话")
    for s in claude_sessions:
        print(f"  - {s['session_name']} (PID: {s['pane_pid']}, Path: {s['current_path']})")

    # 测试创建会话
    print("\n测试创建新会话...")
    result = manager.create_session('/tmp', 'test-claude-session')
    print(f"创建结果: {result}")

    if result['success']:
        time.sleep(2)

        # 测试发送命令
        print("\n测试发送命令...")
        manager.send_keys('test-claude-session', '你好')

        time.sleep(3)

        # 测试捕获输出
        print("\n捕获输出:")
        content = manager.capture_pane('test-claude-session', lines=50)
        print(content[:500])

        # 清理测试会话
        print("\n清理测试会话...")
        manager.kill_session('test-claude-session')
        print("测试完成")
