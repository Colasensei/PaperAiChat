import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
from pathlib import Path

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

class ConfigUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PaperAiChat 完整配置界面")
        self.root.geometry("900x1000")
        self.root.resizable(True, True)
        
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self.config = self.load_config()
        self.create_widgets()
        
    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self.get_default_config()
        return self.get_default_config()
    
    def get_default_config(self):
        return {
            "api_key": "",
            "api_url": "https://api.deepseek.com",
            "model_name": "deepseek-chat",
            "ocr_langs": ["ch_sim", "en"],
            "use_gpu": False,
            "message_region": {"x1": 500, "y1": 300, "x2": 1200, "y2": 400, "width": 700, "height": 100},
            "prompt_file": "",
            "system_prompt": "你是一个友好的AI助手。",
            "check_interval": 1.0,
            "debug_mode": False,
            "save_screenshots": False,
            "max_history": 10,
            "min_message_length": 2,
            "segment_delimiter": "||",
            "ignore_null_response": True,
            "human_pace": "平衡",
            "base_delay_factor": 1.0,
            "max_response_time": 5,
            "min_think_time": 1.0,
            "max_think_time": 3.0,
            "typing_speed_min": 3,
            "typing_speed_max": 8,
            "show_typing_indicator": True,
            "adaptive_speed": True,
            "active_message_frequency": 1.0,
            "max_daily_active_messages": 25,
            "min_user_inactive_time": 300,
            "active_message_cooldown": 300,
            "enable_emoticon": True,
            "emoticon_folder": "Emoticon",
            "keywords": [],
            "keyword_match_mode": "fuzzy",
            "keyword_threshold": 0.8,
            "keyword_case_sensitive": False,
            "log_ignored_messages": False,
            "sleep": {
                "enabled": False,
                "sleep_start_min": 22.0,
                "sleep_end_max": 23.5,
                "wake_start_min": 6.0,
                "wake_end_max": 8.0,
                "handle_messages_in_sleep": False,
                "sleep_reply": "现在在休息，等会儿再聊~"
            },
            "command": {
                "prefix": "\\",
                "tokens": [],
                "commands": ["state", "active", "sleep", "pause", "help"]
            },
            "time_injection": {
                "enabled": True,
                "format": "%Y年%m月%d日 %H:%M:%S"
            },
            "memory_max_count": 30
        }
    
    def save_config(self):
        try:
            self.update_config()
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", "配置已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")
    
    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.create_api_tab(notebook)
        self.create_ocr_tab(notebook)
        self.create_region_tab(notebook)
        self.create_chat_tab(notebook)
        self.create_human_tab(notebook)
        self.create_active_tab(notebook)
        self.create_filter_tab(notebook)      # 新增：关键字过滤
        self.create_sleep_tab(notebook)       # 新增：睡眠模式
        self.create_command_tab(notebook)     # 新增：指令系统
        self.create_memory_tab(notebook)      # 新增：记忆系统
        self.create_emoticon_tab(notebook)
        
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(button_frame, text="保存配置", command=self.save_config).pack(side='left', padx=5)
        ttk.Button(button_frame, text="恢复默认", command=self.reset_default).pack(side='left', padx=5)
        ttk.Button(button_frame, text="打开配置目录", command=self.open_config_dir).pack(side='left', padx=5)
        ttk.Button(button_frame, text="退出", command=self.root.quit).pack(side='right', padx=5)
    
    # ==================== 各选项卡创建方法 ====================
    def create_api_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="API配置")
        frame.columnconfigure(1, weight=1)
        row = 0
        ttk.Label(frame, text="API密钥:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.api_key_var = tk.StringVar(value=self.config.get('api_key', ''))
        ttk.Entry(frame, textvariable=self.api_key_var, width=60, show='*').grid(row=row, column=1, sticky='ew', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="API网址:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.api_url_var = tk.StringVar(value=self.config.get('api_url', 'https://api.deepseek.com'))
        ttk.Entry(frame, textvariable=self.api_url_var, width=60).grid(row=row, column=1, sticky='ew', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="模型名称:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.model_name_var = tk.StringVar(value=self.config.get('model_name', 'deepseek-chat'))
        ttk.Entry(frame, textvariable=self.model_name_var, width=30).grid(row=row, column=1, sticky='w', padx=10, pady=5)
    
    def create_ocr_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="OCR配置")
        frame.columnconfigure(1, weight=1)
        row = 0
        ttk.Label(frame, text="识别语言:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.ocr_langs_var = tk.StringVar(value=','.join(self.config.get('ocr_langs', ['ch_sim', 'en'])))
        ttk.Entry(frame, textvariable=self.ocr_langs_var, width=30).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        ttk.Label(frame, text="(用逗号分隔，如: ch_sim,en,ja)").grid(row=row, column=2, sticky='w', padx=5, pady=5)
        row += 1
        self.use_gpu_var = tk.BooleanVar(value=self.config.get('use_gpu', False))
        ttk.Checkbutton(frame, text="使用GPU加速", variable=self.use_gpu_var).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1
        self.save_screenshots_var = tk.BooleanVar(value=self.config.get('save_screenshots', False))
        ttk.Checkbutton(frame, text="保存调试截图", variable=self.save_screenshots_var).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1
        self.debug_mode_var = tk.BooleanVar(value=self.config.get('debug_mode', False))
        ttk.Checkbutton(frame, text="调试模式", variable=self.debug_mode_var).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
    
    def create_region_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="消息区域")
        region = self.config.get('message_region', {})
        row = 0
        ttk.Label(frame, text="区域坐标设置:").grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=10)
        row += 1
        ttk.Label(frame, text="左上角 X:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.region_x1_var = tk.IntVar(value=region.get('x1', 500))
        ttk.Spinbox(frame, from_=0, to=3840, textvariable=self.region_x1_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="左上角 Y:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.region_y1_var = tk.IntVar(value=region.get('y1', 300))
        ttk.Spinbox(frame, from_=0, to=2160, textvariable=self.region_y1_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="右下角 X:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.region_x2_var = tk.IntVar(value=region.get('x2', 1200))
        ttk.Spinbox(frame, from_=0, to=3840, textvariable=self.region_x2_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="右下角 Y:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.region_y2_var = tk.IntVar(value=region.get('y2', 400))
        ttk.Spinbox(frame, from_=0, to=2160, textvariable=self.region_y2_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="当前区域尺寸:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.size_label = ttk.Label(frame, text=f"{region.get('width', 700)} x {region.get('height', 100)}")
        self.size_label.grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        if HAS_PYAUTOGUI:
            ttk.Button(frame, text="使用鼠标选择区域", command=self.capture_mouse_position).grid(row=row, column=0, columnspan=2, pady=10)
        else:
            ttk.Label(frame, text="未安装pyautogui，无法使用鼠标选择").grid(row=row, column=0, columnspan=2, pady=10)
    
    def create_chat_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="对话行为")
        frame.columnconfigure(1, weight=1)
        row = 0
        ttk.Label(frame, text="提示词文件:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.prompt_file_var = tk.StringVar(value=self.config.get('prompt_file', ''))
        ttk.Entry(frame, textvariable=self.prompt_file_var, width=40).grid(row=row, column=1, sticky='ew', padx=10, pady=5)
        ttk.Button(frame, text="浏览", command=self.browse_prompt_file).grid(row=row, column=2, padx=5, pady=5)
        row += 1
        ttk.Label(frame, text="系统提示词:").grid(row=row, column=0, sticky='nw', padx=10, pady=5)
        self.system_prompt_var = tk.StringVar(value=self.config.get('system_prompt', ''))
        ttk.Entry(frame, textvariable=self.system_prompt_var, width=70).grid(row=row, column=1, columnspan=2, sticky='ew', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="最大历史记录:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.max_history_var = tk.IntVar(value=self.config.get('max_history', 10))
        ttk.Spinbox(frame, from_=1, to=50, textvariable=self.max_history_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="最小消息长度:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.min_message_length_var = tk.IntVar(value=self.config.get('min_message_length', 2))
        ttk.Spinbox(frame, from_=1, to=20, textvariable=self.min_message_length_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="分段符:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.segment_delimiter_var = tk.StringVar(value=self.config.get('segment_delimiter', '||'))
        ttk.Entry(frame, textvariable=self.segment_delimiter_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="检查间隔(秒):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.check_interval_var = tk.DoubleVar(value=self.config.get('check_interval', 1.0))
        ttk.Spinbox(frame, from_=0.1, to=10.0, increment=0.1, textvariable=self.check_interval_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        self.ignore_null_var = tk.BooleanVar(value=self.config.get('ignore_null_response', True))
        ttk.Checkbutton(frame, text="忽略null回复", variable=self.ignore_null_var).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
    
    def create_human_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="人性化设置")
        row = 0
        ttk.Label(frame, text="对话节奏:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.human_pace_var = tk.StringVar(value=self.config.get('human_pace', '平衡'))
        ttk.Combobox(frame, textvariable=self.human_pace_var, values=['快速', '平衡', '慢速']).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="最小思考时间(秒):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.min_think_var = tk.DoubleVar(value=self.config.get('min_think_time', 1.0))
        ttk.Spinbox(frame, from_=0.1, to=5.0, increment=0.1, textvariable=self.min_think_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="最大思考时间(秒):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.max_think_var = tk.DoubleVar(value=self.config.get('max_think_time', 3.0))
        ttk.Spinbox(frame, from_=0.5, to=10.0, increment=0.1, textvariable=self.max_think_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="最慢打字速度(字符/秒):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.speed_min_var = tk.IntVar(value=self.config.get('typing_speed_min', 3))
        ttk.Spinbox(frame, from_=1, to=20, textvariable=self.speed_min_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="最快打字速度(字符/秒):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.speed_max_var = tk.IntVar(value=self.config.get('typing_speed_max', 8))
        ttk.Spinbox(frame, from_=1, to=30, textvariable=self.speed_max_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="最大响应时间(秒):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.max_response_var = tk.IntVar(value=self.config.get('max_response_time', 5))
        ttk.Spinbox(frame, from_=1, to=20, textvariable=self.max_response_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        self.show_indicator_var = tk.BooleanVar(value=self.config.get('show_typing_indicator', True))
        ttk.Checkbutton(frame, text="显示正在输入提示", variable=self.show_indicator_var).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1
        self.adaptive_speed_var = tk.BooleanVar(value=self.config.get('adaptive_speed', True))
        ttk.Checkbutton(frame, text="自适应速度", variable=self.adaptive_speed_var).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
    
    def create_active_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="主动消息")
        row = 0
        ttk.Label(frame, text="主动消息频率(次/小时):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.active_freq_var = tk.DoubleVar(value=self.config.get('active_message_frequency', 1.0))
        ttk.Spinbox(frame, from_=0, to=5, increment=0.1, textvariable=self.active_freq_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="每日最大主动数:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.max_daily_var = tk.IntVar(value=self.config.get('max_daily_active_messages', 25))
        ttk.Spinbox(frame, from_=0, to=50, textvariable=self.max_daily_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="用户不活跃阈值(秒):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.inactive_time_var = tk.IntVar(value=self.config.get('min_user_inactive_time', 300))
        ttk.Spinbox(frame, from_=10, to=600, increment=10, textvariable=self.inactive_time_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="主动后冷却(秒):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.cooldown_var = tk.IntVar(value=self.config.get('active_message_cooldown', 300))
        ttk.Spinbox(frame, from_=30, to=3600, increment=30, textvariable=self.cooldown_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
    
    def create_filter_tab(self, notebook):
        """关键字过滤配置"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="关键字过滤")
        row = 0
        ttk.Label(frame, text="关键字列表(逗号分隔):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.keywords_var = tk.StringVar(value=','.join(self.config.get('keywords', [])))
        ttk.Entry(frame, textvariable=self.keywords_var, width=50).grid(row=row, column=1, sticky='ew', padx=10, pady=5)
        tk.Label(frame, text="例如: 你好,在吗,help").grid(row=row, column=2, sticky='w', padx=5, pady=5)
        row += 1
        ttk.Label(frame, text="匹配模式:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.match_mode_var = tk.StringVar(value=self.config.get('keyword_match_mode', 'fuzzy'))
        ttk.Combobox(frame, textvariable=self.match_mode_var, values=['fuzzy', 'exact'], width=15).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        ttk.Label(frame, text="fuzzy=模糊匹配(编辑距离), exact=精确子串").grid(row=row, column=2, sticky='w', padx=5, pady=5)
        row += 1
        ttk.Label(frame, text="模糊匹配阈值(0.5-1.0):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.threshold_var = tk.DoubleVar(value=self.config.get('keyword_threshold', 0.8))
        ttk.Spinbox(frame, from_=0.5, to=1.0, increment=0.05, textvariable=self.threshold_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        self.case_sensitive_var = tk.BooleanVar(value=self.config.get('keyword_case_sensitive', False))
        ttk.Checkbutton(frame, text="区分大小写", variable=self.case_sensitive_var).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1
        self.log_ignored_var = tk.BooleanVar(value=self.config.get('log_ignored_messages', False))
        ttk.Checkbutton(frame, text="记录被忽略的消息", variable=self.log_ignored_var).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
    
    def create_sleep_tab(self, notebook):
        """睡眠模式配置"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="睡眠模式")
        sleep = self.config.get('sleep', {})
        row = 0
        self.sleep_enabled_var = tk.BooleanVar(value=sleep.get('enabled', False))
        ttk.Checkbutton(frame, text="启用睡眠模式", variable=self.sleep_enabled_var).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="最早入睡时间(小时,0-23):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.sleep_start_var = tk.DoubleVar(value=sleep.get('sleep_start_min', 22.0))
        ttk.Spinbox(frame, from_=0, to=23.5, increment=0.1, textvariable=self.sleep_start_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="最晚入睡时间(小时,0-23):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.sleep_end_var = tk.DoubleVar(value=sleep.get('sleep_end_max', 23.5))
        ttk.Spinbox(frame, from_=0, to=23.5, increment=0.1, textvariable=self.sleep_end_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="最早醒来时间(小时,0-23):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.wake_start_var = tk.DoubleVar(value=sleep.get('wake_start_min', 6.0))
        ttk.Spinbox(frame, from_=0, to=23.5, increment=0.1, textvariable=self.wake_start_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="最晚醒来时间(小时,0-23):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.wake_end_var = tk.DoubleVar(value=sleep.get('wake_end_max', 8.0))
        ttk.Spinbox(frame, from_=0, to=23.5, increment=0.1, textvariable=self.wake_end_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        self.handle_in_sleep_var = tk.BooleanVar(value=sleep.get('handle_messages_in_sleep', False))
        ttk.Checkbutton(frame, text="睡眠期间处理新消息", variable=self.handle_in_sleep_var).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="睡眠回复语:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.sleep_reply_var = tk.StringVar(value=sleep.get('sleep_reply', '现在在休息，等会儿再聊~'))
        ttk.Entry(frame, textvariable=self.sleep_reply_var, width=60).grid(row=row, column=1, sticky='ew', padx=10, pady=5)
    
    def create_command_tab(self, notebook):
        """指令系统配置"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="指令系统")
        cmd = self.config.get('command', {})
        row = 0
        ttk.Label(frame, text="指令引导符:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.prefix_var = tk.StringVar(value=cmd.get('prefix', '\\'))
        ttk.Entry(frame, textvariable=self.prefix_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        ttk.Label(frame, text="(例如 \\ 或 %)").grid(row=row, column=2, sticky='w', padx=5, pady=5)
        row += 1
        ttk.Label(frame, text="权限令牌(逗号分隔):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        tokens = cmd.get('tokens', [])
        self.tokens_var = tk.StringVar(value=','.join(tokens))
        ttk.Entry(frame, textvariable=self.tokens_var, width=50).grid(row=row, column=1, sticky='ew', padx=10, pady=5)
        ttk.Label(frame, text="留空则不验证令牌").grid(row=row, column=2, sticky='w', padx=5, pady=5)
        row += 1
        ttk.Label(frame, text="可用指令列表(只读):").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        commands = cmd.get('commands', ['state', 'active', 'sleep', 'pause', 'help'])
        ttk.Label(frame, text=', '.join(commands)).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        ttk.Label(frame, text="如需修改，请直接编辑config.json").grid(row=row, column=2, sticky='w', padx=5, pady=5)
    
    def create_memory_tab(self, notebook):
        """记忆系统配置"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="记忆系统")
        row = 0
        ttk.Label(frame, text="记忆最大保留条数:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.memory_max_count_var = tk.IntVar(value=self.config.get('memory_max_count', 30))
        ttk.Spinbox(frame, from_=1, to=200, textvariable=self.memory_max_count_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        ttk.Label(frame, text="(超过此数量的旧记忆将被自动丢弃)").grid(row=row, column=2, sticky='w', padx=5, pady=5)
        row += 1
        ttk.Label(frame, text="时间注入:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        time_inj = self.config.get('time_injection', {})
        self.time_inj_enabled_var = tk.BooleanVar(value=time_inj.get('enabled', True))
        ttk.Checkbutton(frame, text="启用", variable=self.time_inj_enabled_var).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="时间格式:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.time_format_var = tk.StringVar(value=time_inj.get('format', '%Y年%m月%d日 %H:%M:%S'))
        ttk.Entry(frame, textvariable=self.time_format_var, width=40).grid(row=row, column=1, sticky='w', padx=10, pady=5)
    
    def create_emoticon_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="表情图片")
        row = 0
        self.enable_emoticon_var = tk.BooleanVar(value=self.config.get('enable_emoticon', True))
        ttk.Checkbutton(frame, text="启用表情图片功能", variable=self.enable_emoticon_var).grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="表情图片文件夹:").grid(row=row, column=0, sticky='w', padx=10, pady=5)
        self.emoticon_folder_var = tk.StringVar(value=self.config.get('emoticon_folder', 'Emoticon'))
        ttk.Entry(frame, textvariable=self.emoticon_folder_var, width=30).grid(row=row, column=1, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="支持的格式: PNG, JPG, GIF, BMP").grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="用法: 在回复中使用 [图片名]").grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        row += 1
        ttk.Label(frame, text="例如: 今天天气真好 [sun]").grid(row=row, column=0, columnspan=2, sticky='w', padx=10, pady=5)
    
    # ==================== 辅助方法 ====================
    def browse_prompt_file(self):
        filename = filedialog.askopenfilename(title="选择提示词文件", filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if filename:
            self.prompt_file_var.set(filename)
    
    def capture_mouse_position(self):
        if not HAS_PYAUTOGUI:
            messagebox.showerror("错误", "未安装pyautogui，无法使用此功能")
            return
        messagebox.showinfo("提示", "请将鼠标移动到消息区域左上角，然后按确定")
        x1, y1 = pyautogui.position()
        messagebox.showinfo("提示", "请将鼠标移动到消息区域右下角，然后按确定")
        x2, y2 = pyautogui.position()
        self.region_x1_var.set(min(x1, x2))
        self.region_y1_var.set(min(y1, y2))
        self.region_x2_var.set(max(x1, x2))
        self.region_y2_var.set(max(y1, y2))
        # 更新尺寸显示
        width = self.region_x2_var.get() - self.region_x1_var.get()
        height = self.region_y2_var.get() - self.region_y1_var.get()
        self.size_label.config(text=f"{width} x {height}")
    
    def open_config_dir(self):
        os.startfile(os.path.dirname(self.config_path))
    
    def reset_default(self):
        if messagebox.askyesno("确认", "确定要恢复默认配置吗？"):
            self.config = self.get_default_config()
            self.refresh_vars()
    
    def refresh_vars(self):
        # API
        self.api_key_var.set(self.config.get('api_key', ''))
        self.api_url_var.set(self.config.get('api_url', 'https://api.deepseek.com'))
        self.model_name_var.set(self.config.get('model_name', 'deepseek-chat'))
        # OCR
        self.ocr_langs_var.set(','.join(self.config.get('ocr_langs', ['ch_sim', 'en'])))
        self.use_gpu_var.set(self.config.get('use_gpu', False))
        self.save_screenshots_var.set(self.config.get('save_screenshots', False))
        self.debug_mode_var.set(self.config.get('debug_mode', False))
        # 区域
        region = self.config.get('message_region', {})
        self.region_x1_var.set(region.get('x1', 500))
        self.region_y1_var.set(region.get('y1', 300))
        self.region_x2_var.set(region.get('x2', 1200))
        self.region_y2_var.set(region.get('y2', 400))
        self.size_label.config(text=f"{region.get('width', 700)} x {region.get('height', 100)}")
        # 对话
        self.prompt_file_var.set(self.config.get('prompt_file', ''))
        self.system_prompt_var.set(self.config.get('system_prompt', ''))
        self.max_history_var.set(self.config.get('max_history', 10))
        self.min_message_length_var.set(self.config.get('min_message_length', 2))
        self.segment_delimiter_var.set(self.config.get('segment_delimiter', '||'))
        self.check_interval_var.set(self.config.get('check_interval', 1.0))
        self.ignore_null_var.set(self.config.get('ignore_null_response', True))
        # 人性化
        self.human_pace_var.set(self.config.get('human_pace', '平衡'))
        self.min_think_var.set(self.config.get('min_think_time', 1.0))
        self.max_think_var.set(self.config.get('max_think_time', 3.0))
        self.speed_min_var.set(self.config.get('typing_speed_min', 3))
        self.speed_max_var.set(self.config.get('typing_speed_max', 8))
        self.max_response_var.set(self.config.get('max_response_time', 5))
        self.show_indicator_var.set(self.config.get('show_typing_indicator', True))
        self.adaptive_speed_var.set(self.config.get('adaptive_speed', True))
        # 主动消息
        self.active_freq_var.set(self.config.get('active_message_frequency', 1.0))
        self.max_daily_var.set(self.config.get('max_daily_active_messages', 25))
        self.inactive_time_var.set(self.config.get('min_user_inactive_time', 300))
        self.cooldown_var.set(self.config.get('active_message_cooldown', 300))
        # 关键字过滤
        self.keywords_var.set(','.join(self.config.get('keywords', [])))
        self.match_mode_var.set(self.config.get('keyword_match_mode', 'fuzzy'))
        self.threshold_var.set(self.config.get('keyword_threshold', 0.8))
        self.case_sensitive_var.set(self.config.get('keyword_case_sensitive', False))
        self.log_ignored_var.set(self.config.get('log_ignored_messages', False))
        # 睡眠模式
        sleep = self.config.get('sleep', {})
        self.sleep_enabled_var.set(sleep.get('enabled', False))
        self.sleep_start_var.set(sleep.get('sleep_start_min', 22.0))
        self.sleep_end_var.set(sleep.get('sleep_end_max', 23.5))
        self.wake_start_var.set(sleep.get('wake_start_min', 6.0))
        self.wake_end_var.set(sleep.get('wake_end_max', 8.0))
        self.handle_in_sleep_var.set(sleep.get('handle_messages_in_sleep', False))
        self.sleep_reply_var.set(sleep.get('sleep_reply', '现在在休息，等会儿再聊~'))
        # 指令系统
        cmd = self.config.get('command', {})
        self.prefix_var.set(cmd.get('prefix', '\\'))
        self.tokens_var.set(','.join(cmd.get('tokens', [])))
        # 记忆系统
        self.memory_max_count_var.set(self.config.get('memory_max_count', 30))
        time_inj = self.config.get('time_injection', {})
        self.time_inj_enabled_var.set(time_inj.get('enabled', True))
        self.time_format_var.set(time_inj.get('format', '%Y年%m月%d日 %H:%M:%S'))
        # 表情
        self.enable_emoticon_var.set(self.config.get('enable_emoticon', True))
        self.emoticon_folder_var.set(self.config.get('emoticon_folder', 'Emoticon'))
    
    def update_config(self):
        # API
        self.config['api_key'] = self.api_key_var.get()
        self.config['api_url'] = self.api_url_var.get()
        self.config['model_name'] = self.model_name_var.get()
        # OCR
        self.config['ocr_langs'] = [lang.strip() for lang in self.ocr_langs_var.get().split(',') if lang.strip()] or ['ch_sim', 'en']
        self.config['use_gpu'] = self.use_gpu_var.get()
        self.config['save_screenshots'] = self.save_screenshots_var.get()
        self.config['debug_mode'] = self.debug_mode_var.get()
        # 区域
        self.config['message_region'] = {
            'x1': self.region_x1_var.get(),
            'y1': self.region_y1_var.get(),
            'x2': self.region_x2_var.get(),
            'y2': self.region_y2_var.get(),
            'width': self.region_x2_var.get() - self.region_x1_var.get(),
            'height': self.region_y2_var.get() - self.region_y1_var.get()
        }
        # 对话
        self.config['prompt_file'] = self.prompt_file_var.get() or None
        self.config['system_prompt'] = self.system_prompt_var.get()
        self.config['max_history'] = self.max_history_var.get()
        self.config['min_message_length'] = self.min_message_length_var.get()
        self.config['segment_delimiter'] = self.segment_delimiter_var.get()
        self.config['check_interval'] = self.check_interval_var.get()
        self.config['ignore_null_response'] = self.ignore_null_var.get()
        # 人性化
        self.config['human_pace'] = self.human_pace_var.get()
        self.config['min_think_time'] = self.min_think_var.get()
        self.config['max_think_time'] = self.max_think_var.get()
        self.config['typing_speed_min'] = self.speed_min_var.get()
        self.config['typing_speed_max'] = self.speed_max_var.get()
        self.config['max_response_time'] = self.max_response_var.get()
        self.config['show_typing_indicator'] = self.show_indicator_var.get()
        self.config['adaptive_speed'] = self.adaptive_speed_var.get()
        # 主动消息
        freq = self.active_freq_var.get()
        self.config['active_message_frequency'] = freq
        if freq > 0:
            avg_interval = 3600 / freq
            self.config['active_message_min_interval'] = int(avg_interval * 0.7)
            self.config['active_message_max_interval'] = int(avg_interval * 1.3)
        self.config['max_daily_active_messages'] = self.max_daily_var.get()
        self.config['min_user_inactive_time'] = self.inactive_time_var.get()
        self.config['active_message_cooldown'] = self.cooldown_var.get()
        # 关键字过滤
        keywords = [kw.strip() for kw in self.keywords_var.get().split(',') if kw.strip()]
        self.config['keywords'] = keywords
        self.config['keyword_match_mode'] = self.match_mode_var.get()
        self.config['keyword_threshold'] = self.threshold_var.get()
        self.config['keyword_case_sensitive'] = self.case_sensitive_var.get()
        self.config['log_ignored_messages'] = self.log_ignored_var.get()
        # 睡眠模式
        self.config['sleep'] = {
            "enabled": self.sleep_enabled_var.get(),
            "sleep_start_min": self.sleep_start_var.get(),
            "sleep_end_max": self.sleep_end_var.get(),
            "wake_start_min": self.wake_start_var.get(),
            "wake_end_max": self.wake_end_var.get(),
            "handle_messages_in_sleep": self.handle_in_sleep_var.get(),
            "sleep_reply": self.sleep_reply_var.get()
        }
        # 指令系统
        tokens = [t.strip() for t in self.tokens_var.get().split(',') if t.strip()]
        self.config['command'] = {
            "prefix": self.prefix_var.get(),
            "tokens": tokens,
            "commands": ["state", "active", "sleep", "pause", "help"]
        }
        # 记忆系统
        self.config['memory_max_count'] = self.memory_max_count_var.get()
        self.config['time_injection'] = {
            "enabled": self.time_inj_enabled_var.get(),
            "format": self.time_format_var.get()
        }
        # 表情
        self.config['enable_emoticon'] = self.enable_emoticon_var.get()
        self.config['emoticon_folder'] = self.emoticon_folder_var.get()
    
    def save_config(self):
        try:
            self.update_config()
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", "配置已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

def main():
    root = tk.Tk()
    app = ConfigUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()