import asyncio
import json
import time
import re
import os
from typing import Dict, List
from urllib.parse import quote
from datetime import datetime
from .configs import AMQP_URL,DEFAULT_HEADERS, EXCHANGE_CONFIG, QUEUE_CONFIG
import aiohttp
import aio_pika
from bs4 import BeautifulSoup
from .broadcaster import Broadcaster
import random
os.environ["PYDEVD_USE_FRAME_EVAL"] = "NO"
def build_search_url(keywords: List[str], page_no: int, engine: str = "bing") -> str:
    """构建搜索引擎 URL"""
    if not keywords:
        return ""
    encoded_keywords = [quote(kw, safe='', encoding='utf-8') for kw in keywords]
    query = '+'.join(encoded_keywords)

    if engine == "baidu":
        pn = (page_no - 1) * 10 if page_no > 1 else 0
        return f"https://www.baidu.com/s?ie=utf-8&f=8&rsv_bp=1&rsv_idx=1&tn=baidu&wd={query}&pn={pn}"
    elif engine == "bing":
        first = (page_no - 1) * 10 + 1 if page_no > 1 else 1
        return f"https://www.cn.bing.com/search?q={query}&first={first}"
    return ""


def parse_links(html_content: str, engine: str = "bing") -> List[Dict[str, str]]:
    """从 HTML 中提取链接（同步解析，不做网络请求）"""
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []

    if engine == "bing":
        items = (
                soup.find_all('li', class_='b_algo') or  # 标准结果
                soup.find_all('div', class_='b_algo') or  # 备选
                soup.select('.b_algo')  # CSS 选择器
        )
        for item in items:
            try:
                title_tag = item.find('h2')
                if not title_tag:
                    continue
                link_tag = title_tag.find('a')
                if not link_tag or not link_tag.get('href'):
                    continue
                source = item.find('cite')  # ⚠️ cite 标签通常包含真实域名

                if title_tag and link_tag:
                    href = link_tag.get('href', '')

                    # 🔥 方法1：从 cite 标签获取真实链接
                    real_url = source.get_text(strip=True) if source else href

                    # 🔥 方法2：如果 href 包含真实 URL，尝试提取
                    if 'bing.com/ck/' in href or not href.startswith('http'):
                        # 尝试从其他属性获取
                        real_url = link_tag.get('data-url') or link_tag.get('href')
                    else:
                        real_url = href

                    results.append({
                        'title': title_tag.get_text(strip=True),
                        'href': real_url,
                        'source': source.get_text(strip=True) if source else '未知来源',
                        'engine': 'bing'
                    })
            except Exception as e:
                print(f"解析失败: {e}")
                continue
    return results
