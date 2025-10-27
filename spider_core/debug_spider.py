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
                      "Chrome/124.0 Safari/537.36",
        "Cookie":"MUID=0F68497DB17E6C99303E5FFDB0A56DE0; MUIDB=0F68497DB17E6C99303E5FFDB0A56DE0; _EDGE_V=1; SRCHD=AF=QBRE; SRCHUID=V=2&GUID=36510794B617405EB0246E5F50D19C20&dmnchg=1; _UR=QS=0&TQS=0&Pn=0; BFBUSR=BFBHP=0; _SS=SID=2D4B70D1C8DA6BC2146F6650C9086A92&R=200&RB=0&GB=0&RG=200&RP=200&h5comp=3; _clck=s66mwf%5E2%5Eg0c%5E0%5E2116; _Rwho=u=d&ts=2025-10-24; _FP=hta=on; ENSEARCH=BENVER=0; _EDGE_S=SID=2D4B70D1C8DA6BC2146F6650C9086A92&mkt=en-US; SNRHOP=I=&TS=; _HPVN=CS=eyJQbiI6eyJDbiI6MTUsIlN0IjowLCJRcyI6MCwiUHJvZCI6IlAifSwiU2MiOnsiQ24iOjE1LCJTdCI6MCwiUXMiOjAsIlByb2QiOiJIIn0sIlF6Ijp7IkNuIjoxNSwiU3QiOjAsIlFzIjowLCJQcm9kIjoiVCJ9LCJBcCI6dHJ1ZSwiTXV0ZSI6dHJ1ZSwiTGFkIjoiMjAyNS0xMC0yN1QwMDowMDowMFoiLCJJb3RkIjowLCJHd2IiOjAsIlRucyI6MCwiRGZ0IjpudWxsLCJNdnMiOjAsIkZsdCI6MCwiSW1wIjo3NCwiVG9ibiI6MH0=; ipv6=hit=1761548489117&t=4; USRLOC=HS=1&ELOC=LAT=34.70549392700195|LON=113.62060546875|N=%E4%BA%8C%E4%B8%83%E5%8C%BA%EF%BC%8C%E6%B2%B3%E5%8D%97%E7%9C%81|ELT=4|; BFPRResults=FirstPageUrls=B23995185ED127ED93A069920217BBB7%2CC1AB7BFBEFE0933FDB5E4B20EC68DF05%2CD8F94870551E438FDCA300F8FCE06DAE%2CF9307C9524A3D21EA96141528C274CA0%2C1A72A6610BB75B336ACBF02AC6A0756D%2CBB2533E5792B70CA1505420BA054C507%2C5CCA0E070585FB756B1CB7B60A0B8FCB%2C4296A6898974E60FD7E550C512E06FCC%2CB98152FE10FB6F9C45A0F4F8CA1E8C50%2C7CE9553067DCC0E374D706BF3A42FBC2&FPIG=6117330B9C6F48EEB89570EFEB9C891A; _RwBf=r=0&ilt=205&ihpd=0&ispd=2&rc=200&rb=0&rg=200&pc=200&mtu=0&rbb=0&clo=0&v=2&l=2025-10-27T07:00:00.0000000Z&lft=0001-01-01T00:00:00.0000000&aof=0&ard=0001-01-01T00:00:00.0000000&rwdbt=0&rwflt=0&rwaul2=0&g=&o=2&p=&c=&t=0&s=0001-01-01T00:00:00.0000000+00:00&ts=2025-10-27T09:16:57.8486299+00:00&rwred=0&wls=&wlb=&wle=&ccp=&cpt=&lka=0&lkt=0&aad=0&TH=&cid=0&gb=; dsc=order=BingPages; SRCHUSR=DOB=20251009&DS=1; SRCHHPGUSR=SRCHLANG=zh-Hans&IG=A04D56035D1647AE888C8787CDC9C5A2&PREFCOL=0&BRW=NOTP&BRH=M&CW=686&CH=906&SCW=1164&SCH=1435&DPR=1.0&UTC=480&PV=19.0.0&B=0&EXLTT=31&AV=14&ADV=14&RB=0&MB=0&PRVCW=686&PRVCH=906&HV=1761556618&HVE=CfDJ8BJecyNyfxpMtsfDoM3OqQsDwshFO0Jz_VQG_3ZfqIk6BPUAB-uBBiFR9GcQ0uohm0AhmVhilRK9t0zW9UqftKAoc5D5qEami5avJ0Lv1TY4Q8aGzXbCEH_CSizOKo7jvMkqEwrT2Zq9qQqmh5EkPR7R5UITwI0i8iOzQnrR0BPHFCsBbrt7ucIUClrUD6x-jA&BZA=0"
    }

    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    html_content = resp.text
    print(html_content[:1000])
    soup = BeautifulSoup(html_content, "html.parser")
    print(str(soup)[:1000])
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
                print(f"标题：{title_tag}, 链接：{link_tag}, 来源：{source}")
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
    keywords = ["科技新闻"]
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
