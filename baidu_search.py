# -*- coding: utf-8 -*-
"""
百度搜索工具 - 解析百度搜索结果页
供 PaperAiChat 联网搜索使用
"""

import re
import json
from urllib.parse import quote

# 缓存搜索结果
_search_cache: dict[str, list[dict]] = {}


def baidu_search(query: str, count: int = 10) -> list[dict]:
    """执行百度搜索（通过解析搜索结果页）

    Args:
        query: 搜索关键词
        count: 返回结果数量（默认 10）

    Returns:
        搜索结果列表，每项包含 title / url / snippet / source
    """
    cache_key = f"baidu:{query}:{count}"
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    # 优先使用 requests
    try:
        import requests
        return _search_via_requests(query, count, cache_key)
    except ImportError:
        pass

    # 降级使用 urllib
    try:
        return _search_via_urllib(query, count, cache_key)
    except Exception as e:
        return [{"error": f"搜索请求失败: {e}"}]


def _search_via_requests(query: str, count: int, cache_key: str) -> list[dict]:
    """使用 requests 库执行搜索"""
    import requests
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    url = f"https://www.baidu.com/s?wd={quote(query)}&rn={min(count, 50)}"
    resp = requests.get(url, headers=headers, timeout=15)
    resp.encoding = "utf-8"
    html = resp.text

    results = _parse_baidu_results(html, count)
    if not results:
        results = [{"error": "百度搜索未返回结果，页面可能被反爬拦截"}]
    else:
        results = results[:count]

    _search_cache[cache_key] = results
    return results


def _search_via_urllib(query: str, count: int, cache_key: str) -> list[dict]:
    """使用 urllib 库执行搜索（降级方案）"""
    import urllib.request
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    url = f"https://www.baidu.com/s?wd={quote(query)}&rn={min(count, 50)}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    results = _parse_baidu_results(html, count)
    if not results:
        results = [{"error": "百度搜索未返回结果"}]
    else:
        results = results[:count]

    _search_cache[cache_key] = results
    return results


def _parse_baidu_results(html: str, count: int = 10) -> list[dict]:
    """解析百度搜索结果 HTML"""
    results = []
    seen_urls = set()

    # 策略1: 新版百度结果 - 查找 h3 > a 标签
    blocks = re.split(r'<div[^>]*class="[^"]*result[^"]*"', html)[1:]

    for block in blocks[:count * 2]:
        title_match = re.search(
            r'<h3[^>]*>.*?<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>',
            block, re.DOTALL,
        )
        if not title_match:
            continue

        url = title_match.group(1)
        title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()
        title = re.sub(r'\s+', ' ', title)

        if not title or not url or url in seen_urls:
            continue
        seen_urls.add(url)

        # 提取摘要
        snippet = ""
        snippet_match = re.search(
            r'<span[^>]*class="[^"]*content-right_[^"]*"[^>]*>(.*?)</span>',
            block, re.DOTALL,
        )
        if snippet_match:
            snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()

        if not snippet:
            abstract_match = re.search(
                r'<div[^>]*class="[^"]*c-abstract[^"]*"[^>]*>(.*?)</div>',
                block, re.DOTALL,
            )
            if abstract_match:
                snippet = re.sub(r'<[^>]+>', '', abstract_match.group(1)).strip()

        snippet = re.sub(r'\s+', ' ', snippet)

        results.append({
            "title": title,
            "url": url,
            "snippet": snippet[:300],
            "source": "baidu",
        })

        if len(results) >= count:
            break

    # 策略2: 如果上面没找到，直接提取所有 h3 > a（百度跳转链接）
    if not results:
        all_links = re.findall(
            r'<h3[^>]*>.*?<a[^>]*href="(https?://www\.baidu\.com/l\?[^"]+)"[^>]*>'
            r'(.*?)</a>',
            html, re.DOTALL,
        )
        for url, title_html in all_links[:count]:
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            title = re.sub(r'\s+', ' ', title)
            if title and title not in seen_urls:
                seen_urls.add(title)
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": "",
                    "source": "baidu",
                })

    return results


def format_search_results(results: list[dict]) -> str:
    """将搜索结果格式化为文本，供 AI 阅读"""
    if not results:
        return "【搜索结果为空】"

    if "error" in results[0]:
        return f"【搜索出错】{results[0]['error']}"

    lines = ["【以下是根据你的问题搜索到的网页信息】"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "无标题")
        snippet = r.get("snippet", "")
        url = r.get("url", "")
        lines.append(f"{i}. {title}")
        if snippet:
            lines.append(f"   摘要: {snippet}")
        lines.append(f"   来源: {url}")

    lines.append("【请基于以上搜索结果回答用户的问题，引用相关来源】")
    return "\n\n".join(lines)


# 工具描述（兼容 OpenAI Function Calling 格式）
baidu_search_tool = {
    "name": "baidu_search",
    "desc": "百度搜索",
    "schema": {
        "type": "function",
        "function": {
            "name": "baidu_search",
            "description": "使用百度搜索引擎搜索互联网，获取最新中文信息。适合查找新闻、资料、实时信息等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                    "count": {
                        "type": "integer",
                        "description": "返回结果数量（默认 5）",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    "fn": lambda query, count=5: baidu_search(query, count),
}
