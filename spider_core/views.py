import json
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import aio_pika
import json as _json
import re
from spider_core.configs import AMQP_URL, QUEUE_CONFIG, EXCHANGE_CONFIG

_crawler_connection = None
_crawler_channel = None
_cmd_exchange = None

def normalize_keywords(keywords):
    """
    兼容三种输入：
    - 已是 list[str]
    - 是 JSON 字符串：'["电影","排名","TOP250"]'
    - 是普通字符串："[电影,排名,TOP250]" / "电影, 排名, TOP250"
    """
    if isinstance(keywords, list):
        return [str(x).strip() for x in keywords if str(x).strip()]

    if isinstance(keywords, str):
        s = keywords.strip()
        # 1) 先尝试当做 JSON 列表
        try:
            parsed = _json.loads(s)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
        # 2) 回退：去掉中括号，按中文/英文逗号或空白切分
        s = s.strip("[]")
        parts = re.split(r"[，,\s]+", s)
        return [p for p in (x.strip() for x in parts) if p]

    return []
async def get_rabbitmq_connection():
    """获取或创建 RabbitMQ 连接"""
    global _crawler_connection, _crawler_channel, _cmd_exchange

    if _crawler_connection is None or _crawler_connection.is_closed:
        _crawler_connection = await aio_pika.connect_robust(AMQP_URL)
        _crawler_channel = await _crawler_connection.channel()
        _cmd_exchange = await _crawler_channel.declare_exchange(
            "crawler.command.exchange",
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
    return _crawler_connection, _crawler_channel, _cmd_exchange


@csrf_exempt
@require_http_methods(["POST"])
async def start_crawl(request):
    """启动爬取任务"""
    try:
        body = json.loads(request.body)
        task_id = body.get("task_id")
        keywords = normalize_keywords(body.get('keywords', []))
        page_size = body.get('pageSize', 1)
        engine = body.get('engine', 'bing')
        concurrency = body.get('concurrency', 5)
        rate_limit = body.get('rateLimitPerSec', 2.0)

        if not keywords:
            return JsonResponse({'error': 'keywords 参数不能为空'}, status=400)

        cmd = {
            "cmd": "start",
            "task_id": task_id,
            "keywords": keywords,
            "pageSize": page_size,
            "engine": engine,
            "concurrency": concurrency,
            "rateLimitPerSec": rate_limit
        }

        _, _, cmd_exchange = await get_rabbitmq_connection()
        await cmd_exchange.publish(
            aio_pika.Message(
                body=json.dumps(cmd, ensure_ascii=False).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key="cmd.start"
        )

        return JsonResponse({
            "task_id": task_id,
            "status": "queued",
            "keywords": keywords,
            "consumers": list(QUEUE_CONFIG.keys()),
            "message": "数据将同时发送到所有消费者"
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的 JSON 格式'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
async def stop_crawl(request, task_id):
    """停止爬取任务"""
    try:
        cmd = {"cmd": "stop", "task_id": task_id}
        _, _, cmd_exchange = await get_rabbitmq_connection()
        await cmd_exchange.publish(
            aio_pika.Message(
                body=json.dumps(cmd).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key="cmd.stop"
        )
        return JsonResponse({"task_id": task_id, "status": "任务已停止"})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


async def stream_results(request, task_id):
    """
    SSE: 前端消费 Envelope。支持 '?debug=1' 调试。
    - 过滤使用 envelope.taskId（兼容老的 task_id）
    - 事件名使用 envelope.messageType
    """
    debug_mode = request.GET.get("debug") == "1"

    async def event_generator():
        conn = None
        try:
            conn = await aio_pika.connect_robust(AMQP_URL)
            channel = await conn.channel()

            exchange_type = getattr(
                aio_pika.ExchangeType,
                EXCHANGE_CONFIG.get("type", "fanout").upper()
            )
            result_exchange = await channel.declare_exchange(
                EXCHANGE_CONFIG["name"],
                exchange_type,
                durable=True
            )

            queue = await channel.declare_queue(
                QUEUE_CONFIG["front"]["name"],
                durable=True
            )
            routing_key = EXCHANGE_CONFIG.get("routing_key", "")
            await queue.bind(result_exchange, routing_key=routing_key)

            yield f"data: {json.dumps({'type': 'connected', 'task_id': task_id})}\n\n"

            wanted_task_id = str(task_id)

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            data = json.loads(message.body)
                        except Exception as e:
                            if debug_mode:
                                yield "event: debug\n"
                                yield f"data: {json.dumps({'reason':'parse_error','error':str(e)}, ensure_ascii=False)}\n\n"
                            continue

                        # Envelope 过滤：优先 taskId，兼容老的 task_id
                        got_tid = data.get("taskId", data.get("task_id"))
                        if not debug_mode and str(got_tid) != wanted_task_id:
                            continue
                        if debug_mode and str(got_tid) != wanted_task_id:
                            yield "event: debug\n"
                            yield f"data: {json.dumps({'reason':'task_id_mismatch','wanted':wanted_task_id,'got':got_tid}, ensure_ascii=False)}\n\n"

                        event_type = data.get("messageType", "message")
                        yield f"event: {event_type}\n"
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

                        if event_type == "status":
                            payload = (data.get("payload") or {})
                            st = payload.get("status") or data.get("status")
                            if st in ["done", "error", "stopped"]:
                                yield "event: end\n"
                                yield f"data: {json.dumps({'status': st})}\n\n"
                                break
        except Exception as e:
            yield "event: error\n"
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if conn:
                await conn.close()

    response = StreamingHttpResponse(event_generator(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@require_http_methods(["GET"])
async def index(request):
    return JsonResponse({
        "service": "Django 异步爬虫系统 - 多端消费版",
        "architecture": "Fanout Exchange",
        "consumers": {
            "springBoot": QUEUE_CONFIG["springBoot"]["name"],
            "front": QUEUE_CONFIG["front"]["name"]
        },
        "endpoints": {
            "start": "POST /api/crawl/start",
            "stop": "POST /api/crawl/stop/<task_id>",
            "stream": "GET /api/crawl/stream/<task_id>"
        }
    })


@require_http_methods(["GET"])
async def queue_info(request):
    return JsonResponse({
        "exchange": EXCHANGE_CONFIG,
        "queues": QUEUE_CONFIG,
        "description": "所有队列都绑定到同一个 Fanout Exchange，消息会广播到所有队列"
    })


@require_http_methods(["POST"])
async def debug_publish(request, task_id):
    """发送一条 Envelope 测试消息到广播 Exchange"""
    try:
        conn = await aio_pika.connect_robust(AMQP_URL)
        async with conn:
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

            envelope = {
                "version": "1.0",
                "messageType": "message",
                "taskId": int(task_id),
                "timestamp": 0,
                "dateTime": "",
                "payload": {"ping": "ok"}
            }

            await ex.publish(
                aio_pika.Message(
                    body=json.dumps(envelope, ensure_ascii=False).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json",
                ),
                routing_key=EXCHANGE_CONFIG.get("routing_key", "")
            )
        return JsonResponse({"ok": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
