import asyncio
import json
import time
import re
from typing import Dict, List
from urllib.parse import quote
from datetime import datetime
from .configs import AMQP_URL,DEFAULT_HEADERS, EXCHANGE_CONFIG, QUEUE_CONFIG
import aiohttp
import aio_pika
from bs4 import BeautifulSoup
from .broadcaster import Broadcaster


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
    return ""


def parse_links(html_content: str, engine: str = "bing") -> List[Dict[str, str]]:
    """从 HTML 中提取链接（同步解析，不做网络请求）"""
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []

    if engine == "baidu":
        for item in soup.find_all('div', class_=re.compile(r'result')):
            try:
                title_tag = (item.find('span', class_=re.compile(r'tts-title-content'))
                             or item.find('h3') or item.find('a'))
                link_tag = (item.find('a', class_=re.compile(r'c-link'))
                            or item.find('a', class_=re.compile(r'c-showurl|c-color-url'))
                            or item.find('a', class_=re.compile(r'block')))
                if not link_tag:
                    for a in item.find_all('a', href=True):
                        if 'baidu.com' not in a['href']:
                            link_tag = a
                            break
                if not link_tag:
                    link_tag = item.find('a', href=True)

                source = item.find('span', class_=re.compile('source')) or item.find('cite')

                if title_tag and link_tag and link_tag.get('href'):
                    results.append({
                        'title': title_tag.get_text(strip=True),
                        'href': link_tag['href'],
                        'source': source.get_text(strip=True) if source else '未知来源',
                        'engine': 'baidu'
                    })
            except Exception:
                continue

    elif engine == "bing":
        for item in soup.find_all('li', class_=re.compile('b_algo')):
            try:
                title_tag = item.find('h2')
                link_tag = title_tag.find('a') if title_tag else None
                source = item.find('div', class_='tptt')
                if title_tag and link_tag and link_tag.get('href'):
                    results.append({
                        'title': title_tag.get_text(strip=True),
                        'href': link_tag['href'],
                        'source': source.get_text(strip=True) if source else '未知来源',
                        'engine': 'bing'
                    })
            except Exception:
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
        concurrency = cmd.get("concurrency", 5)
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
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers=DEFAULT_HEADERS
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

    async def _crawl_one(
        self, session, url, page_no, task_id,
        exchange, sem, rate_limit, stop_event, engine, keywords, total_pages
    ):
        """爬取单个搜索结果页，并广播每条链接"""
        if stop_event.is_set():
            return
        async with sem:
            await rate_limit()
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        print(f"⚠️ 页面 {page_no} 返回状态码: {resp.status}")
                        await Broadcaster.broadcast_progress(exchange, task_id, current=page_no, total=total_pages)
                        return
                    html = await resp.text(errors="ignore")

                links = parse_links(html, engine)
                print(f"📄 页面 {page_no} 找到 {len(links)} 个链接")

                for link in links:
                    if stop_event.is_set():
                        break

                    data = {
                        "task_id": task_id,
                        "keywords": keywords,           # 数组
                        "url": link['href'],
                        "title": link['title'],
                        "source": link['source'],
                        "dateTime": datetime.now().isoformat(),
                    }
                    await Broadcaster.broadcast_result(exchange, task_id, data)

                # 页级进度：第 page_no / total_pages
                await Broadcaster.broadcast_progress(exchange, task_id, current=page_no, total=total_pages)

            except asyncio.TimeoutError:
                print(f"⏱️ 页面 {page_no} 超时")
            except Exception as e:
                print(f"❌ 页面 {page_no} 失败: {e}")
async def main():
    svc = CrawlerService(AMQP_URL)
    await svc.run()

if __name__ == "__main__":  # 注意：用 -m 运行时，这里会触发
    asyncio.run(main())