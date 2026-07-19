# -*- coding: utf-8 -*-
"""
PaperAiChat 自动更新脚本
用法: python Update.py
"""

import os
import sys
import re
import shutil
import urllib.request
import urllib.error
import json
import time

# ========== 配置 ==========
REPO_OWNER = "Colasensei"
REPO_NAME = "PaperAiChat"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

# 本地文件路径
LOCAL_MAIN = "PaperAiChat.py"
LOCAL_UI = "ui.py"
LOCAL_VER = "ver.txt"

# 远程下载基础 URL
BASE_DOWNLOAD_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/download"
# =========================


def get_local_version(file_path):
    """从本地文件第一行提取 VERSION = "x.y.z" """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
        match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', first_line)
        if match:
            return match.group(1)
        else:
            print(f"[错误] 无法从 {file_path} 第一行解析版本号")
            return None
    except Exception as e:
        print(f"[错误] 读取本地文件失败: {e}")
        return None


def get_latest_release_tag():
    """通过 GitHub API 获取最新的 release tag (例如 v8.3.0)"""
    headers = {"User-Agent": "PaperAiChat-UpdateScript/1.0"}
    try:
        req = urllib.request.Request(GITHUB_API_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            tag = data.get("tag_name")
            if tag:
                print(f"[信息] 最新 release 版本: {tag}")
                return tag
            else:
                print("[错误] API 响应中没有 tag_name")
                return None
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print("[错误] API 访问被拒绝，可能触发了限流。请稍后重试或使用代理。")
        elif e.code == 404:
            print("[错误] 未找到 Release 页面，请检查仓库名称是否正确。")
        else:
            print(f"[错误] HTTP {e.code}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"[错误] 网络连接失败: {e.reason}")
        print("  请检查网络连接或尝试使用代理。")
        return None
    except Exception as e:
        print(f"[错误] 获取 Release 信息失败: {e}")
        return None


def download_file(url, local_path, retries=3):
    """下载文件并保存到本地，支持重试"""
    for attempt in range(retries):
        try:
            print(f"  下载 {os.path.basename(local_path)} (尝试 {attempt + 1}/{retries})...")
            urllib.request.urlretrieve(url, local_path)
            return True
        except Exception as e:
            if attempt < retries - 1:
                wait = (attempt + 1) * 2
                print(f"  [重试] 下载失败，{wait}秒后重试: {e}")
                time.sleep(wait)
            else:
                print(f"[错误] 下载失败（已重试{retries}次）: {e}")
                return False
    return False


def backup_file(file_path):
    """备份文件为 file_path.bak"""
    if os.path.exists(file_path):
        backup_path = file_path + ".bak"
        try:
            shutil.copy2(file_path, backup_path)
            print(f"  已备份: {os.path.basename(backup_path)}")
        except Exception as e:
            print(f"[警告] 备份失败: {e}")


def update_file(tag, remote_filename, local_filename):
    """根据 release tag 下载并替换指定文件"""
    url = f"{BASE_DOWNLOAD_URL}/{tag}/{remote_filename}"
    print(f"正在更新 {local_filename}...")
    backup_file(local_filename)
    if download_file(url, local_filename):
        print(f"  {local_filename} ✓ 更新成功")
        return True
    else:
        print(f"  {local_filename} ✗ 更新失败")
        return False


def update_ver_file(version):
    """更新 ver.txt 文件"""
    try:
        with open(LOCAL_VER, 'w', encoding='utf-8') as f:
            f.write(f"VERSION = {version}\n")
        print(f"  {LOCAL_VER} ✓ 版本号已更新")
    except Exception as e:
        print(f"[警告] 更新 ver.txt 失败: {e}")


def compare_versions(local_ver, remote_tag):
    """比较本地版本和远程 tag（远程 tag 通常带 v 前缀，如 v8.3.0）"""
    if remote_tag.startswith('v'):
        remote_ver = remote_tag[1:]
    else:
        remote_ver = remote_tag

    def to_tuple(v):
        try:
            return tuple(map(int, v.split('.')))
        except ValueError:
            return (0, 0, 0)
    return to_tuple(remote_ver) > to_tuple(local_ver)


def main():
    print("=" * 60)
    print("  PaperAiChat 自动更新工具 (GitHub Release)")
    print("=" * 60)
    print()

    # 1. 检查本地主程序文件
    if not os.path.exists(LOCAL_MAIN):
        print(f"[错误] 未找到 {LOCAL_MAIN}，请确认脚本放置在项目根目录下。")
        input("\n按 Enter 键退出...")
        sys.exit(1)

    # 2. 获取本地版本
    local_ver = get_local_version(LOCAL_MAIN)
    if local_ver is None:
        input("\n按 Enter 键退出...")
        sys.exit(1)
    print(f"本地版本: v{local_ver}")

    # 3. 获取远程最新 release tag
    print("正在检查更新...")
    remote_tag = get_latest_release_tag()
    if remote_tag is None:
        input("\n按 Enter 键退出...")
        sys.exit(1)

    # 4. 比较版本
    if not compare_versions(local_ver, remote_tag):
        print(f"\n✓ 当前已是最新版本 (v{local_ver})，无需更新。")
        input("\n按 Enter 键退出...")
        return

    print(f"\n发现新版本 {remote_tag}（当前: v{local_ver}）")
    print("开始更新...")
    print()

    # 5. 更新 PaperAiChat.py
    success_main = update_file(remote_tag, "PaperAiChat.py", LOCAL_MAIN)

    # 6. 更新 ui.py（如果本地存在）
    success_ui = True
    if os.path.exists(LOCAL_UI):
        success_ui = update_file(remote_tag, "ui.py", LOCAL_UI)
    else:
        print("[信息] 本地没有 ui.py，跳过更新")

    # 7. 更新版本号
    update_ver_file(remote_tag.lstrip('v'))

    # 8. 汇总结果
    print()
    print("=" * 60)
    if success_main and success_ui:
        print("✓ 更新完成！程序已升级到最新版本。")
        print(f"  如有问题，可恢复 .bak 备份文件。")
    else:
        print("⚠ 更新过程中出现错误：")
        if not success_main:
            print(f"  - {LOCAL_MAIN} 更新失败")
        if not success_ui:
            print(f"  - {LOCAL_UI} 更新失败")
        print("  请检查网络连接，或手动恢复 .bak 备份文件。")
    print("=" * 60)

    input("\n按 Enter 键退出...")


if __name__ == "__main__":
    main()