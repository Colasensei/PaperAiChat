# PaperAiChat

基于 OCR 视觉识别和大语言模型的聊天自动化工具。通过模拟人类视觉和操作行为，将微信等聊天软件无缝接入 AI。

## 项目原理

传统聊天机器人需要对接官方 API，PaperAiChat 采用视觉模拟方案：

- **微信即服务端**：OCR 识别聊天区域截图，获取用户消息
- **微信即客户端**：模拟键盘输入和鼠标操作，发送 AI 回复
- **行为模拟**：完整复现人类打字速度、思考时间、段落间隔
- **视觉即接口**：任何 GUI 应用即可编程，无需官方 API

## 核心特性

- **PaddleOCR 引擎**：中英文混合识别，准确率 95% 以上
- **Rich 终端美化**：彩色日志、Live 实时状态面板、Panel 表格
- **Web 仪表盘**：Flask + Socket.IO，实时监控 / 远程控制 / API 性能图表 / 在线配置
- **人性化模拟**：动态打字速度、思考时间、段落间隔（空格和换行用按键模拟）
- **主动消息**：基于对话历史自动发起话题，频率和每日上限可调
- **表情图片**：识别 `[文件名]` 格式，自动发送 Emoticon 目录中的图片
- **分段发送**：AI 回复中用 `||` 分隔，逐段发送
- **存档恢复**：退出自动保存对话历史，启动时可加载恢复
- **睡眠模式**：定时 + 主动睡眠，随机入睡/醒来窗口
- **指令系统**：聊天消息中发送指令，权限令牌验证
- **关键字过滤**：模糊匹配（编辑距离）+ 精确子串，只回复包含关键字的消息
- **时间注入**：自动在系统提示词中注入当前时间
- **API Key 加密**：XOR 混淆存储，退出自动加密，防止明文泄露

## 系统要求

- Windows 10/11
- Python 3.8 - 3.11
- 4 GB 以上内存（推荐 8 GB）
- 屏幕分辨率 1920×1080 或更高

## 快速开始

### 1. 安装依赖

```bash
pip install pyautogui pyperclip keyboard openai pillow numpy rich flask flask-socketio paddleocr paddlepaddle
```

### 2. 目录结构

```
PaperAiChat/
├── PaperAiChat.py           # 主程序
├── ui.py                    # Tkinter 配置 UI
├── web_dashboard.py         # Web 仪表盘后端
├── Update.py                # 自动更新脚本
├── start.bat                # 启动脚本（自动安装依赖）
├── config.json              # 配置文件（首次运行自动生成）
├── ver.txt                  # 版本号
├── logs/                    # 日志 & 存档目录
├── Emoticon/                # 表情图片（可选）
├── webui/                   # Web 仪表盘前端
│   ├── templates/index.html
│   └── static/
│       ├── css/style.css
│       └── js/dashboard.js
```

### 3. 首次运行

```bash
python PaperAiChat.py
```

或双击 `start.bat`（自动检查环境并安装依赖）。

首次运行进入 Rich 彩色配置向导，按提示完成：
- API 密钥和模型
- OCR 语言
- 消息区域（鼠标框选）
- 提示词设置
- 人性化参数
- 睡眠 & 指令 & 关键字过滤

### 4. Web 仪表盘

程序启动后自动在 `http://127.0.0.1:5888` 启动 Web 面板：

| 面板 | 功能 |
|------|------|
| 总览 | 运行时长、消息、Token 消耗、响应时间趋势图、实时日志 |
| API 性能 | 调用次数、延迟分布、Token 消耗趋势 |
| 实时日志 | 按级别筛选，自动滚动 |
| 消息记录 | 用户/AI 对话时间线 |
| 配置管理 | 在线编辑并保存配置 |

## 快捷键

| 按键 | 功能 |
|------|------|
| `Pause` / `F8` | 切换暂停/继续 |
| `Ctrl+P` | 强制暂停 |
| `Ctrl+R` | 强制继续 |
| `Ctrl+S` | 显示运行状态（Rich Panel） |
| `Ctrl+L` | 显示日志路径 |
| `Ctrl+A` | 强制发送主动消息 |
| `Ctrl+H` | 显示帮助 |
| `F5` | 切换指令识别开关 |
| `Ctrl+Q` | 退出程序 |

