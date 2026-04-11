import easyocr
import pyautogui
import pyperclip
import time
import json
import os
import sys
import hashlib
import random
from datetime import datetime, timedelta
from openai import OpenAI
import numpy as np
from PIL import Image
from pathlib import Path
import threading
import keyboard
import math
import schedule
import re
from paddleocr import PaddleOCR

class EasyOCRChatBot:
    """EasyOCR版聊天机器人 - 含存档恢复功能"""

    def levenshtein_distance(self, s1, s2):
        """计算两个字符串的编辑距离（Levenshtein距离）"""
        if len(s1) < len(s2):
            return self.levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def similarity_ratio(self, s1, s2):
        """计算两个字符串的相似度（基于编辑距离）"""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        distance = self.levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))
        return 1.0 - (distance / max_len)
    
    def sleep_monitor(self):
        """睡眠状态监控线程，定期检查"""
        while self.running:
            try:
                self._check_sleep_status()
                time.sleep(30)  # 每30秒检查一次
            except Exception as e:
                self.log_error(f"睡眠监控异常: {e}", category="SLEEP")
                time.sleep(60)

    def contains_keyword_fuzzy(self, text):
        """模糊匹配：检查文本是否包含任何关键字（基于编辑距离）"""
        if not self.keyword_filter_enabled:
            return True

        if not text:
            return False

        # 根据配置决定是否区分大小写
        if not self.keyword_case_sensitive:
            text_lower = text.lower()
            keywords_to_check = [kw.lower() for kw in self.keywords]
        else:
            text_lower = text
            keywords_to_check = self.keywords

        # 对每个关键字进行模糊匹配
        for keyword in keywords_to_check:
            # 如果关键字太长，直接检查是否包含
            if len(keyword) > len(text):
                continue

            # 滑动窗口检查
            for i in range(len(text_lower) - len(keyword) + 1):
                window = text_lower[i:i+len(keyword)]
                similarity = self.similarity_ratio(window, keyword)

                if similarity >= self.keyword_threshold:
                    self.log_debug(f"关键字模糊匹配成功: '{keyword}' 相似度: {similarity:.2f} (窗口: '{window}')", category="FILTER")
                    return True

        return False

    def exact_match_keyword(self, text):
        """精确匹配：检查文本是否包含任何关键字（子串匹配）"""
        if not self.keyword_filter_enabled:
            return True

        if not text:
            return False

        # 根据配置决定是否区分大小写
        if not self.keyword_case_sensitive:
            text_lower = text.lower()
            keywords_to_check = [kw.lower() for kw in self.keywords]
        else:
            text_lower = text
            keywords_to_check = self.keywords

        # 检查是否包含任何关键字
        for keyword in keywords_to_check:
            if keyword in text_lower:
                self.log_debug(f"关键字精确匹配成功: '{keyword}'", category="FILTER")
                return True

        return False

    def should_process_message(self, text):
        """判断是否应该处理该消息（基于关键字过滤）"""
        if not self.keyword_filter_enabled:
            return True

        if self.config.get('keyword_match_mode', 'fuzzy') == 'exact':
            return self.exact_match_keyword(text)
        else:
            return self.contains_keyword_fuzzy(text)

    def __init__(self, config_path="config.json", archive_path=None):
        self.config_path = os.path.abspath(config_path)
        self.archive_path = archive_path
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

        # 初始化日志
        self.log_file = self.log_dir / f"session_{self.session_id}.log"
        self.init_logging()

        # 状态控制
        self.running = True
        self.paused = False
        self.pause_event = threading.Event()
        self.pause_event.set()

        # 主动消息发送标志，用于避免与主循环冲突
        self.sending_active = False

        # 加载配置
        self.config = self.load_config()

        # 初始化关键字过滤器
        self.keywords = self.config.get('keywords', [])
        self.keyword_threshold = self.config.get('keyword_threshold', 0.8)
        self.keyword_case_sensitive = self.config.get('keyword_case_sensitive', False)

        self.keyword_filter_enabled = len(self.keywords) > 0
        if self.keyword_filter_enabled:
            self.log_info(f"关键字过滤器已启用: {self.keywords}", category="FILTER")
            self.log_info(f"匹配阈值: {self.keyword_threshold}, 区分大小写: {self.keyword_case_sensitive}", category="FILTER")
        else:
            self.log_info("关键字过滤器未启用（将匹配所有消息）", category="FILTER")

        # 睡眠模式配置
        self.sleep_config = self.config.get('sleep', {})
        self.sleep_enabled = self.sleep_config.get('enabled', False)
        self.sleep_start_min = self.sleep_config.get('sleep_start_min', 22.0)
        self.sleep_end_max = self.sleep_config.get('sleep_end_max', 23.5)
        self.wake_start_min = self.sleep_config.get('wake_start_min', 6.0)
        self.wake_end_max = self.sleep_config.get('wake_end_max', 8.0)
        self.handle_messages_in_sleep = self.sleep_config.get('handle_messages_in_sleep', False)
        self.sleep_reply = self.sleep_config.get('sleep_reply', '现在在休息，等会儿再聊~')
        self.is_asleep = False
        self.sleep_until = None
        self._schedule_daily_sleep()

        # 指令配置
        self.command_config = self.config.get('command', {})
        self.cmd_prefix = self.command_config.get('prefix', '\\')
        raw_tokens = self.command_config.get('tokens', self.command_config.get('token', []))
        if isinstance(raw_tokens, str):
            self.cmd_tokens = [raw_tokens] if raw_tokens else []
        else:
            self.cmd_tokens = raw_tokens if isinstance(raw_tokens, list) else []
        self.cmd_commands = self.command_config.get('commands', [])
        self.cmd_disabled = False

        # 初始化OCR
        self.reader = self.init_ocr()

        # 初始化API客户端
        self.client = OpenAI(
            api_key=self.config['api_key'],
            base_url=self.config['api_url']
        )

        # 状态变量
        if self.archive_path and os.path.exists(self.archive_path):
            self.load_archive(self.archive_path)
        else:
            self.conversation_history = []
            self.message_count = 0
            self.error_count = 0
            self.null_response_count = 0
            self.total_typed_chars = 0
            self.total_typing_time = 0
            self.avg_response_time = 0
            self.response_times = []
            self.last_message_hash = ""
            self.last_active_message_time = 0
            self.active_message_count = 0
            self.daily_active_count = 0
            self.last_user_message_time = time.time()
            self.last_reset_date = datetime.now().date()

        # 人性化模拟参数
        self.user_typing_speed = random.uniform(3, 6)
        self.conversation_pace = random.choice(['快', '中', '慢'])
        self.last_response_time = 0
        self.consecutive_fast_responses = 0

        self.start_time = time.time()
        self.conversation_start_time = self.start_time

        # 初始化睡眠状态检查
        if self.sleep_enabled:
            self._check_sleep_status()
            if self.is_asleep:
                self.log_info(f"程序启动时处于睡眠模式，将睡到 {self.sleep_until.strftime('%H:%M')}", category="SLEEP")

        try:
            import pyperclipimg
            self.has_pyperclipimg = True
        except ImportError:
            self.has_pyperclipimg = False
            self.log_warning("未安装 pyperclipimg，表情图片功能将不可用。请安装：pip install pyperclipimg", category="IMPORT")

        self.config.setdefault('enable_emoticon', True)
        self.config.setdefault('emoticon_folder', 'Emoticon')

        # 启动线程
        self.command_thread = threading.Thread(target=self.command_listener, daemon=True)
        self.command_thread.start()
        self.active_message_thread = threading.Thread(target=self.active_message_checker, daemon=True)
        self.active_message_thread.start()
        self.sleep_monitor_thread = threading.Thread(target=self.sleep_monitor, daemon=True)
        self.sleep_monitor_thread.start()

        self.log_info("系统初始化完成", category="INIT")
        self.log_info(f"配置文件路径: {self.config_path}", category="CONFIG")
        self.log_info(f"对话节奏: {self.conversation_pace}", category="HUMAN")
        self.log_info(f"主动消息间隔: {self.config.get('active_message_min_interval', 300)}-{self.config.get('active_message_max_interval', 1800)}秒", category="ACTIVE")
        if self.archive_path:
            self.log_info(f"已从存档恢复: {self.archive_path}", category="ARCHIVE")

    def init_logging(self):
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"{'='*60}\n")
            f.write(f"会话开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Python版本: {sys.version}\n")
            f.write(f"EasyOCR版本: {easyocr.__version__}\n")
            f.write(f"配置文件: {self.config_path}\n")
            if hasattr(self, 'archive_path') and self.archive_path:
                f.write(f"加载存档: {self.archive_path}\n")
            f.write(f"{'='*60}\n\n")

    def log(self, level, message, category="GENERAL"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] [{level}] [{category}] {message}"
        print(log_entry)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + "\n")

    def log_info(self, message, category="GENERAL"):
        self.log("INFO", message, category)

    def log_warning(self, message, category="GENERAL"):
        self.log("WARNING", message, category)

    def log_error(self, message, category="GENERAL"):
        self.log("ERROR", message, category)
        self.error_count += 1

    def log_debug(self, message, category="DEBUG"):
        if self.config.get('debug_mode', False):
            self.log("DEBUG", message, category)

    def wait_if_paused(self):
        while self.paused and self.running:
            self.pause_event.wait(timeout=0.5)

    # ======================= 睡眠模式 =======================
    def _schedule_daily_sleep(self):
        """根据配置计算今日的入睡和醒来时间（随机选择窗口内的时间点）"""
        if not self.sleep_enabled:
            return

        now = datetime.now()
        today = now.date()
        
        # 生成今日入睡时间（范围：sleep_start_min ~ sleep_end_max）
        sleep_hour = random.uniform(self.sleep_start_min, self.sleep_end_max)
        sleep_time = datetime.combine(today, datetime.min.time()) + timedelta(hours=sleep_hour)
        
        # 生成醒来时间（范围：wake_start_min ~ wake_end_max）
        wake_hour = random.uniform(self.wake_start_min, self.wake_end_max)
        wake_time = datetime.combine(today, datetime.min.time()) + timedelta(hours=wake_hour)
        
        # 如果醒来时间早于入睡时间（跨天），醒来时间设为第二天
        if wake_time <= sleep_time:
            wake_time += timedelta(days=1)
        
        self.sleep_start_time = sleep_time
        self.wake_time = wake_time
        
        self.log_info(f"今日睡眠计划: 入睡 {sleep_time.strftime('%H:%M')} ~ 醒来 {wake_time.strftime('%H:%M')}", category="SLEEP")

    def _check_sleep_status(self):
        """检查当前是否处于睡眠时间段，并更新 is_asleep 和 sleep_until"""
        if not self.sleep_enabled:
            return
        
        now = datetime.now()
        
        # 如果已经设置了主动睡眠结束时间，并且还没到，则保持睡眠
        if self.sleep_until and now < self.sleep_until:
            if not self.is_asleep:
                self.is_asleep = True
                self.log_info("进入睡眠模式（主动睡眠）", category="SLEEP")
            return
        
        # 检查是否在预定义的睡眠时间窗口内
        if hasattr(self, 'sleep_start_time') and hasattr(self, 'wake_time'):
            # 获取今天的睡眠时间（忽略日期，只比较时间）
            sleep_time_today = self.sleep_start_time.time()
            wake_time_today = self.wake_time.time()
            current_time = now.time()
            
            # 判断是否在睡眠窗口内
            in_sleep_window = False
            
            # 跨天情况（入睡时间 > 醒来时间，如 23:36 入睡，07:05 醒来）
            if sleep_time_today > wake_time_today:
                # 跨天：当前时间 >= 入睡时间 或 当前时间 < 醒来时间
                if current_time >= sleep_time_today or current_time < wake_time_today:
                    in_sleep_window = True
                    # 计算睡眠结束时间（今天的醒来时间，如果已经过了则明天）
                    wake_datetime = datetime.combine(now.date(), wake_time_today)
                    if current_time >= sleep_time_today:
                        # 当前时间在入睡时间之后，醒来时间是明天
                        wake_datetime += timedelta(days=1)
                    self.sleep_until = wake_datetime
            else:
                # 不跨天：当前时间 >= 入睡时间 且 当前时间 < 醒来时间
                if sleep_time_today <= current_time < wake_time_today:
                    in_sleep_window = True
                    self.sleep_until = datetime.combine(now.date(), wake_time_today)
            
            if in_sleep_window:
                if not self.is_asleep:
                    self.is_asleep = True
                    self.log_info(f"进入睡眠模式（计划睡眠: {self.sleep_start_time.strftime('%H:%M')} - {self.wake_time.strftime('%H:%M')}）", category="SLEEP")
                return
        
        # 不在睡眠窗口
        if self.is_asleep:
            self.is_asleep = False
            self.sleep_until = None
            self.log_info("退出睡眠模式", category="SLEEP")

    def is_sleeping(self):
        return self.sleep_enabled and self.is_asleep

    def handle_sleep_reply(self, user_message):
        if not self.is_sleeping():
            return False
        if not self.handle_messages_in_sleep:
            if self.sleep_reply:
                self.send_message_human_like([self.sleep_reply])
            else:
                self.log_info("睡眠模式：静默忽略消息", category="SLEEP")
            return True
        else:
            return False

    # ======================= 指令识别 =======================
    def check_command(self, text):
        """检查消息是否为指令，只要消息中包含指令前缀和有效令牌即可"""
        if not text or self.cmd_disabled:
            return False
        
        # 检查是否包含指令前缀
        if self.cmd_prefix not in text:
            return False
        
        # 检查是否包含有效令牌
        token_found = False
        if self.cmd_tokens:
            for token in self.cmd_tokens:
                if token in text:
                    token_found = True
                    break
        else:
            token_found = True  # 未配置令牌则不需要验证
        
        if not token_found:
            # 直接复制粘贴权限不足消息
            self.direct_send_message("权限不足，无法执行指令。")
            self.log_info(f"指令权限不足: {text}", category="COMMAND")
            return True
        
        # 提取指令和参数
        prefix_index = text.find(self.cmd_prefix)
        if prefix_index == -1:
            return False
        
        cmd_part = text[prefix_index + len(self.cmd_prefix):].strip()
        
        # 移除所有令牌
        for token in self.cmd_tokens:
            cmd_part = cmd_part.replace(token, "").strip()
        
        if not cmd_part:
            return False
        
        # 解析指令
        parts = cmd_part.split()
        if not parts:
            return False
        
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if '=' in cmd:
            cmd, arg_eq = cmd.split('=', 1)
            args = [arg_eq] + args
        
        if self.cmd_commands and cmd not in self.cmd_commands:
            self.direct_send_message(f"未知指令: {cmd}。可用指令: {', '.join(self.cmd_commands)}")
            return True
        
        self.log_info(f"执行指令: {cmd} 参数: {args}", category="COMMAND")
        
        # 执行指令（直接输出结果）
        if cmd == "state":
            self.direct_send_status()
        elif cmd == "active":
            # 主动消息需要模拟打字以显得自然，但指令触发时保持原有逻辑
            self.force_active_message()
        elif cmd == "sleep":
            if args:
                try:
                    hours = float(args[0])
                    self.direct_go_to_sleep(hours)
                except ValueError:
                    self.direct_send_message("睡眠时间参数错误，应为数字小时数。")
            else:
                self.direct_go_to_sleep()
        elif cmd == "pause":
            self.direct_toggle_pause()
        elif cmd == "help":
            self.direct_send_help()
        else:
            self.direct_send_message(f"指令 '{cmd}' 已执行，但未实现具体功能。")
        
        return True

    def direct_send_message(self, message):
        """直接发送消息（不模拟打字，用于指令回复）"""
        try:
            # 聚焦输入框
            pyautogui.click()
            time.sleep(0.1)
            
            # 直接复制粘贴整段消息
            pyperclip.copy(message)
            time.sleep(0.05)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)
            
            # 发送
            pyautogui.press('enter')
            
            self.log_info(f"直接发送指令回复: {message[:50]}...", category="COMMAND")
            
        except Exception as e:
            self.log_error(f"直接发送消息失败: {e}", category="COMMAND")

    def direct_send_status(self):
        """直接发送状态信息（不模拟打字）"""
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        active_msg_rate = self.active_message_count / (elapsed / 3600) if elapsed > 0 else 0
        avg_speed = self.total_typed_chars / self.total_typing_time if self.total_typing_time > 0 else 0
        
        status = (
            f"【运行状态】\n"
            f"运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}\n"
            f"系统状态: {'暂停中' if self.paused else '运行中'}\n"
            f"睡眠状态: {'睡眠中' if self.is_sleeping() else '清醒'}\n"
            f"对话节奏: {self.config.get('human_pace', '平衡')}\n"
            f"连续快速回复: {self.consecutive_fast_responses}\n"
            f"平均响应时间: {self.avg_response_time:.2f}秒\n"
            f"\n【主动消息统计】\n"
            f"今日主动: {self.daily_active_count}/{self.config.get('max_daily_active_messages', 10)}\n"
            f"总主动次数: {self.active_message_count}\n"
            f"主动频率: {active_msg_rate:.2f}次/小时\n"
            f"上次主动: {self.format_time_ago(self.last_active_message_time)}\n"
            f"上次用户: {self.format_time_ago(self.last_user_message_time)}\n"
            f"\n【会话统计】\n"
            f"消息处理: {self.message_count}\n"
            f"错误计数: {self.error_count}\n"
            f"Null回复: {self.null_response_count}\n"
            f"历史记录: {len(self.conversation_history)//2}\n"
            f"\n【打字统计】\n"
            f"总输入字符: {self.total_typed_chars}\n"
            f"总输入时间: {self.total_typing_time:.1f}秒\n"
            f"平均速度: {avg_speed:.1f}字符/秒"
        )
        
        self.direct_send_message(status)

    def go_to_sleep(self, hours=None):
        """立即进入睡眠模式，持续指定小时数；若无参数则按配置文件计划入睡"""
        if hours is not None:
            # 主动睡眠指定时长
            self.sleep_until = datetime.now() + timedelta(hours=hours)
            self.is_asleep = True
            self.log_info(f"主动进入睡眠模式，持续 {hours} 小时，直到 {self.sleep_until.strftime('%H:%M')}", category="SLEEP")
            self.direct_send_message(f"好的，我去休息 {hours} 小时。有急事再叫我~")
        else:
            # 按当天配置的睡眠时间入睡
            if self.sleep_enabled and hasattr(self, 'sleep_start_time'):
                now = datetime.now()
                sleep_start = self.sleep_start_time
                
                # 如果当前时间已经过了今天的入睡时间，则睡到明天的醒来时间
                if now.time() >= sleep_start.time():
                    self.sleep_until = datetime.combine(now.date() + timedelta(days=1), self.wake_time.time())
                else:
                    self.sleep_until = datetime.combine(now.date(), self.wake_time.time())
                
                self.is_asleep = True
                self.log_info(f"主动进入睡眠模式，将睡到 {self.sleep_until.strftime('%H:%M')}", category="SLEEP")
                self.direct_send_message("我去睡觉啦，明天见~")
            else:
                self.direct_send_message("睡眠模式未配置，无法主动入睡。")

    def direct_toggle_pause(self):
        """直接切换暂停状态（不模拟打字）"""
        self.paused = not self.paused
        if self.paused:
            self.pause_event.clear()
            self.log_info("系统已暂停 - 按 Pause/F8 键继续", category="PAUSE")
            self.direct_send_message("系统已暂停")
        else:
            self.pause_event.set()
            self.log_info("系统已继续运行", category="PAUSE")
            self.direct_send_message("系统已继续运行")

    def direct_send_help(self):
        """直接发送帮助信息（不模拟打字）"""
        help_text = "【可用指令】（消息中同时包含指令前缀和令牌即可）\n"
        help_text += f"  {self.cmd_prefix}state - 显示运行状态\n"
        help_text += f"  {self.cmd_prefix}active - 强制发送主动消息\n"
        help_text += f"  {self.cmd_prefix}sleep [小时] - 立即入睡（可选小时数）\n"
        help_text += f"  {self.cmd_prefix}pause - 切换暂停/继续\n"
        help_text += f"  {self.cmd_prefix}help - 显示本帮助\n"
        self.direct_send_message(help_text)

    def go_to_sleep(self, hours=None):
        if hours is not None:
            self.sleep_until = datetime.now() + timedelta(hours=hours)
            self.is_asleep = True
            self.log_info(f"主动进入睡眠模式，持续 {hours} 小时", category="SLEEP")
            self.send_message_human_like([f"好的，我去休息 {hours} 小时。有急事再叫我~"])
        else:
            if self.sleep_enabled and hasattr(self, 'sleep_start_time'):
                self.sleep_until = self.sleep_start_time
                self.is_asleep = True
                self.log_info("主动进入睡眠模式，按当日计划入睡", category="SLEEP")
                self.send_message_human_like(["我去睡觉啦，明天见~"])
            else:
                self.send_message_human_like(["睡眠模式未配置，无法主动入睡。"])

    def send_help_message(self):
        help_text = "可用指令：\n"
        help_text += f"  {self.cmd_prefix}state - 显示运行状态\n"
        help_text += f"  {self.cmd_prefix}active - 强制发送主动消息\n"
        help_text += f"  {self.cmd_prefix}sleep [小时] - 立即入睡（可选小时数）\n"
        help_text += f"  {self.cmd_prefix}pause - 切换暂停/继续\n"
        help_text += f"  {self.cmd_prefix}help - 显示本帮助\n"
        if self.cmd_tokens:
            help_text += f"  指令后需附带权限令牌"
        self.send_message_human_like([help_text])

    # ======================= 原有方法（部分有修改） =======================
    def command_listener(self):
        while self.running:
            try:
                if keyboard.is_pressed('pause') or keyboard.is_pressed('f8'):
                    self.toggle_pause()
                    time.sleep(0.5)
                elif keyboard.is_pressed('ctrl+p'):
                    if not self.paused:
                        self.paused = True
                        self.pause_event.clear()
                        self.log_info("用户强制暂停", category="COMMAND")
                    time.sleep(0.5)
                elif keyboard.is_pressed('ctrl+r'):
                    if self.paused:
                        self.paused = False
                        self.pause_event.set()
                        self.log_info("用户强制继续", category="COMMAND")
                    time.sleep(0.5)
                elif keyboard.is_pressed('s'):
                    self.print_status()
                    time.sleep(0.5)
                elif keyboard.is_pressed('l'):
                    self.log_info(f"日志文件: {self.log_file}", category="COMMAND")
                    time.sleep(0.5)
                elif keyboard.is_pressed('a'):
                    self.force_active_message()
                    time.sleep(0.5)
                elif keyboard.is_pressed('q'):
                    self.log_info("用户请求退出", category="COMMAND")
                    self.running = False
                    self.pause_event.set()
                    break
                elif keyboard.is_pressed('f5'):
                    self.cmd_disabled = not self.cmd_disabled
                    status = "禁用" if self.cmd_disabled else "启用"
                    self.log_info(f"指令识别已{status}", category="COMMAND")
                    self.send_message_human_like([f"指令识别已{status}"])
                    time.sleep(0.5)
                time.sleep(0.1)
            except Exception as e:
                self.log_error(f"命令监听异常: {e}", category="COMMAND")
                time.sleep(0.5)

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.pause_event.clear()
            self.log_info("系统已暂停 - 按 Pause/F8 键继续", category="PAUSE")
        else:
            self.pause_event.set()
            self.log_info("系统已继续运行", category="PAUSE")

    def active_message_checker(self):
        while self.running:
            try:
                self.wait_if_paused()
                if self.is_sleeping():
                    time.sleep(30)
                    continue
                today = datetime.now().date()
                if today != self.last_reset_date:
                    self.daily_active_count = 0
                    self.last_reset_date = today
                    self.log_info("每日主动消息计数已重置", category="ACTIVE")
                if self.should_send_active_message():
                    self.send_active_message()
                time.sleep(30)
            except Exception as e:
                self.log_error(f"主动消息检查异常: {e}", category="ACTIVE")
                time.sleep(60)

    def should_send_active_message(self):
        if self.is_sleeping():
            return False
        if self.sending_active:
            return False
        if len(self.conversation_history) == 0:
            return False
        max_daily = self.config.get('max_daily_active_messages', 10)
        if self.daily_active_count >= max_daily:
            return False
        min_interval = self.config.get('active_message_min_interval', 300)
        if time.time() - self.last_active_message_time < min_interval:
            return False
        time_since_user = time.time() - self.last_user_message_time
        if time_since_user < self.config.get('min_user_inactive_time', 60):
            return False
        session_duration = time.time() - self.conversation_start_time
        hours = session_duration / 3600
        base_probability = self.config.get('active_message_frequency', 1.0) / 3600 * 300
        if hours < 0.5:
            probability = base_probability * 0.5
        elif hours < 2:
            probability = base_probability
        elif hours < 4:
            probability = base_probability * 0.7
        else:
            probability = base_probability * 0.3
        return random.random() < probability

    def send_active_message(self):
        if self.sending_active:
            return
        self.sending_active = True
        try:
            self.log_info("准备发送主动消息", category="ACTIVE")
            message = self.get_active_message()
            if not message:
                self.log_info("主动消息生成失败或内容无效", category="ACTIVE")
                return
            self.log_info(f"生成的主动消息: {message[:100]}...", category="ACTIVE")
            delimiter = self.config.get('segment_delimiter', '||')
            if delimiter in message:
                segments = [seg.strip() for seg in message.split(delimiter) if seg.strip()]
                self.log_info(f"主动消息包含分隔符，已分割为 {len(segments)} 段", category="ACTIVE")
            else:
                segments = [message]
            think_time = random.uniform(2, 5)
            self.log_info(f"主动消息思考时间: {think_time:.1f}秒", category="ACTIVE")
            time.sleep(think_time)
            previous_segment = ""
            for i, segment in enumerate(segments, 1):
                pyautogui.click()
                time.sleep(0.2)
                self.log_info(f"正在输入段落 [{i}/{len(segments)}]: {len(segment)}字符", category="ACTIVE")
                self.simulate_human_typing(segment)
                pyautogui.press('enter')
                self.log_info(f"段落 [{i}/{len(segments)}] 发送完成", category="ACTIVE")
                if i < len(segments):
                    delay = self.calculate_human_segment_delay(i-1, len(segments), segment, previous_segment)
                    self.log_info(f"等待段落间隔: {delay:.1f}秒", category="ACTIVE")
                    time.sleep(delay)
                previous_segment = segment
            self.last_active_message_time = time.time()
            self.active_message_count += 1
            self.daily_active_count += 1
            self.message_count += 1
            self.conversation_history.append({"role": "assistant", "content": message})
            self.log_info(f"主动消息发送成功 [#{self.active_message_count}, 今日: {self.daily_active_count}]", category="ACTIVE")
        except Exception as e:
            self.log_error(f"发送主动消息失败: {e}", category="ACTIVE")
        finally:
            self.sending_active = False

    def get_active_message(self):
        try:
            system_prompt = self.get_system_prompt()
            context = self.generate_active_message_context()
            messages = [
                {"role": "system", "content": f"""你是一个真实的聊天对象，会主动发起对话。
你的基本人格设定：
{system_prompt}

主动消息规则：
1. 不要问'在吗'、'你好'等无聊问题
2. 要基于之前的对话内容自然延伸
3. 语气要自然，不要像机器人
4. 可以是提问、分享想法、或者延续话题
5. 主动消息要简短自然（20-100字）
6. 如果合适，可以使用 '{self.config.get('segment_delimiter', '||')}' 分隔符来分段发送较长的消息"""},
                {"role": "user", "content": f"""基于以下对话历史，生成一条自然的主动消息：

{context}

要求：
1. 不要问'在吗'等无意义的问题
2. 要与之前的对话内容相关
3. 语气自然，像真人一样
4. 长度控制在20-100字之间
5. 可以提问、分享想法或延续话题
6. 如果需要发送较长的内容，可以用 '{self.config.get('segment_delimiter', '||')}' 分隔成多个段落

请直接输出主动消息内容："""}
            ]
            self.log_debug("正在生成主动消息...", category="ACTIVE")
            response = self.client.chat.completions.create(
                model=self.config['model_name'],
                messages=messages,
                temperature=0.8,
                max_tokens=300,
                timeout=15
            )
            message = response.choices[0].message.content.strip()
            message = message.strip('"\' \n')
            if len(message) < 5:
                self.log_warning(f"主动消息太短: {len(message)}字符", category="ACTIVE")
                return None
            self.log_debug(f"主动消息生成成功: {len(message)}字符", category="ACTIVE")
            return message
        except Exception as e:
            self.log_error(f"生成主动消息失败: {e}", category="ACTIVE")
            return None

    def generate_active_message_context(self):
        if len(self.conversation_history) < 2:
            return "对话刚刚开始，还没有历史消息。"
        recent = self.conversation_history[-6:]
        context_lines = []
        for msg in recent:
            role = "用户" if msg['role'] == 'user' else "我"
            content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            context_lines.append(f"{role}: {content}")
        return "\n".join(context_lines)

    def force_active_message(self):
        if self.paused:
            self.log_info("系统暂停中，无法发送主动消息", category="COMMAND")
            return
        if self.is_sleeping():
            self.log_info("睡眠模式中，无法发送主动消息", category="COMMAND")
            return
        self.log_info("用户强制发送主动消息", category="COMMAND")
        self.send_active_message()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.log_info(f"配置文件加载成功: {self.config_path}", category="CONFIG")
                return config
            except Exception as e:
                self.log_error(f"配置文件加载失败: {e}", category="CONFIG")
                return self.setup_config()
        else:
            self.log_info("未找到配置文件，启动配置向导", category="CONFIG")
            return self.setup_config()

    def setup_config(self):
        print("\n" + "="*60)
        print(" PaperAiChat 聊天机器人配置向导 ")
        print("="*60)
        config = {}

        print("\n[1/10] API 配置")
        config['api_key'] = input("   API密钥: ").strip()
        config['api_url'] = input("   API网址: ").strip()
        config['model_name'] = input("   模型名称: ").strip()

        print("\n[2/10] OCR 配置")
        print("   支持的语言: ch_sim(简体中文), en(英文), ch_tra(繁体中文), ja(日文), ko(韩文)")
        langs = input("   识别语言 (用逗号分隔, 默认: ch_sim,en): ").strip()
        config['ocr_langs'] = langs.split(',') if langs else ['ch_sim', 'en']
        config['use_gpu'] = input("   使用GPU加速? (y/n, 默认: n): ").strip().lower() == 'y'

        print("\n[3/10] 消息区域配置")
        config['message_region'] = self.select_region_interactive()

        print("\n[4/10] 提示词配置")
        prompt_file = input("   提示词文件路径 (直接回车跳过): ").strip()
        if prompt_file:
            config['prompt_file'] = prompt_file
        else:
            config['system_prompt'] = input("   系统提示词: ").strip()

        print("\n[5/10] 运行参数")
        config['check_interval'] = float(input("   检查间隔(秒, 默认: 1.0): ") or 1.0)
        config['debug_mode'] = input("   调试模式? (y/n, 默认: n): ").strip().lower() == 'y'
        config['save_screenshots'] = input("   保存截图? (y/n, 默认: n): ").strip().lower() == 'y'

        print("\n[6/10] 对话行为")
        config['max_history'] = int(input("   最大历史记录数 (默认: 10): ") or 10)
        config['min_message_length'] = int(input("   最小消息长度 (默认: 2): ") or 2)
        config['segment_delimiter'] = input("   分段符 (默认: ||): ") or "||"
        config['ignore_null_response'] = input("   忽略null回复? (y/n, 默认: y): ").strip().lower() != 'n'

        print("\n[7/10] 关键字过滤配置")
        print("   设置关键字后，只有包含这些关键字的消息才会被回复")
        print("   多个关键字用逗号分隔（例如：你好,在吗,help）")
        keywords_input = input("   请输入关键字（留空则不过滤）: ").strip()
        if keywords_input:
            config['keywords'] = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]
            config['keyword_match_mode'] = input("   匹配模式 (fuzzy=模糊匹配, exact=精确匹配, 默认: fuzzy): ").strip() or 'fuzzy'
            config['keyword_threshold'] = float(input("   模糊匹配阈值 (0.5-1.0, 默认: 0.8): ").strip() or 0.8)
            config['keyword_case_sensitive'] = input("   区分大小写? (y/n, 默认: n): ").strip().lower() == 'y'
            config['log_ignored_messages'] = input("   记录被忽略的消息? (y/n, 默认: n): ").strip().lower() == 'y'
        else:
            config['keywords'] = []

        print("\n[8/10] 人性化模拟配置")
        print("   请选择对话节奏偏好:")
        print("   1. 快速响应 (适合简单对话)")
        print("   2. 平衡模式 (默认)")
        print("   3. 慢速响应 (更像真人)")
        pace_choice = input("   请选择 (1/2/3, 默认: 2): ").strip()
        if pace_choice == '1':
            config['human_pace'] = '快速'
            config['base_delay_factor'] = 0.5
            config['max_response_time'] = 3
        elif pace_choice == '3':
            config['human_pace'] = '慢速'
            config['base_delay_factor'] = 1.5
            config['max_response_time'] = 8
        else:
            config['human_pace'] = '平衡'
            config['base_delay_factor'] = 1.0
            config['max_response_time'] = 5
        config['min_think_time'] = float(input("   最小思考时间(秒, 默认: 1.0): ") or 1.0)
        config['max_think_time'] = float(input("   最大思考时间(秒, 默认: 3.0): ") or 3.0)
        config['typing_speed_min'] = float(input("   最小打字速度(字符/秒, 默认: 3): ") or 3)
        config['typing_speed_max'] = float(input("   最大打字速度(字符/秒, 默认: 8): ") or 8)
        config['show_typing_indicator'] = input("   显示正在输入提示? (y/n, 默认: y): ").strip().lower() != 'n'
        config['adaptive_speed'] = input("   自适应速度? (根据消息长度调整, y/n, 默认: y): ").strip().lower() != 'n'

        print("\n[9/10] 主动消息配置")
        print("   主动消息频率 (每小时主动次数):")
        print("   0 = 从不主动")
        print("   0.5 = 每2小时1次")
        print("   1 = 每小时1次")
        print("   2 = 每小时2次")
        print("   3 = 每小时3次")
        freq = float(input("   请选择频率 (默认: 1): ") or 1)
        config['active_message_frequency'] = max(0, min(freq, 5))
        if config['active_message_frequency'] > 0:
            avg_interval = 3600 / config['active_message_frequency']
            config['active_message_min_interval'] = int(avg_interval * 0.7)
            config['active_message_max_interval'] = int(avg_interval * 1.3)
        else:
            config['active_message_min_interval'] = 999999
            config['active_message_max_interval'] = 999999
        config['max_daily_active_messages'] = int(input("   每日最大主动消息数 (默认: 10): ") or 10)
        config['min_user_inactive_time'] = int(input("   用户多久不活跃才主动(秒, 默认: 60): ") or 60)
        config['active_message_cooldown'] = int(input("   主动后冷却时间(秒, 默认: 300): ") or 300)

        print("\n[10/10] 睡眠模式配置")
        enable_sleep = input("   启用睡眠模式? (y/n, 默认: n): ").strip().lower() == 'y'
        if enable_sleep:
            config['sleep'] = {
                "enabled": True,
                "sleep_start_min": float(input("   最早入睡时间(小时, 0-23, 默认: 22): ") or 22),
                "sleep_end_max": float(input("   最晚入睡时间(小时, 0-23, 默认: 23.5): ") or 23.5),
                "wake_start_min": float(input("   最早醒来时间(小时, 0-23, 默认: 6): ") or 6),
                "wake_end_max": float(input("   最晚醒来时间(小时, 0-23, 默认: 8): ") or 8),
                "handle_messages_in_sleep": input("   睡眠期间处理新消息? (y/n, 默认: n): ").strip().lower() == 'y',
                "sleep_reply": input("   睡眠回复语 (默认: 现在在休息，等会儿再聊~): ").strip() or "现在在休息，等会儿再聊~"
            }
        else:
            config['sleep'] = {"enabled": False}

        print("\n指令配置")
        enable_cmd = input("   启用指令识别? (y/n, 默认: y): ").strip().lower() != 'n'
        if enable_cmd:
            prefix = input("   指令引导符 (默认: \\\\): ").strip()
            if not prefix:
                prefix = '\\'
            tokens_input = input("   权限令牌 (多个用逗号分隔, 留空则不检查): ").strip()
            tokens = [t.strip() for t in tokens_input.split(',')] if tokens_input else []
            config['command'] = {
                "prefix": prefix,
                "tokens": tokens,
                "commands": ["state", "active", "sleep", "pause", "help"]
            }
        else:
            config['command'] = {"enabled": False}

        print("\n时间注入配置")
        inject_time = input("   在系统提示词中注入当前时间? (y/n, 默认: y): ").strip().lower() != 'n'
        if inject_time:
            time_format = input("   时间格式 (默认: %Y年%m月%d日 %H:%M:%S): ").strip()
            if not time_format:
                time_format = "%Y年%m月%d日 %H:%M:%S"
            config['time_injection'] = {
                "enabled": True,
                "format": time_format
            }
        else:
            config['time_injection'] = {"enabled": False}

        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        self.log_info(f"配置已保存: {self.config_path}", category="CONFIG")
        return config

    def select_region_interactive(self):
        print("\n   请将鼠标移动到消息区域的左上角")
        input("   按 Enter 键继续...")
        time.sleep(1)
        x1, y1 = pyautogui.position()
        print(f"   左上角坐标: ({x1}, {y1})")
        print("\n   请将鼠标移动到消息区域的右下角")
        input("   按 Enter 键继续...")
        time.sleep(1)
        x2, y2 = pyautogui.position()
        print(f"   右下角坐标: ({x2}, {y2})")
        region = {
            'x1': min(x1, x2),
            'y1': min(y1, y2),
            'x2': max(x1, x2),
            'y2': max(y1, y2),
            'width': abs(x2 - x1),
            'height': abs(y2 - y1)
        }
        self.log_info(f"消息区域已选定: {region}", category="CONFIG")
        return region

    def get_system_prompt(self):
        base_prompt = ""
        if self.config.get('prompt_file'):
            try:
                with open(self.config['prompt_file'], 'r', encoding='utf-8') as f:
                    base_prompt = f.read().strip()
                self.log_debug(f"从文件加载提示词: {len(base_prompt)} 字符", category="PROMPT")
            except Exception as e:
                self.log_error(f"读取提示词文件失败: {e}", category="PROMPT")
                base_prompt = self.config.get('system_prompt', '你是一个友好的AI助手。模拟真实对话，不使用markdown格式。模拟真实线上聊天，用"||"将回复隔开。每段一般不超过10字。网络聊天，尽量少用标点。不要出现换行符。如果用户的内容是完全无法理解的奇异内容（考虑识图错误）或你完全无法回复，输出"null"')
        else:
            base_prompt = self.config.get('system_prompt', '你是一个友好的AI助手。')
        time_injection = self.config.get('time_injection', {})
        if time_injection.get('enabled', False):
            time_str = datetime.now().strftime(time_injection.get('format', "%Y年%m月%d日 %H:%M:%S"))
            base_prompt = f"{base_prompt}\n\n当前时间：{time_str}"
        return base_prompt

    def init_ocr(self, max_retries=3):
        """初始化 PaddleOCR 引擎 (2.x 版本)"""
        if not hasattr(self, 'error_count'):
            self.error_count = 0
        
        for attempt in range(max_retries):
            try:
                self.log_info(f"初始化 PaddleOCR 引擎 (尝试 {attempt + 1}/{max_retries})...", category="OCR")
                
                from paddleocr import PaddleOCR
                self.ocr_engine = PaddleOCR(
                    use_angle_cls=True,      # 启用方向分类
                    lang='ch',               # 中英文
                    use_gpu=False,           # 使用 CPU
                    show_log=False           # 关闭日志
                )
                
                self.log_info("PaddleOCR 引擎初始化成功", category="OCR")
                return True
                
            except Exception as e:
                self.log_error(f"OCR 初始化失败: {str(e)}", category="OCR")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    self.log_info(f"等待 {wait_time} 秒后重试...", category="OCR")
                    time.sleep(wait_time)
                else:
                    self.log_error("OCR 引擎初始化失败，程序退出", category="FATAL")
                    sys.exit(1)

    def capture_screen_region(self):
        region = self.config['message_region']
        try:
            screenshot = pyautogui.screenshot(
                region=(region['x1'], region['y1'], region['width'], region['height'])
            )
            if self.config.get('save_screenshots', False):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                screenshot_path = self.log_dir / f"screenshot_{timestamp}.png"
                screenshot.save(screenshot_path)
                self.log_debug(f"截图已保存: {screenshot_path}", category="SCREEN")
            return screenshot
        except Exception as e:
            self.log_error(f"截图失败: {e}", category="SCREEN")
            return None

    def extract_text_from_image(self, image):
        """使用 PaddleOCR 识别图片中的文字 (2.x 版本)"""
        if image is None:
            return ""
        
        try:
            img_array = np.array(image)
            
            start_time = time.time()
            # 2.x 版本使用 cls=True 参数
            result = self.ocr_engine.ocr(img_array, cls=True)
            elapsed = (time.time() - start_time) * 1000
            
            if not result or not result[0]:
                self.log_debug(f"OCR 未识别到文字: {elapsed:.0f}ms", category="OCR")
                return ""
            
            lines = []
            for line in result[0]:
                # 2.x 格式: [[bbox], (text, confidence)]
                text = line[1][0]
                confidence = line[1][1]
                lines.append(text)
                self.log_debug(f"  识别: '{text}' (置信度: {confidence:.2f})", category="OCR")
            
            text = ' '.join(lines).strip()
            
            self.log_debug(f"OCR 识别完成: {elapsed:.0f}ms, 共 {len(lines)} 行", category="OCR")
            return text
            
        except Exception as e:
            self.log_error(f"OCR 识别失败: {e}", category="OCR")
            return ""
            
        except Exception as e:
            self.log_error(f"OCR 识别失败: {e}", category="OCR")
            return ""

    def calculate_hash(self, text):
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def is_new_message(self, text):
        if not text or len(text) < self.config.get('min_message_length', 2):
            return False
        text_hash = self.calculate_hash(text)
        if text_hash != self.last_message_hash:
            self.last_message_hash = text_hash
            return True
        return False

    def is_null_response(self, text):
        if not text:
            return True
        cleaned = text.strip().lower()
        null_patterns = ['null', 'none', 'nil', 'undefined', '空', '无', '没有']
        return cleaned in null_patterns or cleaned == ''

    def segment_message(self, text):
        delimiter = self.config.get('segment_delimiter', '||')
        if delimiter in text:
            segments = [seg.strip() for seg in text.split(delimiter) if seg.strip()]
            self.log_info(f"消息已分割为 {len(segments)} 段", category="SEGMENT")
            return segments
        else:
            return [text]

    def calculate_human_think_time(self, message_length, response_length):
        base_think = random.uniform(
            self.config.get('min_think_time', 1.0),
            self.config.get('max_think_time', 3.0)
        )
        if message_length > 100:
            base_think += random.uniform(1.0, 2.0)
        elif message_length > 50:
            base_think += random.uniform(0.5, 1.0)
        if response_length > 200:
            base_think += random.uniform(1.5, 3.0)
        elif response_length > 100:
            base_think += random.uniform(0.8, 1.5)
        pace_factor = self.config.get('base_delay_factor', 1.0)
        if self.consecutive_fast_responses > 2:
            base_think *= (1 + self.consecutive_fast_responses * 0.2)
        if self.config.get('adaptive_speed', True) and response_length > 300:
            base_think *= 0.8
        think_time = base_think * pace_factor
        max_time = self.config.get('max_response_time', 5)
        think_time = min(think_time, max_time)
        return think_time

    def calculate_typing_speed(self, text_length):
        min_speed = self.config.get('typing_speed_min', 3)
        max_speed = self.config.get('typing_speed_max', 8)
        if text_length < 20:
            speed = random.uniform(min_speed, max_speed)
        elif text_length < 50:
            speed = random.uniform(min_speed + 1, max_speed)
        else:
            speed = random.uniform(min_speed, max_speed - 1)
        speed *= random.uniform(0.9, 1.1)
        return speed

    def simulate_human_typing(self, text):
        if not text:
            return
        text_only = self.strip_emoticon_tags(text)
        typing_speed = self.calculate_typing_speed(len(text_only))
        expected_time = len(text_only) / typing_speed
        self.total_typed_chars += len(text_only)
        self.total_typing_time += expected_time
        self.log_info(f"开始打字: 文本长度 {len(text_only)} 字符, 速度: {typing_speed:.1f}字符/秒, 预计文本时间: {expected_time:.1f}秒", category="TYPING")
        i = 0
        n = len(text)
        while i < n:
            char = text[i]
            if char == '[' and self.config.get('enable_emoticon', True) and self.has_pyperclipimg:
                j = text.find(']', i + 1)
                if j != -1:
                    img_name = text[i+1:j].strip()
                    if img_name:
                        self.process_emoticon(img_name)
                    i = j + 1
                    continue
            pyperclip.copy(char)
            time.sleep(0.01)
            pyautogui.hotkey('ctrl', 'v')
            base_interval = 1.0 / typing_speed
            interval = base_interval * random.uniform(0.8, 1.2)
            if char in ['.', '。', '!', '！', '?', '？', ',', '，', ';', '；', '\n']:
                interval += random.uniform(0.1, 0.3)
            if (i + 1) % 10 == 0 or i == n - 1:
                progress = (i + 1) / n * 100
                self.log_debug(f"打字进度: {progress:.0f}% ({i+1}/{n}总字符)", category="TYPING")
            time.sleep(interval)
            i += 1
        final_pause = random.uniform(0.2, 0.5)
        time.sleep(final_pause)
        self.log_debug(f"段落输入完成: 共处理 {n} 字符（含表情标记）", category="TYPING")

    def strip_emoticon_tags(self, text):
        return re.sub(r'\[[^\]]*\]', '', text)

    def process_emoticon(self, img_name):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            emoticon_folder = self.config.get('emoticon_folder', 'Emoticon')
            img_path = os.path.join(script_dir, emoticon_folder, img_name)
            if not os.path.splitext(img_path)[1]:
                for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                    test_path = img_path + ext
                    if os.path.exists(test_path):
                        img_path = test_path
                        break
            if not os.path.exists(img_path):
                self.log_error(f"表情图片不存在: {img_path}", category="EMOTICON")
                return
            import pyperclipimg
            pyperclipimg.copy(img_path)
            self.log_info(f"已复制表情图片: {img_name}", category="EMOTICON")
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.2)
            pyautogui.press('enter')
            self.log_info("表情图片已发送", category="EMOTICON")
            time.sleep(random.uniform(0.5, 1.0))
        except Exception as e:
            self.log_error(f"处理表情图片失败: {e}", category="EMOTICON")

    def get_ai_response(self, message):
        try:
            system_prompt = self.get_system_prompt()
            messages = [{"role": "system", "content": system_prompt}]
            for hist in self.conversation_history[-self.config['max_history']:]:
                messages.append(hist)
            messages.append({"role": "user", "content": message})
            self.log_debug(f"发送API请求: {self.config['model_name']}", category="API")
            start_time = time.time()
            response = self.client.chat.completions.create(
                model=self.config['model_name'],
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                timeout=30
            )
            elapsed = (time.time() - start_time) * 1000
            reply = response.choices[0].message.content
            original_reply = reply
            reply = self.convert_empty_lines_to_delimiter(reply)
            if original_reply != reply:
                self.log_info(f"空行转换: 将 {reply.count('||')} 个空行转换为分隔符", category="FORMAT")
            self.log_info(f"API响应: {elapsed:.0f}ms, 长度: {len(reply)}", category="API")
            if self.config.get('ignore_null_response', True) and self.is_null_response(reply):
                self.null_response_count += 1
                self.log_info(f"检测到null回复 (总计: {self.null_response_count})", category="API")
                return None
            self.conversation_history.append({"role": "user", "content": message})
            self.conversation_history.append({"role": "assistant", "content": reply})
            max_history = self.config['max_history']
            if len(self.conversation_history) > max_history * 2:
                self.conversation_history = self.conversation_history[-max_history*2:]
            self.response_times.append(elapsed / 1000)
            if len(self.response_times) > 10:
                self.response_times.pop(0)
            self.avg_response_time = sum(self.response_times) / len(self.response_times)
            return reply
        except Exception as e:
            self.log_error(f"API请求失败: {e}", category="API")
            return None

    def convert_empty_lines_to_delimiter(self, text):
        if not text:
            return text
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        result = []
        empty_line_count = 0
        last_was_empty = False
        for line in lines:
            if line == "":
                if not last_was_empty and result:
                    empty_line_count = 1
                    last_was_empty = True
                else:
                    empty_line_count += 1
            else:
                if empty_line_count > 0 and result:
                    result.append(self.config.get('segment_delimiter', '||'))
                    empty_line_count = 0
                result.append(line)
                last_was_empty = False
        final_text = ''.join(result)
        return final_text

    def calculate_human_segment_delay(self, segment_index, total_segments, segment_text, previous_segment_text=""):
        base_delay = random.uniform(0.8, 1.8)
        if segment_index == 0:
            base_delay *= random.uniform(0.8, 1.2)
        elif segment_index == total_segments - 1:
            base_delay *= random.uniform(1.0, 1.5)
        else:
            base_delay *= random.uniform(0.9, 1.3)
        if len(segment_text) < 20:
            base_delay *= 0.8
        elif len(segment_text) > 100:
            base_delay *= 1.3
        connectors = ['而且', '并且', '但是', '然而', '所以', '因此', '另外', '还有', '也']
        if previous_segment_text and any(conn in previous_segment_text[-10:] or conn in segment_text[:10] for conn in connectors):
            base_delay *= 0.9
        return base_delay

    def send_message_human_like(self, segments):
        previous_segment = ""
        for i, segment in enumerate(segments, 1):
            try:
                self.log_info(f"准备发送段落 [{i}/{len(segments)}]: {len(segment)} 字符", category="SEND")
                pyautogui.click()
                time.sleep(0.2)
                self.simulate_human_typing(segment)
                pyautogui.press('enter')
                self.log_info(f"段落 [{i}/{len(segments)}] 发送完成", category="SEND")
                if i == 1 and len(segments) == 1:
                    self.consecutive_fast_responses += 1
                else:
                    self.consecutive_fast_responses = max(0, self.consecutive_fast_responses - 1)
                if i < len(segments):
                    delay = self.calculate_human_segment_delay(i-1, len(segments), segment, previous_segment)
                    self.log_info(f"等待段落间隔: {delay:.1f} 秒", category="SEND")
                    time.sleep(delay)
                previous_segment = segment
            except Exception as e:
                self.log_error(f"发送失败 [段落 {i}]: {e}", category="SEND")

    def print_status(self):
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        active_msg_rate = self.active_message_count / (elapsed / 3600) if elapsed > 0 else 0
        avg_speed = self.total_typed_chars / self.total_typing_time if self.total_typing_time > 0 else 0
        status = (
            f"\n{'='*60}\n"
            f"运行状态\n"
            f"{'='*60}\n"
            f"运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}\n"
            f"系统状态: {'暂停中' if self.paused else '运行中'}\n"
            f"睡眠状态: {'睡眠中' if self.is_sleeping() else '清醒'}\n"
            f"对话节奏: {self.config.get('human_pace', '平衡')}\n"
            f"连续快速回复: {self.consecutive_fast_responses}\n"
            f"平均响应时间: {self.avg_response_time:.2f}秒\n"
            f"\n主动消息统计:\n"
            f"今日主动: {self.daily_active_count}/{self.config.get('max_daily_active_messages', 10)}\n"
            f"总主动次数: {self.active_message_count}\n"
            f"主动频率: {active_msg_rate:.2f}次/小时\n"
            f"上次主动: {self.format_time_ago(self.last_active_message_time)}\n"
            f"上次用户: {self.format_time_ago(self.last_user_message_time)}\n"
            f"\n会话统计:\n"
            f"消息处理: {self.message_count}\n"
            f"错误计数: {self.error_count}\n"
            f"Null回复: {self.null_response_count}\n"
            f"历史记录: {len(self.conversation_history)//2}\n"
            f"\n打字统计:\n"
            f"总输入字符: {self.total_typed_chars}\n"
            f"总输入时间: {self.total_typing_time:.1f}秒\n"
            f"平均速度: {avg_speed:.1f}字符/秒\n"
            f"\n配置信息:\n"
            f"配置文件: {self.config_path}\n"
            f"日志文件: {self.log_file}\n"
            f"{'='*60}\n"
        )
        print(status)

    def format_time_ago(self, timestamp):
        if timestamp == 0:
            return "从未"
        diff = time.time() - timestamp
        if diff < 60:
            return f"{int(diff)}秒前"
        elif diff < 3600:
            return f"{int(diff/60)}分钟前"
        else:
            return f"{int(diff/3600)}小时前"

    def print_help(self):
        help_text = (
            f"\n{'='*60}\n"
            f"命令帮助\n"
            f"{'='*60}\n"
            f"[Pause/F8]      切换暂停/继续\n"
            f"[Ctrl+P]        强制暂停\n"
            f"[Ctrl+R]        强制继续\n"
            f"[S]             显示运行状态\n"
            f"[L]             显示日志路径\n"
            f"[A]             强制发送主动消息\n"
            f"[F5]            切换指令识别开关\n"
            f"[Q]             退出程序\n"
            f"[H]             显示本帮助\n"
            f"{'='*60}\n"
            f"\n当前设置:\n"
            f"对话节奏: {self.config.get('human_pace', '平衡')}\n"
            f"思考时间: {self.config.get('min_think_time', 1.0)}-{self.config.get('max_think_time', 3.0)}秒\n"
            f"打字速度: {self.config.get('typing_speed_min', 3)}-{self.config.get('typing_speed_max', 8)}字符/秒\n"
            f"主动频率: {self.config.get('active_message_frequency', 1)}次/小时\n"
            f"今日已主动: {self.daily_active_count}/{self.config.get('max_daily_active_messages', 10)}\n"
            f"睡眠模式: {'启用' if self.sleep_enabled else '禁用'}\n"
            f"指令识别: {'启用' if not self.cmd_disabled else '禁用'}\n"
            f"{'='*60}\n"
        )
        print(help_text)

    def save_archive(self):
        try:
            prompt_name = "default"
            if self.config.get('prompt_file'):
                prompt_name = os.path.splitext(os.path.basename(self.config['prompt_file']))[0]
            elif self.config.get('system_prompt'):
                prompt_name = self.config['system_prompt'][:10].replace(' ', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_filename = f"{prompt_name}_{timestamp}.json"
            archive_path = self.log_dir / archive_filename
            archive_data = {
                "version": "1.0",
                "saved_at": datetime.now().isoformat(),
                "config_snapshot": {
                    "api_url": self.config.get('api_url'),
                    "model_name": self.config.get('model_name'),
                    "prompt_file": self.config.get('prompt_file'),
                    "system_prompt": self.config.get('system_prompt'),
                    "segment_delimiter": self.config.get('segment_delimiter')
                },
                "state": {
                    "conversation_history": self.conversation_history,
                    "message_count": self.message_count,
                    "active_message_count": self.active_message_count,
                    "daily_active_count": self.daily_active_count,
                    "last_active_message_time": self.last_active_message_time,
                    "last_user_message_time": self.last_user_message_time,
                    "last_message_hash": self.last_message_hash,
                    "total_typed_chars": self.total_typed_chars,
                    "total_typing_time": self.total_typing_time,
                    "avg_response_time": self.avg_response_time,
                    "response_times": self.response_times,
                    "null_response_count": self.null_response_count,
                    "error_count": self.error_count,
                    "last_reset_date": self.last_reset_date.isoformat() if hasattr(self, 'last_reset_date') else None
                }
            }
            with open(archive_path, 'w', encoding='utf-8') as f:
                json.dump(archive_data, f, ensure_ascii=False, indent=2)
            self.log_info(f"对话存档已保存: {archive_path}", category="ARCHIVE")
            return str(archive_path)
        except Exception as e:
            self.log_error(f"保存存档失败: {e}", category="ARCHIVE")
            return None

    def load_archive(self, archive_path):
        try:
            with open(archive_path, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)
            if 'state' in archive_data:
                state = archive_data['state']
            else:
                state = archive_data
            self.conversation_history = state.get('conversation_history', [])
            if not isinstance(self.conversation_history, list):
                self.conversation_history = []
            self.message_count = state.get('message_count', 0)
            self.active_message_count = state.get('active_message_count', 0)
            self.daily_active_count = state.get('daily_active_count', 0)
            self.last_active_message_time = state.get('last_active_message_time', 0)
            self.last_user_message_time = state.get('last_user_message_time', time.time())
            self.last_message_hash = state.get('last_message_hash', "")
            self.total_typed_chars = state.get('total_typed_chars', 0)
            self.total_typing_time = state.get('total_typing_time', 0)
            self.avg_response_time = state.get('avg_response_time', 0)
            self.response_times = state.get('response_times', [])
            self.null_response_count = state.get('null_response_count', 0)
            self.error_count = state.get('error_count', 0)
            last_reset_str = state.get('last_reset_date')
            if last_reset_str:
                try:
                    self.last_reset_date = datetime.fromisoformat(last_reset_str).date()
                except:
                    self.last_reset_date = datetime.now().date()
            else:
                self.last_reset_date = datetime.now().date()
            self.log_info(f"已从存档恢复: {archive_path}", category="ARCHIVE")
            self.log_info(f"恢复对话历史: {len(self.conversation_history)} 条消息", category="ARCHIVE")
            if self.conversation_history and self.config.get('debug_mode', False):
                last_few = self.conversation_history[-4:]
                self.log_info("最近对话:", category="ARCHIVE")
                for msg in last_few:
                    role = "用户" if msg.get('role') == 'user' else "AI"
                    content = msg.get('content', '')[:50]
                    self.log_info(f"  {role}: {content}...", category="ARCHIVE")
        except Exception as e:
            self.log_error(f"加载存档失败: {e}，将启动新会话", category="ARCHIVE")
            self.conversation_history = []
            self.message_count = 0
            self.active_message_count = 0
            self.daily_active_count = 0
            self.last_active_message_time = 0
            self.last_user_message_time = time.time()
            self.last_message_hash = ""
            self.total_typed_chars = 0
            self.total_typing_time = 0
            self.avg_response_time = 0
            self.response_times = []
            self.null_response_count = 0
            self.error_count = 0
            self.last_reset_date = datetime.now().date()

    def run(self):
        self.log_info("启动主循环", category="MAIN")
        self.log_info(f"OCR语言: {self.config['ocr_langs']}", category="CONFIG")
        self.log_info(f"检查间隔: {self.config['check_interval']}秒", category="CONFIG")
        self.log_info(f"人性化节奏: {self.config.get('human_pace', '平衡')}", category="HUMAN")
        self.log_info(f"主动消息频率: {self.config.get('active_message_frequency', 1)}次/小时", category="ACTIVE")
        self.log_info("预热OCR引擎...", category="OCR")
        test_img = Image.new('RGB', (100, 30), color='white')
        self.extract_text_from_image(test_img)
        print("\n" + "="*60)
        print(" 聊天系统已就绪")
        print("="*60)
        self.print_help()
        print("="*60 + "\n")
        try:
            while self.running:
                self.wait_if_paused()
                if keyboard.is_pressed('h'):
                    self.print_help()
                    time.sleep(0.5)
                screenshot = self.capture_screen_region()
                detected_text = self.extract_text_from_image(screenshot)
                if detected_text and self.is_new_message(detected_text):
                    self.message_count += 1
                    self.last_user_message_time = time.time()
                    self.log_info(f"检测到新消息 [{self.message_count}]", category="DETECT")
                    self.log_info(f"消息内容: {detected_text[:200]}" + ("..." if len(detected_text) > 200 else ""), category="MESSAGE")
                    # 先处理指令（如果指令处理返回 True，则不再继续AI回复）
                    if self.check_command(detected_text):
                        continue
                    # 睡眠模式处理
                    if self.handle_sleep_reply(detected_text):
                        continue
                    if self.should_process_message(detected_text):
                        self.log_info(f"消息通过关键字过滤，正在请求AI回复...", category="FILTER")
                        response = self.get_ai_response(detected_text)
                        if response:
                            self.log_info(f"AI回复: {response[:200]}" + ("..." if len(response) > 200 else ""), category="RESPONSE")
                            think_time = self.calculate_human_think_time(len(detected_text), len(response))
                            self.log_info(f"人性化思考: {think_time:.1f} 秒", category="HUMAN")
                            time.sleep(think_time)
                            segments = self.segment_message(response)
                            if len(segments) > 1:
                                self.log_info(f"检测到分段符，将发送 {len(segments)} 条消息", category="SEGMENT")
                            self.send_message_human_like(segments)
                            self.last_response_time = time.time()
                        else:
                            self.log_info("AI返回空回复，已忽略", category="API")
                    else:
                        self.log_info(f"消息未包含任何关键字，已忽略处理", category="FILTER")
                        if self.config.get('log_ignored_messages', False):
                            self.log_debug(f"被忽略的消息: {detected_text}", category="FILTER")
                time.sleep(self.config['check_interval'])
        except KeyboardInterrupt:
            self.log_info("用户中断程序", category="MAIN")
        except Exception as e:
            self.log_error(f"运行异常: {e}", category="FATAL")
            import traceback
            self.log_error(traceback.format_exc(), category="FATAL")
        finally:
            self.cleanup()

    def cleanup(self):
        self.running = False
        self.pause_event.set()
        self.log_info("正在清理资源...", category="MAIN")
        self.save_archive()
        elapsed = time.time() - self.start_time
        avg_speed = self.total_typed_chars / self.total_typing_time if self.total_typing_time > 0 else 0
        self.log_info(f"总运行时间: {elapsed:.1f}秒", category="STATS")
        self.log_info(f"总消息处理: {self.message_count}", category="STATS")
        self.log_info(f"总错误数: {self.error_count}", category="STATS")
        self.log_info(f"Null回复数: {self.null_response_count}", category="STATS")
        self.log_info(f"主动消息数: {self.active_message_count}", category="STATS")
        self.log_info(f"总输入字符: {self.total_typed_chars}", category="STATS")
        self.log_info(f"总输入时间: {self.total_typing_time:.1f}秒", category="STATS")
        self.log_info(f"平均速度: {avg_speed:.1f}字符/秒", category="STATS")
        self.log_info(f"平均响应时间: {self.avg_response_time:.2f}秒", category="STATS")
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"会话结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"处理消息: {self.message_count}\n")
            f.write(f"主动消息: {self.active_message_count}\n")
            f.write(f"Null回复: {self.null_response_count}\n")
            f.write(f"错误计数: {self.error_count}\n")
            f.write(f"输入字符: {self.total_typed_chars}\n")
            f.write(f"输入时间: {self.total_typing_time:.1f}秒\n")
            f.write(f"平均速度: {avg_speed:.1f}字符/秒\n")
            f.write(f"平均响应时间: {self.avg_response_time:.2f}秒\n")
            f.write(f"{'='*60}\n")
        self.log_info("程序正常退出", category="MAIN")

def main():
    print("="*60)
    print(" PaperAiChat 聊天机器人 v8.0")
    print(" 人性化模拟 | 主动消息 | 存档恢复 | 睡眠模式 | 指令系统")
    print("="*60)
    archive_path = None
    if len(sys.argv) > 1:
        archive_path = sys.argv[1]
        print(f"[信息] 将加载存档: {archive_path}")
    try:
        import easyocr, pyautogui, pyperclip, keyboard, openai, PIL, numpy
    except ImportError as e:
        print(f"[FATAL] 依赖库缺失: {e}")
        print("\n请安装依赖:")
        print("pip install easyocr pyautogui pyperclip keyboard openai pillow numpy")
        sys.exit(1)
    if sys.version_info >= (3, 12):
        print(f"[WARNING] Python {sys.version_info.major}.{sys.version_info.minor} 可能不兼容")
        print("建议使用 Python 3.8-3.11\n")
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    bot = EasyOCRChatBot(config_path, archive_path=archive_path)
    try:
        bot.run()
    except Exception as e:
        bot.log_error(f"未捕获的异常: {e}", category="FATAL")
        import traceback
        bot.log_error(traceback.format_exc(), category="FATAL")
    finally:
        input("\n按 Enter 键退出...")

if __name__ == "__main__":
    main()