#!/usr/bin/env python
"""
爬虫服务启动脚本
运行 CrawlerService 来处理爬虫任务和消息广播
"""
import asyncio
import os
import sys
import django
import importlib  # 🔥 添加

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MultiSpiders.settings')
django.setup()

# 🔥 强制重新加载模块
import spider_core.crawler

importlib.reload(spider_core.crawler)

from spider_core.crawler import CrawlerService
from spider_core.configs import AMQP_URL


async def main():
    """启动爬虫服务"""
    print("🚀 正在启动爬虫服务...")
    print(f"🔍 调试：crawler 模块路径 = {spider_core.crawler.__file__}")  # 🔥 验证加载的文件

    # 创建爬虫服务实例
    crawler = CrawlerService(AMQP_URL)

    try:
        # 运行爬虫服务
        await crawler.run()
    except KeyboardInterrupt:
        print("\n🛑 收到停止信号，正在关闭爬虫服务...")
    except Exception as e:
        print(f"❌ 爬虫服务运行出错: {e}")
        import traceback
        traceback.print_exc()  # 🔥 打印完整错误堆栈
    finally:
        # 清理资源
        if crawler.connection and not crawler.connection.is_closed:
            await crawler.connection.close()
        print("✅ 爬虫服务已停止")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 再见!")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)