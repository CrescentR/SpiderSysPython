import json, time
from datetime import datetime
import aio_pika

class Broadcaster:
    @classmethod
    def _envelope(cls, message_type: str, task_id: int, payload: dict) -> dict:
        return {
            "version": "1.0",
            "messageType": message_type,   # status | progress | result
            "taskId": task_id,
            "timestamp": int(time.time()),
            "dateTime": datetime.now().isoformat(),
            "payload": payload or {}
        }

    @classmethod
    async def _broadcast_data(cls, exchange, data: dict):
        message = aio_pika.Message(
            body=json.dumps(data, ensure_ascii=False).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers={
                "messageType": data.get("messageType", "unknown"),
                "taskId": str(data.get("taskId", "")),
                "timestamp": str(data.get("timestamp", 0)),
            }
        )
        # Fanout 忽略 routing_key，但参数必须给
        await exchange.publish(message, routing_key="")

    # --- 三种标准广播 ---

    @classmethod
    async def broadcast_status(cls, exchange, task_id: int, status: str, error: str | None = None):
        payload = {"status": status, "error": error}
        data = cls._envelope("status", task_id, payload)
        await cls._broadcast_data(exchange, data)

    @classmethod
    async def broadcast_progress(cls, exchange, task_id: int, current: int, total: int):
        payload = {"currentPage": current, "totalPages": total}
        data = cls._envelope("progress", task_id, payload)
        await cls._broadcast_data(exchange, data)

    @classmethod
    async def broadcast_result(cls, exchange, task_id: int, data: dict):
        """
        data 期望包含: keywords(list[str]) / url / title / source / (可选)dateTime
        兼容 keywords 为字符串的历史数据，自动转为数组。
        """
        kw = data.get("keywords", [])
        if isinstance(kw, str):
            # 兼容  "[电影,排名,TOP250]" 或 "电影,排名,TOP250"
            try:
                import json as _json
                parsed = _json.loads(kw)
                if isinstance(parsed, list):
                    kw = [str(x) for x in parsed]
                else:
                    kw = [s.strip() for s in kw.strip("[]").split(",") if s.strip()]
            except Exception:
                kw = [s.strip() for s in kw.strip("[]").split(",") if s.strip()]

        payload = {
            "taskId": task_id,
            "keywords": kw,
            "url": data.get("url", ""),
            "title": data.get("title", ""),
            "source": data.get("source", ""),
            "dateTime": data.get("dateTime") or datetime.now().isoformat(),
        }
        env = cls._envelope("result", task_id, payload)
        await cls._broadcast_data(exchange, env)
