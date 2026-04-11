@echo off
chcp 65001 >nul
title PaperAiChat
setlocal enabledelayedexpansion

echo ================================================
echo       AI 聊天机器人 - 启动脚本
echo ================================================
echo.

:: 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
echo [信息] 工作目录: %CD%
echo.

:: 检查 Python 是否安装
echo [1/4] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python 安装！
    echo.
    echo 请先安装 Python 3.8-3.11 版本:
    echo 下载地址: https://www.python.org/downloads/release/python-31011/
    echo.
    pause
    exit /b 1
)

:: 显示 Python 版本
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set "PY_VERSION=%%i"
echo [成功] 检测到 %PY_VERSION%

:: 检查 Python 版本是否兼容
python -c "import sys; exit(0) if sys.version_info >= (3,8) and sys.version_info < (3,12) else exit(1)" >nul 2>&1
if errorlevel 1 (
    echo [警告] Python 版本可能不兼容！
    echo 推荐使用 Python 3.8-3.11 版本
    echo 当前版本: %PY_VERSION%
    echo.
    choice /c YN /m "是否继续? "
    if errorlevel 2 exit /b 1
)
echo.

:: 检查并安装依赖
echo [2/4] 检查依赖包...

:: 检查是否已安装依赖
python -c "import easyocr, pyautogui, pyperclip, keyboard, openai, PIL, numpy, schedule,pyperclipimg" >nul 2>&1
if errorlevel 1 (
    echo [信息] 正在安装依赖包（使用清华镜像源）...
    echo.
    
    :: 安装基础依赖
    pip install easyocr -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install pyautogui -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install pyperclip -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install keyboard -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install openai -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install numpy -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install schedule -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install pyperclipimg -i https://pypi.tuna.tsinghua.edu.cn/simple
    
    echo.
    echo [成功] 依赖包安装完成
) else (
    echo [成功] 所有依赖包已存在
)
echo.

:: 检查主程序文件
echo [3/4] 检查主程序文件...
if not exist "PaperAiChat.py" (
    echo [错误] 未找到 PaperAiChat.py！
    echo 请确保该文件位于当前目录: %CD%
    echo.
    dir *.py
    echo.
    pause
    exit /b 1
)
echo [成功] 找到 PaperAiChat.py
echo.

:: 存档选择
set "ARCHIVE_ARG="
echo [可选] 是否加载历史存档？
echo.
choice /c YN /m "是否加载存档?  "
if errorlevel 2 (
    echo [信息] 将启动新会话
) else (
    if exist "logs\" (
        echo.
        echo 可用的存档文件:
        dir /b logs\*.json 2>nul
        echo.
        echo 请输入存档文件完整路径（可拖拽文件到此处，直接回车则不加载）:
        set /p "ARCHIVE_PATH=%CD%\logs\"
        rem 注意：这里必须启用延迟扩展或在外部使用
    ) else (
        echo [信息] logs目录不存在，无法加载存档
    )
)

:: 单独处理存档路径（只能从程序目录下的logs文件夹加载）
if defined ARCHIVE_PATH (
    rem 去除可能存在的引号和前后空格
    set "ARCHIVE_PATH=!ARCHIVE_PATH:"=!"
    
    rem 构建正确的路径：程序目录\logs\文件名
    set "ARCHIVE_ARG=%SCRIPT_DIR%logs\!ARCHIVE_PATH!"
    
    rem 如果输入的是完整路径，提取文件名
    for %%a in ("!ARCHIVE_PATH!") do set "ARCHIVE_FILENAME=%%~nxa"
    set "ARCHIVE_ARG=%SCRIPT_DIR%logs\!ARCHIVE_FILENAME!"
    
    rem 检查文件是否存在
    if exist "!ARCHIVE_ARG!" (
        echo [信息] 将加载存档: !ARCHIVE_ARG!
    ) else (
        echo [警告] 存档文件不存在: !ARCHIVE_ARG!
        set "ARCHIVE_ARG="
        echo [信息] 将启动新会话
    )
) else (
    echo [信息] 将启动新会话
)

echo.

:: 显示启动信息
echo [4/4] 准备启动程序...
echo.

:: 询问是否立即启动
choice /c YN /m "是否立即启动 ? "
if errorlevel 2 (
    echo.
    echo 已取消启动今天
    pause
    exit /b 0
)

echo.
echo [启动] 正在启动 ...
echo [提示] 首次运行会自动进入配置向导，请按提示完成设置
echo [提示] 程序运行中可随时按 Q 键退出
echo.

:: 启用延迟扩展，以便在条件语句中使用变量
setlocal enabledelayedexpansion

:: 运行主程序（带存档参数）
if defined ARCHIVE_PATH (
    rem 构建正确的存档路径：程序目录\logs\文件名
    for %%a in ("%ARCHIVE_PATH%") do set "ARCHIVE_FILENAME=%%~nxa"
    set "ARCHIVE_ARG=%SCRIPT_DIR%logs\%ARCHIVE_FILENAME%"
    
    if exist "!ARCHIVE_ARG!" (
        echo [信息] 将加载存档: !ARCHIVE_ARG!
        python -u PaperAiChat.py "!ARCHIVE_ARG!"
    ) else (
        echo [错误] 存档文件不存在: !ARCHIVE_ARG!
        echo [信息] 将启动新会话
        python -u PaperAiChat.py
    )
) else (
    echo [信息] 执行命令: python -u PaperAiChat.py
    python -u PaperAiChat.py
)

:: 检查运行结果
if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，错误码: %errorlevel%
) else (
    echo.
    echo [成功] 程序正常退出
)

echo.
echo ================================================
echo 会话已结束
echo ================================================
echo.

pause