## 聊天指令

消息中包含指令前缀和权限令牌即可执行：

| 指令 | 功能 | 示例 |
|------|------|------|
| `state` | 显示运行状态 | `%admin state` |
| `active` | 强制主动消息 | `%admin active` |
| `sleep [小时]` | 立即入睡 | `%admin sleep 2` |
| `pause` | 切换暂停/继续 | `%admin pause` |
| `help` | 显示帮助 | `%admin help` |

## 配置文件参考

```json
{
  "api_key": "sk-xxx",
  "api_url": "https://api.deepseek.com",
  "model_name": "deepseek-chat",
  "ocr_langs": ["ch_sim", "en"],
  "use_gpu": false,
  "message_region": {"x1": 540, "y1": 930, "x2": 1500, "y2": 1275},
  "check_interval": 1.0,
  "max_history": 30,
  "min_message_length": 2,
  "segment_delimiter": "||",
  "human_pace": "平衡",
  "min_think_time": 1.0,
  "max_think_time": 3.0,
  "typing_speed_min": 3,
  "typing_speed_max": 8,
  "active_message_frequency": 1.0,
  "max_daily_active_messages": 25,
  "sleep": {
    "enabled": true,
    "sleep_start_min": 23.5,
    "sleep_end_max": 23.9,
    "wake_start_min": 7.0,
    "wake_end_max": 9.0
  },
  "command": {"prefix": "%", "tokens": ["admin"]},
  "time_injection": {"enabled": true, "format": "%Y年%m月%d日 %H:%M:%S"},
  "keywords": [],
  "web_dashboard": {"enabled": true, "port": 5888}
}
```

## ChangeLog

### v8.3.0 (2026-07-19)
- **Rich 终端美化**：彩色日志、Live 实时状态面板、Panel 表格
- **Web 仪表盘**：Flask + Socket.IO，5 大面板，实时监控 + 远程控制
- **API Key 加密存储**：XOR 混淆，退出自动加密
- **空格/换行按键模拟**：修复剪切板粘贴空格失败问题
- **快捷键优化**：`S/L/A/Q/H` 改为 `Ctrl+S/L/A/Q/H`，防止误触
- 清理无用依赖（easyocr、schedule、math）
- 修复 `direct_go_to_sleep` 缺失、`go_to_sleep` 重复定义
- 修复 `init_ocr` 返回 bool 覆盖 PaddleOCR 实例

### v8.2.0
- PaddleOCR 引擎，中文识别 95%+
- 睡眠模式、指令系统、关键字过滤、时间注入

### v8.0 - v7.0
- 表情图片、存档恢复、主动消息、分段发送
- 初始版本发布
- 基础OCR识别功能
- 基础消息发送功能

## 维护建议

### 每周维护清单

1. 检查日志文件大小，清理过期日志
2. 备份重要存档
3. 验证OCR识别准确率
4. 检查API密钥和余额
5. 重启程序（无需重启系统）

### 故障排查

| 问题 | 可能原因 | 解决 |
|------|----------|------|
| OCR不识别 | 模型文件损坏 | 删除C:\Users\用户名\.paddleocr重新下载 |
| API报错 | 密钥失效/余额不足 | 登录官网检查 |
| 无法粘贴 | 输入框失去焦点 | 手动点击输入框 |
| 微信掉线 | 安全机制触发 | 重新扫码登录，降低发送频率 |
| 程序卡死 | 进程残留 | taskkill /f /im python.exe |

## 硬件建议

| 配置 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 双核2.0GHz | 四核3.0GHz+ |
| 内存 | 4GB | 16GB |
| 存储 | 10GB空闲 | SSD + 1TB HDD |
| GPU | 无需 | GTX 1650+ (可选) |

## 免责声明

本软件仅供学习研究使用。使用者需遵守：
- 微信等平台的使用条款
- 当地法律法规
- 个人隐私保护规定

过度使用可能导致账号受限，建议使用小号测试。