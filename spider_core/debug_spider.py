import re
from typing import Dict, List, Iterable, Callable, Optional
from urllib.parse import quote
from bs4 import BeautifulSoup
import requests


def build_search_url(keywords: List[str], page_no: int, engine: str = "bing") -> str:
    """构建搜索引擎 URL"""
    if not keywords:
        return ""

    encoded_keywords = [quote(kw) for kw in keywords]
    query = '+'.join(encoded_keywords)

    if engine == "baidu":
        pn = (page_no - 1) * 10 if page_no > 1 else 0
        return f"https://www.baidu.com/s?ie=utf-8&f=8&rsv_bp=1&rsv_idx=1&tn=baidu&wd={query}&pn={pn}"
    elif engine == "bing":
        first = (page_no - 1) * 10 + 1 if page_no > 1 else 1
        return f"https://cn.bing.com/search?q={query}&first={first}"
    else:
        return ""


def iter_parse_links(
    url: str,
    engine: str = "bing",
    on_item: Optional[Callable[[Dict[str, str]], None]] = None,
    timeout: int = 15,
    headers: Optional[Dict[str, str]] = None,
) -> Iterable[Dict[str, str]]:
    """
    从搜索结果页“边解析边产出”链接。
    - 解析到一条就 yield 一条（或调用 on_item）
    - 与原 parse_links 等价，但不再一次性返回整表
    """
    headers = headers or {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0 Safari/537.36"
    }

    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    html_content = resp.text
    soup = BeautifulSoup(html_content, "html.parser")

    if engine == "baidu":
        # 百度搜索结果容器经常变，这里保留你原来的多选择器兜底策略
        for item in soup.find_all('div', class_=re.compile(r'result')):
            try:
                title_tag = (item.find('span', class_=re.compile(r'tts-title-content'))
                             or item.find('h3')
                             or item.find('a'))

                link_tag = (item.find('a', class_=re.compile(r'c-link'))
                            or item.find('a', class_=re.compile(r'c-showurl|c-color-url'))
                            or item.find('a', class_=re.compile(r'block')))

                if not link_tag:
                    # 兜底：找第一个非 baidu 域的外链
                    for a in item.find_all('a', href=True):
                        if 'baidu.com' not in a['href']:
                            link_tag = a
                            break
                if not link_tag:
                    link_tag = item.find('a', href=True)

                source = item.find('span', class_=re.compile('source')) or item.find('cite')

                if title_tag and link_tag and link_tag.get('href'):
                    data = {
                        'title': title_tag.get_text(strip=True),
                        'href': link_tag['href'],
                        'source': source.get_text(strip=True) if source else '未知来源',
                        'engine': 'baidu'
                    }
                    if on_item:
                        on_item(data)  # 立刻处理一条
                    yield data       # 立刻产出一条
            except Exception as e:
                print(f"解析百度结果项时出错: {e}")
                continue

    elif engine == "bing":
        # Bing 常见结构：li.b_algo > h2 > a
        for item in soup.find_all('li', class_=re.compile(r'\bb_algo\b')):
            try:
                title_tag = item.find('h2')
                link_tag = title_tag.find('a') if title_tag else None
                source = item.find('div', class_='tptt')  # 有些页面没有

                if title_tag and link_tag and link_tag.get('href'):
                    data = {
                        'title': title_tag.get_text(strip=True),
                        'href': link_tag['href'],
                        'source': source.get_text(strip=True) if source else '未知来源',
                        'engine': 'bing'
                    }
                    if on_item:
                        on_item(data)
                    yield data
            except Exception as e:
                print(f"解析Bing结果项时出错: {e}")
                continue


if __name__ == "__main__":
    keywords = ["电影", "排名", "TOP250"]
    page_no = 1
    engine = "bing"

    search_url = build_search_url(keywords, page_no, engine)
    print(f"搜索 URL: {search_url}")

    # 用法 1：生成器——谁先解析到就先拿到，边拿边用
    for result in iter_parse_links(search_url, engine):
        print(f"标题: {result['title']}")
        print(f"链接: {result['href']}")
        print(f"来源: {result['source']}")
        print(f"引擎: {result['engine']}")
        print("-" * 40)

