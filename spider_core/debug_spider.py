import asyncio
from playwright.async_api import async_playwright
from urllib.parse import quote_plus, urlencode
import random
import time

BING_BASE = "https://www.bing.com/search"

# 可选：想要彻底不出知乎，直接加上负词
EXCLUDE_SITES = ["zhihu.com", "baidu.com", "tieba.baidu.com"]

# # 可选：只想要壁纸站，打开这个白名单
# WHITELIST_SITES = [
#     "wallhaven.cc", "unsplash.com", "pexels.com", "pixabay.com",
#     "alpha.wallhaven.cc", "deviantart.com", "artstation.com",
#     "simpledesktops.com", "wallpaperflare.com", "wallpaperhub.app",
# ]

def build_query(keywords, exclude_sites=None, whitelist_sites=None):
    """
    keywords: str 或 list[str]
    """
    if isinstance(keywords, (list, tuple)):
        q = " ".join(keywords)
    else:
        q = str(keywords)

    # 负词排除域
    if exclude_sites:
        q += " " + " ".join([f"-site:{d}" for d in exclude_sites])

    # 只要白名单（可选）
    if whitelist_sites:
        q += " " + " OR ".join([f"site:{d}" for d in whitelist_sites])

    return q.strip()


async def fetch_bing_results(keywords, page_no: int, *, mkt="en-US", cc="US",
                             use_english_results=True, count=10, timeout_ms=15000,
                             exclude_sites=None):  # 新增参数
    """
    增加 exclude_sites 参数，在解析结果时手动过滤
    """
    q = build_query(keywords, exclude_sites=exclude_sites, whitelist_sites=None)
    params = {
        "q": q,
        "count": count,
        "first": page_no * count + 1,
        "form": "PERE",
        "mkt": mkt,
        "cc": cc,
    }
    if use_english_results:
        params["ensearch"] = "1"

    url = f"{BING_BASE}?{urlencode(params)}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="en-US" if use_english_results else "zh-CN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9" if use_english_results else "zh-CN,zh;q=0.9",
            },
        )

        page = await context.new_page()
        page.set_default_timeout(timeout_ms)

        await page.goto(url)
        await page.wait_for_selector("li.b_algo h2 a", timeout=timeout_ms)

        nodes = await page.query_selector_all("li.b_algo h2 a")

        results = []
        seen = set()

        for a in nodes:
            try:
                title = (await a.inner_text()).strip()
                href = await a.get_attribute("href")
                if not href:
                    continue

                # 🔥 手动过滤排除站点
                if exclude_sites:
                    skip = False
                    for domain in exclude_sites:
                        if domain in href:
                            skip = True
                            break
                    if skip:
                        continue

                key = (title, href)
                if key in seen:
                    continue
                seen.add(key)

                results.append({"title": title, "href": href})
            except Exception:
                continue

        await context.close()
        await browser.close()
        return results


async def crawl_pages(keywords, total_pages: int, exclude_sites=None, **kwargs):
    """传递 exclude_sites 到每个请求"""
    tasks = []
    for page_no in range(total_pages):
        await asyncio.sleep(random.uniform(0.2, 0.6))
        tasks.append(fetch_bing_results(
            keywords, page_no,
            exclude_sites=exclude_sites,  # 传递参数
            **kwargs
        ))

    pages = await asyncio.gather(*tasks, return_exceptions=True)

    merged, seen = [], set()
    for page in pages:
        if isinstance(page, Exception):
            continue
        for item in page:
            key = item["href"]
            if key not in seen:
                seen.add(key)
                merged.append(item)
    return merged


async def start_crawl_task(keywords, total_pages: int, exclude_sites=None, **kwargs):
    """传递 exclude_sites"""
    results = await crawl_pages(keywords, total_pages, exclude_sites=exclude_sites, **kwargs)
    print(f"\n✅ 共获取 {len(results)} 个有效结果\n")
    for i, link in enumerate(results, 1):
        print(f"{i}. Title: {link['title']}")
        print(f"   Link: {link['href']}\n")


async def main():
    # 方案 A：英文关键词 + 手动过滤知乎
    keywords = ["4K wallpaper"]
    await start_crawl_task(
        keywords,
        total_pages=3,  # 先测试 3 页
        exclude_sites=EXCLUDE_SITES,  # 🔥 传递排除列表
        mkt="en-US",
        cc="US",
        use_english_results=True,
        count=10
    )


if __name__ == "__main__":
    asyncio.run(main())