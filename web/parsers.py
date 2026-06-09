"""HTML parsing + structured response builders."""

import html
import re
from typing import Any


def html_to_text(html_content: str) -> str:
    """Strip HTML tags and clean up text content."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(div|h[1-6]|li|tr|pre|blockquote)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<a\s[^>]*href="([^"]+)"[^>]*>', r'[\1] ', text, flags=re.IGNORECASE)
    text = re.sub(r'<img\s[^>]*alt="([^"]*)"[^>]*>', r' \1 ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\[https?://[^\]]+\]\s*', '', text)
    lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 3]
    seen = set()
    unique = []
    for l in lines:
        key = l[:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(l)
    return '\n'.join(unique)


def json_ok(tool: str, data: Any, meta: dict = None) -> dict:
    result = {"success": True, "tool": tool, "data": data}
    if meta:
        result["meta"] = meta
    return result


def json_error(tool: str, error: str, detail: str = "") -> dict:
    result = {"success": False, "tool": tool, "error": error}
    if detail:
        result["detail"] = detail
    return result
