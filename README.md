# PaperAiChat

基于OCR视觉识别和大语言模型的聊天自动化工具，通过模拟人类视觉和操作行为，将微信等聊天软件无缝融入AI服务端和客户端。

## 项目原理

传统聊天机器人需要对接官方API，而PaperAiChat采用视觉模拟方案：

- **微信即服务端**：通过OCR识别聊天区域截图，获取用户消息
- **微信即客户端**：通过模拟键盘输入和鼠标操作，发送AI回复
- **行为模拟**：完整复现人类打字速度、思考时间、段落间隔等行为特征
- **视觉即接口**：将任何GUI应用转化为可编程接口，无需官方API

## 核心特性

- **OCR文字识别**：支持PaddleOCR和EasyOCR双引擎，中文识别准确率达95%以上
- **人性化模拟**：动态打字速度、思考时间、段落间隔，完全模仿真人
- **主动消息**：基于对话历史自动发起话题，频率可调，避免冷场
- **表情图片支持**：识别[文件名]格式，自动发送对应表情图片
- **多行识别**：支持用户连续输入多行，逐行智能响应
- **分段发送**：AI回复中使用||分隔符，自动分段发送
- **存档恢复**：退出时自动保存对话历史，可通过参数加载继续对话
- **睡眠模式**：支持定时睡眠和主动睡眠，可配置随机入睡/醒来时间窗口
- **指令系统**：支持在聊天消息中发送指令控制程序行为，需权限令牌验证
- **关键字过滤**：支持精确匹配和模糊匹配，只有包含指定关键字的用户消息才会被回复
- **时间注入**：可在系统提示词中自动注入当前时间

## 系统要求

- Windows 10/11 (推荐LTSC版本)
- Python 3.8 - 3.11 (Python 3.12+可能不兼容)
- 4GB以上内存 (推荐8GB)
- 屏幕分辨率建议1920x1080或更高

## 快速开始

### 1. 安装依赖

```bash
pip install easyocr pyautogui pyperclip keyboard openai pillow numpy pyperclipimg paddlepaddle paddleocr
```

推荐使用清华镜像源加速：

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple easyocr pyautogui pyperclip keyboard openai pillow numpy pyperclipimg
python -m pip install paddlepaddle==2.5.2 -f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html
pip install paddleocr==2.8.1 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 目录结构

```
PaperAiChat/
├── PaperAiChat.py          # 主程序
├── start.bat                # 启动脚本
├── up.bat                   # 依赖更新脚本
├── config.json              # 配置文件（首次运行自动生成）
├── prompt.txt               # 提示词文件（可选）
├── logs/                    # 日志和存档目录
├── Emoticon/                # 表情图片文件夹（可选）
│   ├── smile.png
│   └── hello.jpg
```

### 3. 首次运行

```bash
python PaperAiChat.py
```

或双击 `start.bat` 启动脚本（自动检查环境并安装依赖）。

首次运行会自动进入配置向导，按提示完成设置：
- API密钥和模型配置
- OCR语言选择
- 消息区域选择（鼠标框选）
- 提示词设置
- 人性化参数调整
- 睡眠模式配置
- 指令系统配置

## 配置文件说明

### API配置

```json
{
    "api_key": "sk-xxxxxxxx",
    "api_url": "https://api.deepseek.com",
    "model_name": "deepseek-chat"
}
```

### OCR配置

```json
{
    "ocr_langs": ["ch_sim", "en"],
    "use_gpu": false
}
```

### 消息区域配置

```json
{
    "message_region": {
        "x1": 366, "y1": 600,
        "x2": 751, "y2": 756,
        "width": 385, "height": 156
    }
}
```

### 运行参数

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| check_interval | 检查间隔(秒) | 1.0 |
| min_message_length | 最小消息长度 | 2 |
| max_history | 历史记录数 | 10-30 |
| segment_delimiter | 分段符 | "||" |
| ignore_null_response | 忽略null回复 | true |

### 人性化配置

| 参数 | 说明 | 推荐范围 |
|------|------|----------|
| human_pace | 对话节奏(快速/平衡/慢速) | 平衡 |
| min_think_time | 最小思考时间(秒) | 1.0-2.0 |
| max_think_time | 最大思考时间(秒) | 2.0-4.0 |
| typing_speed_min | 最慢打字速度(字符/秒) | 3-4 |
| typing_speed_max | 最快打字速度(字符/秒) | 7-9 |
| max_response_time | 最大响应时间(秒) | 5-8 |

### 主动消息配置

| 参数 | 说明 | 推荐范围 |
|------|------|----------|
| active_message_frequency | 主动频率(次/小时) | 0.5-1.5 |
| max_daily_active_messages | 每日上限 | 8-25 |
| min_user_inactive_time | 用户不活跃阈值(秒) | 60-300 |

