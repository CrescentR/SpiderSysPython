import aio_pika
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',  # 🔥 优先英文
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Cache-Control': 'max-age=0',
    # 🔥 不要设置 Referer，避免被识别为中国区流量
}

AMQP_URL = "amqp://guest:guest@localhost:5672/"
EXCHANGE_CONFIG = {
    "name": "crawler.fanout.exchange",  # 交换机名称
    "type": aio_pika.ExchangeType.FANOUT,  # Fanout 类型：广播模式
    "durable": True  # 持久化
}
QUEUE_CONFIG = {
    "springBootData": {
        "name": "crawler.data.springBoot",  # SpringBoot 队列名
        "durable": True,  # 持久化队列
        "auto_delete": False  # 不自动删除
    },
    "front": {
        "name": "crawler.data.front",  # 前端队列名
        "durable": True,
        "auto_delete": False
    },
    "springBootStatus": {
        "name": "crawler.status.springBoot",  # SpringBoot 队列名
        "durable": True,  # 持久化队列
        "auto_delete": False  # 不自动删除
    },
}