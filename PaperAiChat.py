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

class EasyOCRChatBot:
    """EasyOCR版聊天机器人 - 含存档恢复功能"""
    
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
        
        # 加载配置
        self.config = self.load_config()
        
        # 初始化OCR
        self.reader = self.init_ocr()
        
        # 初始化API客户端
        self.client = OpenAI(
            api_key=self.config['api_key'],
            base_url=self.config['api_url']
        )
        
        # 状态变量（如果提供了存档则从存档加载，否则初始化为空）
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
        
        # 会话开始时间（重置为当前时间，不保存存档中的）
        self.start_time = time.time()
        self.conversation_start_time = self.start_time

        # 尝试导入 pyperclipimg
        try:
            import pyperclipimg
            self.has_pyperclipimg = True
        except ImportError:
            self.has_pyperclipimg = False
            self.log_warning("未安装 pyperclipimg，表情图片功能将不可用。请安装：pip install pyperclipimg", category="IMPORT")       
        
        self.config.setdefault('enable_emoticon', True)
        self.config.setdefault('emoticon_folder', 'Emoticon')

        # 启动命令监听线程
        self.command_thread = threading.Thread(target=self.command_listener, daemon=True)
        self.command_thread.start()
        
        # 启动主动消息检查线程
        self.active_message_thread = threading.Thread(target=self.active_message_checker, daemon=True)
        self.active_message_thread.start()
        
        self.log_info("系统初始化完成", category="INIT")
        self.log_info(f"配置文件路径: {self.config_path}", category="CONFIG")
        self.log_info(f"对话节奏: {self.conversation_pace}", category="HUMAN")
        self.log_info(f"主动消息间隔: {self.config.get('active_message_min_interval', 300)}-{self.config.get('active_message_max_interval', 1800)}秒", category="ACTIVE")
        if self.archive_path:
            self.log_info(f"已从存档恢复: {self.archive_path}", category="ARCHIVE")
    
    def init_logging(self):
        """初始化日志系统"""
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
        """结构化日志记录"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] [{level}] [{category}] {message}"
        
        # 控制台输出
        print(log_entry)
        
        # 文件输出
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
    
    def command_listener(self):
        """独立命令监听线程"""
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
                
                time.sleep(0.1)
                
            except Exception as e:
                self.log_error(f"命令监听异常: {e}", category="COMMAND")
                time.sleep(0.5)
    
    def toggle_pause(self):
        """切换暂停状态"""
        self.paused = not self.paused
        if self.paused:
            self.pause_event.clear()
            self.log_info("系统已暂停 - 按 Pause/F8 键继续", category="PAUSE")
        else:
            self.pause_event.set()
            self.log_info("系统已继续运行", category="PAUSE")
    
    def wait_if_paused(self):
        """如果处于暂停状态，则等待"""
        if self.paused:
            self.log_debug("系统暂停中，等待继续...", category="PAUSE")
        self.pause_event.wait()
    
    def active_message_checker(self):
        """主动消息检查线程"""
        while self.running:
            try:
                self.wait_if_paused()
                
                # 检查是否需要重置每日计数
                today = datetime.now().date()
                if today != self.last_reset_date:
                    self.daily_active_count = 0
                    self.last_reset_date = today
                    self.log_info("每日主动消息计数已重置", category="ACTIVE")
                
                # 检查是否应该发送主动消息
                if self.should_send_active_message():
                    self.send_active_message()
                
                # 每30秒检查一次
                time.sleep(30)
                
            except Exception as e:
                self.log_error(f"主动消息检查异常: {e}", category="ACTIVE")
                time.sleep(60)
    
    def should_send_active_message(self):
        """判断是否应该发送主动消息"""
        # 如果会话历史为空，不发送
        if len(self.conversation_history) == 0:
            return False
        
        # 检查每日上限
        max_daily = self.config.get('max_daily_active_messages', 10)
        if self.daily_active_count >= max_daily:
            return False
        
        # 检查最小间隔
        min_interval = self.config.get('active_message_min_interval', 300)  # 5分钟
        time_since_last = time.time() - self.last_active_message_time
        if time_since_last < min_interval:
            return False
        
        # 检查用户是否活跃
        time_since_user = time.time() - self.last_user_message_time
        min_user_inactive = self.config.get('min_user_inactive_time', 60)  # 1分钟
        
        if time_since_user < min_user_inactive:
            return False
        
        # 根据会话时长调整概率
        session_duration = time.time() - self.conversation_start_time
        hours = session_duration / 3600
        
        # 基础概率（每小时0.5-2次）
        base_probability = self.config.get('active_message_frequency', 1.0) / 3600 * 300  # 每5分钟的概率
        
        # 根据会话时长调整
        if hours < 0.5:  # 半小时内，较活跃
            probability = base_probability * 0.5
        elif hours < 2:  # 2小时内，正常
            probability = base_probability
        elif hours < 4:  # 4小时内，稍低
            probability = base_probability * 0.7
        else:  # 4小时以上，可能快结束了
            probability = base_probability * 0.3
        
        # 随机判断
        return random.random() < probability
    
    def generate_active_message_context(self):
        """生成主动消息的上下文"""
        if len(self.conversation_history) < 2:
            return "对话刚刚开始，还没有历史消息。"
        
        # 获取最近几条消息（最多6条）
        recent = self.conversation_history[-6:]
        
        # 构建格式化的对话历史
        context_lines = []
        for msg in recent:
            role = "用户" if msg['role'] == 'user' else "我"
            # 截取适当长度
            content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            context_lines.append(f"{role}: {content}")
        
        return "\n".join(context_lines)
    
    def get_active_message(self):
        """获取AI生成的主动消息内容"""
        try:
            # 获取系统提示词
            system_prompt = self.get_system_prompt()
            
            # 构建主动消息的上下文
            context = self.generate_active_message_context()
            
            # 构建消息历史
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
            
            # 清理和验证
            message = message.strip('"\' \n')
            if len(message) < 5:
                self.log_warning(f"主动消息太短: {len(message)}字符", category="ACTIVE")
                return None
            
            self.log_debug(f"主动消息生成成功: {len(message)}字符", category="ACTIVE")
            return message
            
        except Exception as e:
            self.log_error(f"生成主动消息失败: {e}", category="ACTIVE")
            return None
    
    def force_active_message(self):
        """强制发送主动消息（用户触发）"""
        if self.paused:
            self.log_info("系统暂停中，无法发送主动消息", category="COMMAND")
            return
        
        self.log_info("用户强制发送主动消息", category="COMMAND")
        self.send_active_message()
    
    def init_ocr(self, max_retries=3):
        """初始化OCR引擎"""
        for attempt in range(max_retries):
            try:
                self.log_info(f"初始化OCR引擎 (尝试 {attempt + 1}/{max_retries})...", category="OCR")
                
                model_dir = Path.home() / ".EasyOCR" / "model"
                model_dir.mkdir(parents=True, exist_ok=True)
                self.log_info(f"模型存储路径: {model_dir}", category="OCR")
                
                existing_models = list(model_dir.glob("*.zip"))
                if existing_models:
                    self.log_info(f"发现已下载模型: {[f.name for f in existing_models]}", category="OCR")
                
                reader = easyocr.Reader(
                    self.config['ocr_langs'],
                    gpu=self.config.get('use_gpu', False),
                    model_storage_directory=str(model_dir),
                    download_enabled=True,
                    verbose=False
                )
                
                self.log_info("OCR引擎初始化成功", category="OCR")
                return reader
                
            except Exception as e:
                self.log_error(f"OCR初始化失败: {str(e)}", category="OCR")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    self.log_info(f"等待 {wait_time} 秒后重试...", category="OCR")
                    time.sleep(wait_time)
                else:
                    self.log_error("OCR引擎初始化失败，程序退出", category="FATAL")
                    sys.exit(1)

    def send_active_message(self):
        """发送主动消息"""
        try:
            self.log_info("准备发送主动消息", category="ACTIVE")
            
            # 获取主动消息内容
            message = self.get_active_message()
            if not message:
                self.log_info("主动消息生成失败或内容无效", category="ACTIVE")
                return
            
            self.log_info(f"生成的主动消息: {message[:100]}...", category="ACTIVE")
            
            # 检查是否包含分隔符
            delimiter = self.config.get('segment_delimiter', '||')
            if delimiter in message:
                segments = [seg.strip() for seg in message.split(delimiter) if seg.strip()]
                self.log_info(f"主动消息包含分隔符，已分割为 {len(segments)} 段", category="ACTIVE")
            else:
                segments = [message]
            
            # 人性化思考（假装在想说什么）
            think_time = random.uniform(2, 5)
            self.log_info(f"主动消息思考时间: {think_time:.1f}秒", category="ACTIVE")
            time.sleep(think_time)
            
            # 发送分段消息
            previous_segment = ""
            for i, segment in enumerate(segments, 1):
                # 聚焦输入框
                pyautogui.click()
                time.sleep(0.2)
                
                # 模拟打字
                self.log_info(f"正在输入段落 [{i}/{len(segments)}]: {len(segment)}字符", category="ACTIVE")
                self.simulate_human_typing(segment)
                
                # 发送
                pyautogui.press('enter')
                
                self.log_info(f"段落 [{i}/{len(segments)}] 发送完成", category="ACTIVE")
                
                # 段落间隔
                if i < len(segments):
                    delay = self.calculate_human_segment_delay(i-1, len(segments), segment, previous_segment)
                    self.log_info(f"等待段落间隔: {delay:.1f}秒", category="ACTIVE")
                    time.sleep(delay)
                
                previous_segment = segment
            
            # 更新统计
            self.last_active_message_time = time.time()
            self.active_message_count += 1
            self.daily_active_count += 1
            self.message_count += 1
            
            # 保存到历史（保存完整消息）
            self.conversation_history.append({"role": "assistant", "content": message})
            
            self.log_info(f"主动消息发送成功 [#{self.active_message_count}, 今日: {self.daily_active_count}]", category="ACTIVE")
            
        except Exception as e:
            self.log_error(f"发送主动消息失败: {e}", category="ACTIVE")
    
    def load_config(self):
        """加载配置文件"""
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
        """配置向导"""
        print("\n" + "="*60)
        print(" PaperAiChat 聊天机器人配置向导 ")
        print("="*60)
        
        config = {}
        
        # API配置
        print("\n[1/8] API 配置")
        config['api_key'] = input("   API密钥: ").strip()
        config['api_url'] = input("   API网址: ").strip()
        config['model_name'] = input("   模型名称: ").strip()
        
        # OCR配置
        print("\n[2/8] OCR 配置")
        print("   支持的语言: ch_sim(简体中文), en(英文), ch_tra(繁体中文), ja(日文), ko(韩文)")
        langs = input("   识别语言 (用逗号分隔, 默认: ch_sim,en): ").strip()
        config['ocr_langs'] = langs.split(',') if langs else ['ch_sim', 'en']
        config['use_gpu'] = input("   使用GPU加速? (y/n, 默认: n): ").strip().lower() == 'y'
        
        # 识别区域配置
        print("\n[3/8] 消息区域配置")
        config['message_region'] = self.select_region_interactive()
        
        # 提示词配置
        print("\n[4/8] 提示词配置")
        prompt_file = input("   提示词文件路径 (直接回车跳过): ").strip()
        if prompt_file:
            config['prompt_file'] = prompt_file
        else:
            config['system_prompt'] = input("   系统提示词: ").strip()
        
        # 运行参数
        print("\n[5/8] 运行参数")
        config['check_interval'] = float(input("   检查间隔(秒, 默认: 1.0): ") or 1.0)
        config['debug_mode'] = input("   调试模式? (y/n, 默认: n): ").strip().lower() == 'y'
        config['save_screenshots'] = input("   保存截图? (y/n, 默认: n): ").strip().lower() == 'y'
        
        # 对话行为
        print("\n[6/8] 对话行为")
        config['max_history'] = int(input("   最大历史记录数 (默认: 10): ") or 10)
        config['min_message_length'] = int(input("   最小消息长度 (默认: 2): ") or 2)
        config['segment_delimiter'] = input("   分段符 (默认: ||): ") or "||"
        config['ignore_null_response'] = input("   忽略null回复? (y/n, 默认: y): ").strip().lower() != 'n'
        
        # 人性化模拟配置
        print("\n[7/8] 人性化模拟配置")
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
        
        # 主动消息配置
        print("\n[8/8] 主动消息配置")
        print("   主动消息频率 (每小时主动次数):")
        print("   0 = 从不主动")
        print("   0.5 = 每2小时1次")
        print("   1 = 每小时1次")
        print("   2 = 每小时2次")
        print("   3 = 每小时3次")
        
        freq = float(input("   请选择频率 (默认: 1): ") or 1)
        config['active_message_frequency'] = max(0, min(freq, 5))
        
        # 计算具体间隔
        if config['active_message_frequency'] > 0:
            avg_interval = 3600 / config['active_message_frequency']
            config['active_message_min_interval'] = int(avg_interval * 0.7)  # 最小间隔
            config['active_message_max_interval'] = int(avg_interval * 1.3)  # 最大间隔
        else:
            config['active_message_min_interval'] = 999999
            config['active_message_max_interval'] = 999999
        
        config['max_daily_active_messages'] = int(input("   每日最大主动消息数 (默认: 10): ") or 10)
        config['min_user_inactive_time'] = int(input("   用户多久不活跃才主动(秒, 默认: 60): ") or 60)
        config['active_message_cooldown'] = int(input("   主动后冷却时间(秒, 默认: 300): ") or 300)
        
        # 保存配置
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        self.log_info(f"配置已保存: {self.config_path}", category="CONFIG")
        return config
    
    def select_region_interactive(self):
        """交互式区域选择"""
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
        """获取系统提示词"""
        if self.config.get('prompt_file'):
            try:
                with open(self.config['prompt_file'], 'r', encoding='utf-8') as f:
                    prompt = f.read().strip()
                self.log_debug(f"从文件加载提示词: {len(prompt)} 字符", category="PROMPT")
                return prompt
            except Exception as e:
                self.log_error(f"读取提示词文件失败: {e}", category="PROMPT")
                return self.config.get('system_prompt', '你是一个友好的AI助手。模拟真实对话，不使用markdown格式。模拟真实线上聊天，用"||"将回复隔开。每段一般不超过10字。网络聊天，尽量少用标点。不要出现换行符。如果用户的内容是完全无法理解的奇异内容（考虑识图错误）或你完全无法回复，输出"null"')
        else:
            return self.config.get('system_prompt', '你是一个友好的AI助手。')
    
    def capture_screen_region(self):
        """截图指定区域"""
        region = self.config['message_region']
        
        try:
            screenshot = pyautogui.screenshot(
                region=(
                    region['x1'],
                    region['y1'],
                    region['width'],
                    region['height']
                )
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
        """OCR识别"""
        if image is None:
            return ""
        
        try:
            img_array = np.array(image)
            
            start_time = time.time()
            result = self.reader.readtext(
                img_array,
                paragraph=True,
                detail=0,
                batch_size=self.config.get('ocr_batch_size', 1)
            )
            elapsed = (time.time() - start_time) * 1000
            
            text = ' '.join(result).strip()
            
            if text:
                self.log_debug(f"OCR识别完成: {elapsed:.0f}ms, 长度: {len(text)}", category="OCR")
            else:
                self.log_debug(f"OCR未识别到文字: {elapsed:.0f}ms", category="OCR")
            
            return text
            
        except Exception as e:
            self.log_error(f"OCR识别失败: {e}", category="OCR")
            return ""
    
    def calculate_hash(self, text):
        """计算文本哈希"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def is_new_message(self, text):
        """判断是否为新消息"""
        if not text or len(text) < self.config.get('min_message_length', 2):
            return False
        
        text_hash = self.calculate_hash(text)
        
        if text_hash != self.last_message_hash:
            self.last_message_hash = text_hash
            return True
        return False
    
    def is_null_response(self, text):
        """判断是否为null回复"""
        if not text:
            return True
        
        cleaned = text.strip().lower()
        null_patterns = ['null', 'none', 'nil', 'undefined', '空', '无', '没有']
        return cleaned in null_patterns or cleaned == ''
    
    def segment_message(self, text):
        """根据分隔符分割消息"""
        delimiter = self.config.get('segment_delimiter', '||')
        
        if delimiter in text:
            segments = [seg.strip() for seg in text.split(delimiter) if seg.strip()]
            self.log_info(f"消息已分割为 {len(segments)} 段", category="SEGMENT")
            return segments
        else:
            return [text]
    
    def calculate_human_think_time(self, message_length, response_length):
        """计算人性化思考时间"""
        # 基础思考时间
        base_think = random.uniform(
            self.config.get('min_think_time', 1.0),
            self.config.get('max_think_time', 3.0)
        )
        
        # 根据消息长度增加思考时间
        if message_length > 100:
            base_think += random.uniform(1.0, 2.0)
        elif message_length > 50:
            base_think += random.uniform(0.5, 1.0)
        
        # 根据回复长度增加思考时间
        if response_length > 200:
            base_think += random.uniform(1.5, 3.0)
        elif response_length > 100:
            base_think += random.uniform(0.8, 1.5)
        
        # 对话节奏影响
        pace_factor = self.config.get('base_delay_factor', 1.0)
        
        # 连续快速回复惩罚
        if self.consecutive_fast_responses > 2:
            base_think *= (1 + self.consecutive_fast_responses * 0.2)
        
        # 自适应速度
        if self.config.get('adaptive_speed', True) and response_length > 300:
            base_think *= 0.8
        
        # 最终思考时间
        think_time = base_think * pace_factor
        
        # 确保不超过最大响应时间
        max_time = self.config.get('max_response_time', 5)
        think_time = min(think_time, max_time)
        
        return think_time
    
    def calculate_typing_speed(self, text_length):
        """计算打字速度（字符/秒）"""
        min_speed = self.config.get('typing_speed_min', 3)
        max_speed = self.config.get('typing_speed_max', 8)
        
        # 根据文本长度调整速度
        if text_length < 20:
            speed = random.uniform(min_speed, max_speed)
        elif text_length < 50:
            speed = random.uniform(min_speed + 1, max_speed)
        else:
            speed = random.uniform(min_speed, max_speed - 1)
        
        # 添加随机波动
        speed *= random.uniform(0.9, 1.1)
        
        return speed
    
    def simulate_human_typing(self, text):
        """模拟真人打字，支持表情图片[文件名]"""
        if not text:
            return
        
        # 计算预计打字时间（仅文本部分，图片部分单独处理）
        text_only = self.strip_emoticon_tags(text)  # 用于估算时间
        typing_speed = self.calculate_typing_speed(len(text_only))
        expected_time = len(text_only) / typing_speed
        
        self.total_typed_chars += len(text_only)
        self.total_typing_time += expected_time
        
        self.log_info(f"开始打字: 文本长度 {len(text_only)} 字符, 速度: {typing_speed:.1f}字符/秒, 预计文本时间: {expected_time:.1f}秒", category="TYPING")
        
        i = 0
        n = len(text)
        
        while i < n:
            char = text[i]
            
            # 检测到表情开始标记 [
            if char == '[' and self.config.get('enable_emoticon', True) and self.has_pyperclipimg:
                # 查找匹配的 ]
                j = text.find(']', i + 1)
                if j != -1:
                    # 提取图片名
                    img_name = text[i+1:j].strip()
                    if img_name:
                        self.process_emoticon(img_name)
                    # 跳过已处理的表情标记
                    i = j + 1
                    continue
                else:
                    # 没有找到匹配的 ]，当作普通字符处理
                    pass
            
            # 普通字符处理：逐个复制粘贴
            pyperclip.copy(char)
            time.sleep(0.01)
            pyautogui.hotkey('ctrl', 'v')
            
            # 计算字符间隔
            base_interval = 1.0 / typing_speed
            interval = base_interval * random.uniform(0.8, 1.2)
            
            # 标点符号额外停顿
            if char in ['.', '。', '!', '！', '?', '？', ',', '，', ';', '；', '\n']:
                interval += random.uniform(0.1, 0.3)
            
            # 进度显示
            if (i + 1) % 10 == 0 or i == n - 1:
                progress = (i + 1) / n * 100
                self.log_debug(f"打字进度: {progress:.0f}% ({i+1}/{n}总字符)", category="TYPING")
            
            time.sleep(interval)
            i += 1
        
        # 输入完成后的停顿
        final_pause = random.uniform(0.2, 0.5)
        time.sleep(final_pause)
        
        self.log_debug(f"段落输入完成: 共处理 {n} 字符（含表情标记）", category="TYPING")

    def strip_emoticon_tags(self, text):
        """去除表情标记，返回纯文本（用于时间估算）"""
        import re
        return re.sub(r'\[[^\]]*\]', '', text)

    def process_emoticon(self, img_name):
        """处理表情图片：从Emoticon文件夹复制并发送"""
        try:
            # 构建图片路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            emoticon_folder = self.config.get('emoticon_folder', 'Emoticon')
            img_path = os.path.join(script_dir, emoticon_folder, img_name)
            
            # 如果文件名不含扩展名，尝试常见扩展名
            if not os.path.splitext(img_path)[1]:
                for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                    test_path = img_path + ext
                    if os.path.exists(test_path):
                        img_path = test_path
                        break
            
            if not os.path.exists(img_path):
                self.log_error(f"表情图片不存在: {img_path}", category="EMOTICON")
                return
            
            # 复制图片到剪贴板
            import pyperclipimg
            pyperclipimg.copy(img_path)
            self.log_info(f"已复制表情图片: {img_name}", category="EMOTICON")
            
            # 粘贴并发送
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.2)
            pyautogui.press('enter')
            self.log_info("表情图片已发送", category="EMOTICON")
            
            # 发送后稍作停顿，模拟真人操作
            time.sleep(random.uniform(0.5, 1.0))
            
        except Exception as e:
            self.log_error(f"处理表情图片失败: {e}", category="EMOTICON")
    
    def get_ai_response(self, message):
        """获取AI回复，并将空行转换为分隔符"""
        try:
            system_prompt = self.get_system_prompt()
            
            # 构建消息历史
            messages = [{"role": "system", "content": system_prompt}]
            
            # 添加上下文
            for hist in self.conversation_history[-self.config['max_history']:]:
                messages.append(hist)
            
            # 添加当前消息
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
            
            # 处理空行转换为分隔符
            original_reply = reply
            reply = self.convert_empty_lines_to_delimiter(reply)
            
            if original_reply != reply:
                self.log_info(f"空行转换: 将 {reply.count('||')} 个空行转换为分隔符", category="FORMAT")
            
            self.log_info(f"API响应: {elapsed:.0f}ms, 长度: {len(reply)}", category="API")
            
            # 检查是否为null回复
            if self.config.get('ignore_null_response', True) and self.is_null_response(reply):
                self.null_response_count += 1
                self.log_info(f"检测到null回复 (总计: {self.null_response_count})", category="API")
                return None
            
            # 保存到历史
            self.conversation_history.append({"role": "user", "content": message})
            self.conversation_history.append({"role": "assistant", "content": reply})
            
            # 限制历史长度
            max_history = self.config['max_history']
            if len(self.conversation_history) > max_history * 2:
                self.conversation_history = self.conversation_history[-max_history*2:]
            
            # 记录响应时间
            self.response_times.append(elapsed / 1000)
            if len(self.response_times) > 10:
                self.response_times.pop(0)
            self.avg_response_time = sum(self.response_times) / len(self.response_times)
            
            return reply
            
        except Exception as e:
            self.log_error(f"API请求失败: {e}", category="API")
            return None

    def convert_empty_lines_to_delimiter(self, text):
        """将连续空行转换为分隔符，同时删除换行符"""
        if not text:
            return text
        
        import re
        
        # 步骤1: 按行分割
        lines = text.split('\n')
        
        # 步骤2: 处理每一行，去除首尾空格
        lines = [line.strip() for line in lines]
        
        # 步骤3: 过滤掉完全空的行（但保留有内容的行）
        # 同时，将连续的空行标记为分隔符位置
        result = []
        empty_line_count = 0
        last_was_empty = False
        
        for line in lines:
            if line == "":  # 空行
                if not last_was_empty and result:  # 第一次遇到空行，且前面有内容
                    empty_line_count = 1
                    last_was_empty = True
                else:
                    empty_line_count += 1
            else:  # 有内容的行
                # 如果之前有空行，且空行数量达到阈值（至少1个空行），添加分隔符
                if empty_line_count > 0 and result:
                    # 多个空行也只添加一个分隔符
                    result.append(self.config.get('segment_delimiter', '||'))
                    empty_line_count = 0
                
                result.append(line)
                last_was_empty = False
        
        # 步骤4: 连接所有内容（删除换行符）
        final_text = ''.join(result)
        
        return final_text
    
    def calculate_human_segment_delay(self, segment_index, total_segments, segment_text, previous_segment_text=""):
        """计算人性化段落间隔"""
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
        """人性化发送消息"""
        previous_segment = ""
        
        for i, segment in enumerate(segments, 1):
            try:
                self.log_info(f"准备发送段落 [{i}/{len(segments)}]: {len(segment)} 字符", category="SEND")
                
                # 聚焦输入框（点击确保焦点）
                current_pos = pyautogui.position()
                pyautogui.click()
                time.sleep(0.2)
                
                # 模拟打字
                self.simulate_human_typing(segment)
                
                # 发送
                pyautogui.press('enter')
                
                self.log_info(f"段落 [{i}/{len(segments)}] 发送完成", category="SEND")
                
                # 更新连续快速回复计数
                if i == 1 and len(segments) == 1:
                    self.consecutive_fast_responses += 1
                else:
                    self.consecutive_fast_responses = max(0, self.consecutive_fast_responses - 1)
                
                # 段落间隔
                if i < len(segments):
                    delay = self.calculate_human_segment_delay(i-1, len(segments), segment, previous_segment)
                    self.log_info(f"等待段落间隔: {delay:.1f} 秒", category="SEND")
                    time.sleep(delay)
                
                previous_segment = segment
                
            except Exception as e:
                self.log_error(f"发送失败 [段落 {i}]: {e}", category="SEND")
    
    def print_status(self):
        """打印状态信息"""
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        # 计算主动消息统计
        active_msg_rate = self.active_message_count / (elapsed / 3600) if elapsed > 0 else 0
        
        avg_speed = self.total_typed_chars / self.total_typing_time if self.total_typing_time > 0 else 0
        
        status = (
            f"\n{'='*60}\n"
            f"运行状态\n"
            f"{'='*60}\n"
            f"运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}\n"
            f"系统状态: {'暂停中' if self.paused else '运行中'}\n"
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
        """格式化时间差"""
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
        """打印帮助信息"""
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
            f"[Q]             退出程序\n"
            f"[H]             显示本帮助\n"
            f"{'='*60}\n"
            f"\n当前设置:\n"
            f"对话节奏: {self.config.get('human_pace', '平衡')}\n"
            f"思考时间: {self.config.get('min_think_time', 1.0)}-{self.config.get('max_think_time', 3.0)}秒\n"
            f"打字速度: {self.config.get('typing_speed_min', 3)}-{self.config.get('typing_speed_max', 8)}字符/秒\n"
            f"主动频率: {self.config.get('active_message_frequency', 1)}次/小时\n"
            f"今日已主动: {self.daily_active_count}/{self.config.get('max_daily_active_messages', 10)}\n"
            f"{'='*60}\n"
        )
        print(help_text)
    
    def save_archive(self):
        """保存对话存档到logs目录，文件名格式：{提示词文件名}_{时间}.json"""
        try:
            # 获取提示词文件名（不含路径和扩展名）
            prompt_name = "default"
            if self.config.get('prompt_file'):
                prompt_name = os.path.splitext(os.path.basename(self.config['prompt_file']))[0]
            elif self.config.get('system_prompt'):
                # 取系统提示词前10个字符作为文件名的一部分（去除空格）
                prompt_name = self.config['system_prompt'][:10].replace(' ', '_')
            
            # 生成时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_filename = f"{prompt_name}_{timestamp}.json"
            archive_path = self.log_dir / archive_filename
            
            # 准备存档数据
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
        """从存档文件加载对话状态"""
        try:
            with open(archive_path, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)
            
            state = archive_data.get('state', {})
            self.conversation_history = state.get('conversation_history', [])
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
            
            # 恢复 last_reset_date，如果不存在则设为今天
            last_reset_str = state.get('last_reset_date')
            if last_reset_str:
                self.last_reset_date = datetime.fromisoformat(last_reset_str).date()
            else:
                self.last_reset_date = datetime.now().date()
            
            self.log_info(f"已从存档恢复: {archive_path}", category="ARCHIVE")
            self.log_info(f"恢复对话历史: {len(self.conversation_history)} 条消息", category="ARCHIVE")
            
        except Exception as e:
            self.log_error(f"加载存档失败: {e}", category="ARCHIVE")
            # 如果加载失败，初始化为空状态
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
        """主运行循环"""
        self.log_info("启动主循环", category="MAIN")
        
        # 打印配置摘要
        self.log_info(f"OCR语言: {self.config['ocr_langs']}", category="CONFIG")
        self.log_info(f"检查间隔: {self.config['check_interval']}秒", category="CONFIG")
        self.log_info(f"人性化节奏: {self.config.get('human_pace', '平衡')}", category="HUMAN")
        self.log_info(f"主动消息频率: {self.config.get('active_message_frequency', 1)}次/小时", category="ACTIVE")
        
        # 预热OCR
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
                # 检查暂停状态
                self.wait_if_paused()
                
                # 检查键盘命令
                if keyboard.is_pressed('h'):
                    self.print_help()
                    time.sleep(0.5)
                
                # 1. 截图
                screenshot = self.capture_screen_region()
                
                # 2. OCR识别
                detected_text = self.extract_text_from_image(screenshot)
                
                # 3. 判断是否为新消息
                if detected_text and self.is_new_message(detected_text):
                    self.message_count += 1
                    self.last_user_message_time = time.time()
                    
                    self.log_info(f"检测到新消息 [{self.message_count}]", category="DETECT")
                    self.log_info(f"消息内容: {detected_text[:200]}" + 
                                ("..." if len(detected_text) > 200 else ""), 
                                category="MESSAGE")
                    
                    # 4. 获取AI回复
                    self.log_info("正在请求AI回复...", category="API")
                    response = self.get_ai_response(detected_text)
                    
                    if response:
                        self.log_info(f"AI回复: {response[:200]}" + 
                                    ("..." if len(response) > 200 else ""), 
                                    category="RESPONSE")
                        
                        # 5. 人性化思考延迟
                        think_time = self.calculate_human_think_time(len(detected_text), len(response))
                        self.log_info(f"人性化思考: {think_time:.1f} 秒", category="HUMAN")
                        time.sleep(think_time)
                        
                        # 6. 分段处理
                        segments = self.segment_message(response)
                        
                        if len(segments) > 1:
                            self.log_info(f"检测到分段符，将发送 {len(segments)} 条消息", 
                                        category="SEGMENT")
                        
                        # 7. 人性化发送
                        self.send_message_human_like(segments)
                        
                        self.last_response_time = time.time()
                    else:
                        self.log_info("AI返回空回复，已忽略", category="API")
                
                # 等待下一次检查
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
        """清理资源，退出前保存存档"""
        self.running = False
        self.pause_event.set()
        
        self.log_info("正在清理资源...", category="MAIN")
        
        # 保存存档
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
    """主函数"""
    print("="*60)
    print(" PaperAiChat 聊天机器人 v7.0")
    print(" 人性化模拟 | 主动消息 | 存档恢复")
    print("="*60)
    
    # 解析命令行参数
    archive_path = None
    if len(sys.argv) > 1:
        archive_path = sys.argv[1]
        print(f"[信息] 将加载存档: {archive_path}")
    
    # 检查依赖
    try:
        import easyocr
        import pyautogui
        import pyperclip
        import keyboard
        from openai import OpenAI
        from PIL import Image
        import numpy as np
    except ImportError as e:
        print(f"[FATAL] 依赖库缺失: {e}")
        print("\n请安装依赖:")
        print("pip install easyocr pyautogui pyperclip keyboard openai pillow numpy")
        sys.exit(1)
    
    # 检查Python版本
    if sys.version_info >= (3, 12):
        print(f"[WARNING] Python {sys.version_info.major}.{sys.version_info.minor} 可能不兼容")
        print("建议使用 Python 3.8-3.11\n")
    
    # 配置文件路径
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    
    # 启动机器人，传入存档路径
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