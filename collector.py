"""采集官方 HTML 页面标题和动态 JSON 数据。"""

import hashlib
import json
import re
from html import unescape
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://bis.dsat.gov.mo:37812"
MACAU_TIME = timezone(timedelta(hours=8))


def make_token(params):
    """保留参数插入顺序，复现官方前端的 MD5 + 澳门分钟时间格式。"""
    raw = "&".join(f"{key}={value}" for key, value in params.items())
    digest = hashlib.md5(raw.encode()).hexdigest()
    minute = datetime.now(MACAU_TIME).strftime("%Y%m%d%H%M")
    return (
        digest[:4]
        + minute[:4]
        + digest[4:12]
        + minute[4:8]
        + digest[12:24]
        + minute[8:]
        + digest[24:]
    )


def request_data(path, params):
    request = Request(
        BASE_URL + path,
        data=urlencode(params).encode(),
        headers={"token": make_token(params), "User-Agent": "Mozilla/5.0"},
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def fetch(path, action, direction="0"):
    return request_data(
        "/macauweb/" + path,
        dict(action=action, routeName="102", dir=direction, lang="zh-tw", device="web"),
    )


def extract_title(html):
    """针对官方页面的 title 标签提取文本，而非通用 HTML 解析器。"""
    match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    if not match or not match.group(1).strip():
        raise ValueError("官方 HTML 缺少页面标题")
    return unescape(match.group(1)).strip()


def fetch_page_title():
    request = Request(
        BASE_URL + "/macauweb/index.html", headers={"User-Agent": "Mozilla/5.0"}
    )
    with urlopen(request, timeout=15) as response:
        html = response.read().decode("utf-8")
    return extract_title(html)
