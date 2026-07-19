# -*- coding: utf-8 -*-
"""
PaperAiChat Web 仪表盘 - 实时监控与远程控制
基于 Flask + SocketIO 实现
"""

import os
import sys
import json
import time
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit

# ---------- Flask 应用 ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBUI_DIR = os.path.join(BASE_DIR, "webui")

app = Flask(__name__, template_folder=os.path.join(WEBUI_DIR, "templates"),
            static_folder=os.path.join(WEBUI_DIR, "static"))
app.config["SECRET_KEY"] = os.urandom(24).hex()
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading",
                    ping_interval=10, ping_timeout=30)


class DashboardState:
    """共享状态对象，Bot 与 Web 之间通过此对象交换数据"""
    def __init__(self):
        self.lock = threading.Lock()
        # 运行状态
        self.running = True
        self.paused = False
        self.is_asleep = False
        self.sleep_until = None
        self.cmd_disabled = False
        # 统计
        self.session_id = ""
        self.start_time = 0
        self.message_count = 0
        self.error_count = 0
        self.null_response_count = 0
        self.total_typed_chars = 0
        self.total_typing_time = 0.0
        self.avg_response_time = 0.0
        self.response_times = []
        self.active_message_count = 0
        self.daily_active_count = 0
        self.last_active_message_time = 0
        self.last_user_message_time = 0
        self.last_response_time = 0
        self.consecutive_fast_responses = 0
        # API 统计
        self.api_last_call_time = 0
        self.api_last_latency_ms = 0
        self.api_last_tokens = 0
        self.api_total_calls = 0
        self.api_total_tokens = 0
        self.api_total_latency_ms = 0.0
        # 最近日志
        self.recent_logs = []  # [(timestamp, level, category, message), ...] 最多200条
        self.max_logs = 200
        # 最近消息
        self.recent_messages = []  # [(timestamp, role, content[:100]), ...] 最多50条
        self.max_messages = 50
        # 配置快照
        self.config_snapshot = {}
        # 版本
        self.version = "8.3.0"

    def update_stats(self, bot):
        """从 Bot 实例同步统计数据"""
        with self.lock:
            self.running = bot.running
            self.paused = bot.paused
            self.is_asleep = bot.is_sleeping() if hasattr(bot, 'is_sleeping') else False
            self.sleep_until = bot.sleep_until if hasattr(bot, 'sleep_until') else None
            self.cmd_disabled = bot.cmd_disabled if hasattr(bot, 'cmd_disabled') else False
            self.session_id = bot.session_id
            self.start_time = bot.start_time
            self.message_count = bot.message_count
            self.error_count = bot.error_count
            self.null_response_count = bot.null_response_count
            self.total_typed_chars = bot.total_typed_chars
            self.total_typing_time = bot.total_typing_time
            self.avg_response_time = bot.avg_response_time
            self.response_times = list(bot.response_times[-20:]) if hasattr(bot, 'response_times') else []
            self.active_message_count = bot.active_message_count
            self.daily_active_count = bot.daily_active_count
            self.last_active_message_time = bot.last_active_message_time
            self.last_user_message_time = bot.last_user_message_time
            self.last_response_time = bot.last_response_time if hasattr(bot, 'last_response_time') else 0
            self.consecutive_fast_responses = bot.consecutive_fast_responses
            self.config_snapshot = {
                "api_url": bot.config.get("api_url", ""),
                "model_name": bot.config.get("model_name", ""),
                "human_pace": bot.config.get("human_pace", "平衡"),
                "check_interval": bot.config.get("check_interval", 1.0),
                "max_history": bot.config.get("max_history", 10),
                "debug_mode": bot.config.get("debug_mode", False),
                "keywords": bot.config.get("keywords", []),
                "sleep_enabled": bot.config.get("sleep", {}).get("enabled", False),
                "active_message_frequency": bot.config.get("active_message_frequency", 1.0),
                "max_daily_active_messages": bot.config.get("max_daily_active_messages", 25),
                "typing_speed_min": bot.config.get("typing_speed_min", 3),
                "typing_speed_max": bot.config.get("typing_speed_max", 8),
                "command_prefix": bot.config.get("command", {}).get("prefix", "\\"),
            }

    def add_log(self, timestamp, level, category, message):
        with self.lock:
            self.recent_logs.append((timestamp, level, category, message))
            if len(self.recent_logs) > self.max_logs:
                self.recent_logs = self.recent_logs[-self.max_logs:]

    def add_message(self, timestamp, role, content):
        with self.lock:
            self.recent_messages.append((timestamp, role, content[:200]))
            if len(self.recent_messages) > self.max_messages:
                self.recent_messages = self.recent_messages[-self.max_messages:]

    def record_api_call(self, latency_ms, tokens):
        with self.lock:
            self.api_last_call_time = time.time()
            self.api_last_latency_ms = latency_ms
            self.api_last_tokens = tokens
            self.api_total_calls += 1
            self.api_total_tokens += tokens
            self.api_total_latency_ms += latency_ms

    def get_snapshot(self):
        """获取完整状态快照（线程安全）"""
        with self.lock:
            elapsed = time.time() - self.start_time if self.start_time else 0
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            active_msg_rate = self.active_message_count / (elapsed / 3600) if elapsed > 0 else 0
            avg_speed = self.total_typed_chars / self.total_typing_time if self.total_typing_time > 0 else 0
            avg_api_latency = self.api_total_latency_ms / self.api_total_calls if self.api_total_calls > 0 else 0

            return {
                "version": self.version,
                "session_id": self.session_id,
                "timestamp": time.time(),
                "running": self.running,
                "paused": self.paused,
                "is_asleep": self.is_asleep,
                "sleep_until": self.sleep_until.strftime("%H:%M") if self.sleep_until else None,
                "cmd_disabled": self.cmd_disabled,
                "uptime": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
                "uptime_seconds": elapsed,
                "message_count": self.message_count,
                "error_count": self.error_count,
                "null_response_count": self.null_response_count,
                "total_typed_chars": self.total_typed_chars,
                "total_typing_time": round(self.total_typing_time, 1),
                "avg_typing_speed": round(avg_speed, 1),
                "avg_response_time": round(self.avg_response_time, 2),
                "response_times": self.response_times,
                "active_message_count": self.active_message_count,
                "daily_active_count": self.daily_active_count,
                "last_active_message_ago": self._format_ago(self.last_active_message_time),
                "last_user_message_ago": self._format_ago(self.last_user_message_time),
                "last_response_ago": self._format_ago(self.last_response_time),
                "consecutive_fast_responses": self.consecutive_fast_responses,
                "active_msg_rate": round(active_msg_rate, 2),
                # API stats
                "api_last_latency_ms": round(self.api_last_latency_ms, 0),
                "api_last_tokens": self.api_last_tokens,
                "api_total_calls": self.api_total_calls,
                "api_total_tokens": self.api_total_tokens,
                "api_avg_latency_ms": round(avg_api_latency, 0),
                "api_last_call_ago": self._format_ago(self.api_last_call_time),
                # Config
                "config": self.config_snapshot,
                # Recent logs (last 30)
                "recent_logs": [{"ts": ts, "level": lv, "cat": cat, "msg": msg[:150]}
                                for ts, lv, cat, msg in self.recent_logs[-30:]],
                # Recent messages (last 20)
                "recent_messages": [{"ts": ts, "role": r, "content": c}
                                    for ts, r, c in self.recent_messages[-20:]],
            }

    def _format_ago(self, ts):
        if not ts or ts == 0:
            return "从未"
        diff = time.time() - ts
        if diff < 60:
            return f"{int(diff)}秒前"
        elif diff < 3600:
            return f"{int(diff/60)}分钟前"
        elif diff < 86400:
            return f"{int(diff/3600)}小时前"
        return f"{int(diff/86400)}天前"


