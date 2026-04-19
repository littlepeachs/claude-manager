"""
会话监控器
监控 tmux 会话状态，检测需要用户交互的情况
"""

import re
import time
import subprocess
from typing import Dict, Optional, List


class SessionMonitor:
    def __init__(self):
        # 需要用户确认的提示模式
        self.confirmation_patterns = [
            r'\(y/n\)',
            r'\(yes/no\)',
            r'\[y/N\]',
            r'\[Y/n\]',
            r'Continue\?',
            r'Proceed\?',
            r'Are you sure\?',
            r'Do you want to',
            r'Should I',
            r'确认',
            r'是否继续',
            r'password:',
            r'Password:',
            r'passphrase',
        ]

        # Shell进程名称
        self.shell_processes = ['bash', 'zsh', 'sh', 'fish', 'tcsh', 'csh']

        # 记录每个会话的最后活动时间和输出
        self.session_states = {}

    def get_window_process(self, session_name: str, window_index: int) -> Optional[str]:
        """获取tmux窗口中运行的进程名称"""
        try:
            # 获取窗口的pane PID
            result = subprocess.run(
                ['tmux', 'display-message', '-p', '-t', f'{session_name}:{window_index}', '#{pane_pid}'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode != 0:
                return None

            pane_pid = result.stdout.strip()
            if not pane_pid:
                return None

            # 获取该pane下的所有子进程
            ps_result = subprocess.run(
                ['ps', '-o', 'comm=', '-g', pane_pid],
                capture_output=True,
                text=True,
                timeout=2
            )

            if ps_result.returncode != 0:
                return None

            processes = ps_result.stdout.strip().split('\n')
            # 过滤掉空行和ps自身
            processes = [p.strip() for p in processes if p.strip() and p.strip() != 'ps']

            if not processes:
                return None

            # 返回最后一个进程（通常是前台进程）
            return processes[-1].split('/')[-1]  # 只取进程名，不要路径

        except Exception as e:
            return None

    def analyze_output(self, session_id: str, output: str, session_name: str = None, window_index: int = None) -> Dict:
        """
        分析会话输出，检测会话状态

        返回:
        {
            'status': 'running' | 'waiting-confirm' | 'idle',
            'needs_interaction': bool,
            'interaction_type': 'confirmation' | 'idle' | None,
            'message': str,
            'options': List[str]
        }
        """
        current_time = time.time()

        if not output:
            return {
                'status': 'running',
                'needs_interaction': False,
                'interaction_type': None,
                'message': '',
                'options': [],
                'session_id': session_id
            }

        # 获取最后几行输出
        lines = output.strip().split('\n')
        last_lines = lines[-10:] if len(lines) > 10 else lines
        last_output = '\n'.join(last_lines)

        # 获取窗口中运行的进程
        current_process = None
        if session_name and window_index is not None:
            current_process = self.get_window_process(session_name, window_index)

        # 优先检查是否需要确认（黄色状态）
        has_confirmation_prompt = False
        for pattern in self.confirmation_patterns:
            if re.search(pattern, last_output, re.IGNORECASE):
                has_confirmation_prompt = True
                break

        if has_confirmation_prompt:
            # 检查输出是否稳定（2秒内没变化）
            is_stable = False
            if session_id in self.session_states:
                last_state = self.session_states[session_id]
                if last_state['output'] == output:
                    idle_time = current_time - last_state['last_update']
                    if idle_time > 1.5:  # 1.5秒内输出没变化
                        is_stable = True

            if is_stable:
                options = self._extract_options(last_output)
                return {
                    'status': 'waiting-confirm',
                    'needs_interaction': True,
                    'interaction_type': 'confirmation',
                    'message': last_output.strip(),
                    'options': options,
                    'session_id': session_id
                }

        # 检查是否在等待输入（绿色状态）
        # 判断依据：有命令提示符，且输出稳定
        has_prompt = False
        for line in lines[-3:]:  # 检查最后3行
            if self._is_prompt_line(line):
                has_prompt = True
                break

        if has_prompt:
            # 检查输出是否稳定（没有变化）
            if session_id in self.session_states:
                last_state = self.session_states[session_id]
                if last_state['output'] == output:
                    idle_time = current_time - last_state['last_update']
                    if idle_time > 1.5:  # 1.5秒内输出没变化，说明在等待输入
                        return {
                            'status': 'idle',
                            'needs_interaction': True,
                            'interaction_type': 'idle',
                            'message': '等待输入',
                            'options': [],
                            'session_id': session_id
                        }

        # 更新会话状态
        self.session_states[session_id] = {
            'output': output,
            'last_update': current_time,
            'process': current_process
        }

        # 默认为正在运行（红色状态）
        return {
            'status': 'running',
            'needs_interaction': False,
            'interaction_type': None,
            'message': '',
            'options': [],
            'session_id': session_id
        }

    def _extract_options(self, text: str) -> List[str]:
        """从文本中提取选项"""
        options = []

        # 匹配 (y/n) 格式
        match = re.search(r'\(([^)]+)\)', text)
        if match:
            option_text = match.group(1)
            options = [opt.strip() for opt in option_text.split('/')]

        # 匹配 [y/N] 格式
        match = re.search(r'\[([^\]]+)\]', text)
        if match:
            option_text = match.group(1)
            options = [opt.strip() for opt in option_text.split('/')]

        # 如果没有找到选项，返回默认的
        if not options:
            options = ['yes', 'no']

        return options

    def _is_prompt_line(self, line: str) -> bool:
        """检查是否是命令提示符行"""
        prompt_indicators = ['❯', '$', '#', '>', '%']
        # 移除所有空白字符（包括不间断空格\xa0）
        stripped = ''.join(line.split())
        return any(stripped.startswith(indicator) for indicator in prompt_indicators)

    def reset_session(self, session_id: str):
        """重置会话状态"""
        if session_id in self.session_states:
            del self.session_states[session_id]
