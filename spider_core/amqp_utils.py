import json
import aio_pika
from .configs import AMQP_URL, EXCHANGE_CONFIG  # 依据你的项目结构调整导入

async def publish_result(task_id, payload: dict, message_type: str = "message"):
    """
    统一发布爬虫结果到结果交换机，确保交换机/路由键与 SSE 一致，并统一字符串 task_id。
    """
    conn = await aio_pika.connect_robust(AMQP_URL)
    try:
        ch = await conn.channel()
        exchange_type = getattr(
            aio_pika.ExchangeType,
            EXCHANGE_CONFIG.get("type", "fanout").upper()
        )
        ex = await ch.declare_exchange(
            EXCHANGE_CONFIG["name"],
            exchange_type,
            durable=True
        )
        body = {
            "task_id": str(task_id),
            "messageType": message_type,
            **payload
        }
        await ex.publish(
            aio_pika.Message(
                body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=EXCHANGE_CONFIG.get("routing_key", "")
        )
    finally:
        await conn.close()