# 全局仪表盘状态
dashboard = DashboardState()


# ==================== Flask 路由 ====================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    return jsonify(dashboard.get_snapshot())


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    config_path = os.path.join(BASE_DIR, "config.json")
    if request.method == "GET":
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            # 隐藏 API Key
            if cfg.get("api_key"):
                cfg["api_key"] = cfg["api_key"][:8] + "****" if len(cfg["api_key"]) > 8 else "****"
            return jsonify(cfg)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            data = request.get_json()
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            # 只更新允许的字段
            allowed = ["api_url", "model_name", "check_interval", "debug_mode",
                       "max_history", "min_message_length", "segment_delimiter",
                       "ignore_null_response", "human_pace", "min_think_time",
                       "max_think_time", "typing_speed_min", "typing_speed_max",
                       "max_response_time", "show_typing_indicator", "adaptive_speed",
                       "active_message_frequency", "max_daily_active_messages",
                       "min_user_inactive_time", "active_message_cooldown",
                       "enable_emoticon", "emoticon_folder", "keywords",
                       "keyword_match_mode", "keyword_threshold", "keyword_case_sensitive",
                       "log_ignored_messages", "memory_max_count"]
            for key in allowed:
                if key in data:
                    cfg[key] = data[key]
            # 更新 API Key（如果提供了新值且不是掩码）
            if "api_key" in data and data["api_key"] and "****" not in data["api_key"]:
                cfg["api_key"] = data["api_key"]
            # 更新睡眠配置
            if "sleep" in data:
                cfg.setdefault("sleep", {}).update(data["sleep"])
            # 更新时间注入
            if "time_injection" in data:
                cfg.setdefault("time_injection", {}).update(data["time_injection"])
            # 更新指令配置
            if "command" in data:
                cfg.setdefault("command", {}).update(data["command"])
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            dashboard.config_snapshot.update({
                "api_url": cfg.get("api_url", ""),
                "model_name": cfg.get("model_name", ""),
                "human_pace": cfg.get("human_pace", "平衡"),
            })
            return jsonify({"success": True, "message": "配置已保存，重启后生效"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500


# ==================== SocketIO 事件 ====================

@socketio.on("connect")
def handle_connect():
    """客户端连接时立即推送状态"""
    emit("stats_update", dashboard.get_snapshot())
    dashboard.add_log(datetime.now().strftime("%H:%M:%S"), "INFO", "WEB", "仪表盘客户端已连接")


@socketio.on("disconnect")
def handle_disconnect():
    dashboard.add_log(datetime.now().strftime("%H:%M:%S"), "INFO", "WEB", "仪表盘客户端已断开")


@socketio.on("request_stats")
def handle_request_stats():
    emit("stats_update", dashboard.get_snapshot())


@socketio.on("bot_command")
def handle_bot_command(data):
    """接收来自 Web 的控制指令，通过共享状态 + 回调执行"""
    cmd = data.get("command", "")
    args = data.get("args", {})
    ts = datetime.now().strftime("%H:%M:%S")

    # 指令通过回调函数传递给 Bot 主线程
    if hasattr(dashboard, "_command_callback") and dashboard._command_callback:
        try:
            result = dashboard._command_callback(cmd, args)
            emit("command_result", {"success": True, "command": cmd, "result": result})
            dashboard.add_log(ts, "INFO", "WEB", f"执行指令: {cmd} → {result}")
        except Exception as e:
            emit("command_result", {"success": False, "command": cmd, "error": str(e)})
            dashboard.add_log(ts, "ERROR", "WEB", f"指令失败: {cmd} - {e}")
    else:
        emit("command_result", {"success": False, "command": cmd, "error": "Bot 未注册指令回调"})
        dashboard.add_log(ts, "WARNING", "WEB", f"指令无法执行（Bot 未连接）: {cmd}")


def set_command_callback(callback):
    """注册 Bot 指令回调函数"""
    dashboard._command_callback = callback


# ==================== 后台推送线程 ====================
_push_thread = None
_push_running = False


def _push_loop(interval=1.0):
    global _push_running
    while _push_running:
        try:
            socketio.emit("stats_update", dashboard.get_snapshot())
        except Exception:
            pass
        time.sleep(interval)


def start_push_thread(interval=1.0):
    global _push_thread, _push_running
    if _push_thread and _push_thread.is_alive():
        return
    _push_running = True
    _push_thread = threading.Thread(target=_push_loop, args=(interval,), daemon=True)
    _push_thread.start()


def stop_push_thread():
    global _push_running
    _push_running = False


# ==================== 启动函数 ====================
def start_server(host="0.0.0.0", port=5888, debug=False):
    """启动 Web 仪表盘服务器（在独立线程中运行）"""
    start_push_thread(interval=1.5)
    print(f"\n[Web仪表盘] 启动于 http://{host}:{port}")
    print(f"[Web仪表盘] 本地访问: http://127.0.0.1:{port}\n")
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


def start_server_thread(host="0.0.0.0", port=5888):
    """在后台线程启动服务器"""
    t = threading.Thread(target=start_server, args=(host, port), daemon=True)
    t.start()
    return t