### 睡眠模式配置

| 参数 | 说明 | 推荐范围 |
|------|------|----------|
| sleep.enabled | 是否启用睡眠模式 | true/false |
| sleep.sleep_start_min | 最早入睡时间(小时) | 22.0-23.5 |
| sleep.sleep_end_max | 最晚入睡时间(小时) | 23.5-23.9 |
| sleep.wake_start_min | 最早醒来时间(小时) | 6.0-7.0 |
| sleep.wake_end_max | 最晚醒来时间(小时) | 8.0-9.0 |
| sleep.handle_messages_in_sleep | 睡眠期间是否处理新消息 | true/false |

### 指令系统配置

| 参数 | 说明 | 示例 |
|------|------|------|
| command.prefix | 指令引导符 | "%" |
| command.tokens | 权限令牌列表 | ["admin"] |
| command.commands | 可用指令列表 | ["state","active","sleep","pause","help"] |

### 关键字过滤配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| keywords | 关键字列表 | [] |
| keyword_match_mode | 匹配模式(fuzzy/exact) | fuzzy |
| keyword_threshold | 模糊匹配相似度阈值 | 0.8 |
| keyword_case_sensitive | 是否区分大小写 | false |

## 使用指南

### 快捷键

| 按键 | 功能 |
|------|------|
| Pause/F8 | 切换暂停/继续 |
| Ctrl+P | 强制暂停 |
| Ctrl+R | 强制继续 |
| S | 显示运行状态 |
| L | 显示日志路径 |
| A | 强制发送主动消息 |
| F5 | 切换指令识别开关 |
| Q | 退出程序 |
| H | 显示帮助 |

### 聊天指令

消息中同时包含指令前缀和权限令牌即可执行指令：

| 指令 | 功能 | 示例 |
|------|------|------|
| state | 显示运行状态 | %admin state |
| active | 强制发送主动消息 | %admin active |
| sleep [小时] | 立即入睡 | %admin sleep 2 |
| pause | 切换暂停/继续 | %admin pause |
| help | 显示帮助 | %admin help |

### 表情图片使用

在Emoticon文件夹中放置图片，在AI回复中使用[文件名]格式：

```
今天天气真好 [sun]   # 自动发送sun.png/jpg/gif
```

支持格式：PNG、JPG、JPEG、GIF、BMP

### 分段发送

AI回复中使用||分隔符，程序会自动分段发送：

```
第一段内容 || 第二段内容 || 第三段内容
```

### 存档恢复

程序退出时自动保存存档到logs目录，格式：{提示词}_{时间}.json

启动时加载存档：

```bash
python PaperAiChat.py logs/default_20250214_153022.json
```

## 运行状态

按S键查看实时运行状态：

```
运行时间: 01:23:45
系统状态: 运行中
睡眠状态: 清醒
对话节奏: 平衡
平均响应时间: 2.35秒

主动消息统计:
今日主动: 3/25
总主动次数: 27
主动频率: 1.15次/小时

会话统计:
消息处理: 156
错误计数: 0
Null回复: 2
历史记录: 24

打字统计:
总输入字符: 8921
总输入时间: 1245.3秒
平均速度: 7.2字符/秒
```

## ChangeLog

### v10.0 (2026-04-11)
- 集成PaddleOCR作为主要OCR引擎，中文识别准确率提升至95%以上
- 支持双OCR引擎切换（PaddleOCR / EasyOCR）
- 优化OCR初始化流程，增加重试机制
- 修复OCR参数兼容性问题
- 更新依赖安装脚本，支持从官方whl源安装PaddlePaddle

### v9.0 (2026-04-10)
- 新增睡眠模式功能，支持定时睡眠和主动睡眠
- 新增指令系统，支持聊天消息控制程序行为
- 新增关键字过滤功能，支持精确匹配和模糊匹配
- 新增时间注入功能，可在提示词中自动注入当前时间
- 优化主动消息逻辑，避免与主循环冲突
- 修复存档恢复时对话历史未正确加载的问题
- 优化代码结构，增加多个辅助方法

### v8.0 (2026-03-15)
- 新增表情图片支持
- 优化打字模拟算法，更接近真人输入习惯
- 改进多行消息识别逻辑，支持用户连续输入
- 增加运行状态实时显示
- 修复存档加载时的变量未定义问题

### v7.0 (2026-02-14)
- 新增存档恢复功能
- 新增主动消息功能
- 优化分段发送逻辑
- 改进日志系统，增加结构化输出
- 增加启动脚本，支持自动环境检查

### v6.0 (2026-02-10)
- 重构核心架构
- 优化OCR识别流程
- 增加人性化模拟参数
- 改进错误处理机制

### v5.0 (2026-02-05)
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