class CrawlerService:
    """
    爬虫服务 - 支持多端消费（Fanout 广播）
    """
    def __init__(self, amqp_url: str):
        self.amqp_url = amqp_url
        self.stop_flags: Dict[str, asyncio.Event] = {}
        self.connection = None
        self.channel = None
        self.exchange = None  # Fanout 交换机
        self.cmd_queue = None
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0'
        ]

    def get_headers(self):
        """获取随机请求头"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
            'DNT': '1'
        }
    async def initialize(self):
        """初始化 RabbitMQ：Fanout Exchange + 业务队列；Topic Exchange + 命令队列"""
        self.connection = await aio_pika.connect(url=self.amqp_url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=50)

        # 广播 Exchange
        self.exchange = await self.channel.declare_exchange(
            EXCHANGE_CONFIG["name"],
            EXCHANGE_CONFIG["type"],  # fanout
            durable=EXCHANGE_CONFIG["durable"]
        )

        # 绑定所有消费队列
        for queue_key, config in QUEUE_CONFIG.items():
            queue = await self.channel.declare_queue(
                config["name"],
                durable=config["durable"],
                auto_delete=config["auto_delete"]
            )
            await queue.bind(self.exchange, routing_key="")
            print(f"✅ 队列已创建并绑定: {config['name']} ({queue_key})")

        # 命令通道（Topic）
        cmd_exchange = await self.channel.declare_exchange(
            "crawler.command.exchange",
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        self.cmd_queue = await self.channel.declare_queue(
            "crawler.command.queue",
            durable=True,
        )
        await self.cmd_queue.bind(cmd_exchange, routing_key="cmd.*")
        print("✅ 命令队列已创建: crawler.command.queue")

    async def run(self):
        """运行主循环：监听命令队列"""
        await self.initialize()

        print("🚀 爬虫服务已启动（多端消费模式）")
        print(f"📡 广播交换机: {EXCHANGE_CONFIG['name']}")
        print(f"📮 消费队列: {', '.join([c['name'] for c in QUEUE_CONFIG.values()])}\n")

        async with self.cmd_queue.iterator() as queue_iter:
            async for msg in queue_iter:
                async with msg.process():
                    try:
                        cmd = json.loads(msg.body)
                        task_id = cmd["task_id"]
                        if cmd["cmd"] == "start":
                            print(f"📝 收到启动命令: {task_id}")
                            self.stop_flags[task_id] = asyncio.Event()
                            asyncio.create_task(
                                self._start_job(self.exchange, cmd, self.stop_flags[task_id])
                            )
                        elif cmd["cmd"] == "stop":
                            print(f"🛑 收到停止命令: {task_id}")
                            if task_id in self.stop_flags:
                                self.stop_flags[task_id].set()
                    except Exception as e:
                        print(f"❌ 处理命令失败: {e}")

    async def _start_job(self, exchange, cmd, stop_event: asyncio.Event):
        """启动爬取任务"""
        task_id = cmd["task_id"]
        keywords = cmd["keywords"]
        total_pages = cmd["pageSize"]
        concurrency = cmd.get("concurrency", 1)
        rate = cmd.get("rateLimitPerSec", 2)
        engine = cmd.get("engine", "bing")

        print(f"🎯 开始任务 {task_id}: 关键词={keywords}, 页数={total_pages}")

        sem = asyncio.Semaphore(concurrency)
        last_ts = [time.time()]

        async def rate_limit():
            delta = time.time() - last_ts[0]
            if delta < 1.0 / rate:
                await asyncio.sleep(1.0 / rate - delta)
            last_ts[0] = time.time()

        try:
            connector = aiohttp.TCPConnector(
                ssl=False,  # 或者使用 ssl=ssl.create_default_context()
                limit=10,  # 限制并发连接数
                ttl_dns_cache=300
            )
            async with aiohttp.ClientSession(
                    connector=connector,
                    timeout=aiohttp.ClientTimeout(
                        total=30,  # 增加总超时
                        connect=10,  # 连接超时
                        sock_read=20  # 读取超时
                    ),
                    headers=self.get_headers(),
                    cookie_jar=aiohttp.CookieJar()
            ) as session:
                # 开始状态 + 初始进度
                await Broadcaster.broadcast_status(exchange, task_id, "started")
                await Broadcaster.broadcast_progress(exchange, task_id, current=0, total=total_pages)

                tasks = []
                for page_no in range(1, total_pages + 1):
                    if stop_event.is_set():
                        break
                    url = build_search_url(keywords, page_no, engine=engine)

                    task = asyncio.create_task(
                        self._crawl_one(
                            session=session,
                            url=url,
                            page_no=page_no,
                            task_id=task_id,
                            exchange=exchange,
                            sem=sem,
                            rate_limit=rate_limit,
                            stop_event=stop_event,
                            engine=engine,
                            keywords=keywords,
                            total_pages=total_pages
                        )
                    )
                    tasks.append(task)

                await asyncio.gather(*tasks, return_exceptions=True)

                if not stop_event.is_set():
                    await Broadcaster.broadcast_status(exchange, task_id, "done")
                    print(f"✅ 任务完成: {task_id}")
                else:
                    await Broadcaster.broadcast_status(exchange, task_id, "stopped")
                    print(f"⏹️ 任务已停止: {task_id}")

        except Exception as e:
            print(f"❌ 任务失败 {task_id}: {e}")
            await Broadcaster.broadcast_status(exchange, task_id, "error", str(e))
        finally:
            if task_id in self.stop_flags:
                del self.stop_flags[task_id]

    async def _crawl_one(self, session, url, page_no, task_id,
                         exchange, sem, rate_limit, stop_event, engine, keywords, total_pages):
        """爬取单个搜索结果页，并广播每条链接"""
        if stop_event.is_set():
            return

        async with sem:
            await rate_limit()

            # 🔥 添加重试机制
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            print(f"⚠️ 页面 {page_no} 返回状态码: {resp.status}")
                            await Broadcaster.broadcast_progress(exchange, task_id, current=page_no, total=total_pages)
                            return
                        html = await resp.text(errors="ignore")

                        # 🔥 保存 HTML 用于调试
                        debug_file = f"debug_bing_page{page_no}_task{task_id}.html"
                        with open(debug_file, 'w', encoding='utf-8') as f:
                            f.write(html)
                        print(f"🔍 已保存调试文件: {debug_file}")

                    links = parse_links(html, engine)
                    print(f"📄 页面 {page_no} 找到 {len(links)} 个链接")
                    print(f"🔗 链接详情: {links}")  # 🔥 确保打印

                    for link in links:
                        if stop_event.is_set():
                            break
                        data = {
                            "task_id": task_id,
                            "keywords": keywords,
                            "url": link['href'],
                            "title": link['title'],
                            "source": link['source'],
                            "dateTime": datetime.now().isoformat(),
                        }
                        await Broadcaster.broadcast_result(exchange, task_id, data)

                    await Broadcaster.broadcast_progress(exchange, task_id, current=page_no, total=total_pages)
                    return  # 🔥 成功后直接返回

                except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 指数退避: 1s, 2s, 4s
                        print(f"⚠️ 页面 {page_no} 失败 (尝试 {attempt + 1}/{max_retries}): {e}, {wait_time}秒后重试...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"❌ 页面 {page_no} 最终失败: {e}")
                        return
                except Exception as e:
                    print(f"❌ 页面 {page_no} 未知错误: {e}")
                    return
async def main():
    svc = CrawlerService(AMQP_URL)
    await svc.run()

if __name__ == "__main__":  # 注意：用 -m 运行时，这里会触发
    asyncio.run(main())