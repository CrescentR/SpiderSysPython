 一、项目目标（一句话概括）
实现一个基于 Django 的简易网页爬虫任务系统：
用户通过 Web 页面输入关键词和参数，系统创建爬虫任务，并使用爬虫模块（如 Bing 搜索）自动获取相关网页链接，实时输出或保存结果。

🧩 二、整体功能模块划分
模块	主要功能	实现技术	是否必须
🧱 1. 任务管理模块	创建、查看、删除爬虫任务	Django + SQLite	✅ 必须
🔍 2. 爬取模块	根据关键词抓取网页链接（如 Bing 搜索结果）	requests / aiohttp + BeautifulSoup	✅ 必须
🧭 3. 异步抓取模块（可选）	实时输出每个爬到的链接	asyncio + aiohttp	⭐ 推荐
💾 4. 数据存储模块	保存任务参数、结果（数据库 + JSON 文件）	Django ORM / json	✅ 必须
💬 5. 消息与反馈模块	创建任务成功/失败提示	Django messages	✅ 必须
🖥️ 6. 前端展示模块	任务创建表单 + 结果展示页面	Django模板 + Bootstrap	✅ 必须
⚙️ 7. 扩展功能（选做）	分页爬取、关键词分词、导出Excel等	可选	⭐ 可加分

⚙️ 三、执行流程（后端逻辑）
markdown
复制
编辑
用户打开创建任务页
     ↓
填写任务名称 + 关键词 + 种子URL + 参数
     ↓
点击“创建任务” → Django 视图 create_task()
     ↓
1️⃣ 验证输入参数
2️⃣ 创建 SpiderTask 数据记录（状态=created）
3️⃣ 显示“任务创建成功”消息
     ↓
跳转到任务详情页 task_detail
     ↓
后端启动爬取逻辑（可异步执行）
     ↓
实时输出或最终保存爬取到的链接结果
🧱 四、各文件职责梳理
文件 / 模块	功能说明
models.py	定义 SpiderTask 数据模型（任务名、关键词、状态等）
views.py	控制任务创建、详情展示、启动爬虫逻辑
urls.py	配置路由：/task/create/、/task/<id>/
templates/spider_ui/task_create.html	任务创建表单页面
templates/spider_ui/task_detail.html	任务详情与结果展示
crawler/spider.py	实际的爬虫逻辑文件（Bing 爬取、异步输出）
static/	前端样式（Bootstrap，可选）

💡 五、数据库模型简要示例
python
复制
编辑
class SpiderTask(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    keywords = models.CharField(max_length=255)
    seed_urls = models.TextField()  # 存JSON字符串
    max_pages = models.IntegerField(default=100)
    max_depth = models.IntegerField(default=3)
    concurrent_requests = models.IntegerField(default=5)
    download_delay = models.FloatField(default=1.0)
    timeout = models.IntegerField(default=30)
    status = models.CharField(max_length=20, default='created')
    created_at = models.DateTimeField(auto_now_add=True)
🔍 六、爬虫逻辑（简易版）
你只需要一个爬虫文件实现以下流程即可：

python
复制
编辑
def crawl_links_from_bing(keyword, pages=1):
    results = []
    for i in range(pages):
        first = i * 10
        url = f"https://cn.bing.com/search?q={keyword}&first={first}"
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.select('li.b_algo h2 a'):
            results.append({'title': a.text, 'url': a['href']})
    return results
如果想改为“异步 + 实时输出”，就用你前面那版 aiohttp + asyncio.as_completed()。

💬 七、前端交互逻辑
页面	主要功能
task_create.html	用户输入任务参数表单（name、keywords、seed_urls 等）
task_detail.html	显示任务状态与已爬取结果
messages	提示“任务创建成功”或“参数错误”等消息
可选AJAX实时刷新	动态更新爬取结果（选做）

📦 八、最终运行结果示例
1️⃣ 用户填写：

arduino
复制
编辑
任务名：豆瓣Top100爬虫
关键词：豆瓣,电影,排名,TOP100
种子URL：https://cn.bing.com/
2️⃣ 点击创建 → 显示提示：

复制
编辑
✅ 任务 “豆瓣Top100爬虫” 创建成功
3️⃣ 跳转到详情页：

arduino
复制
编辑
任务名：豆瓣Top100爬虫
状态：running
关键词：豆瓣,电影,排名,TOP100
--------------------------
豆瓣电影Top250 - https://movie.douban.com/top250
豆瓣电影排行榜 - 百度百科 - https://baike.baidu.com/item/豆瓣电影排行榜
...
🧠 九、总结一句话
你的服务最终要实现的，是一个基于 Django 的「可视化关键词爬虫任务系统」：

用户通过网页创建任务；

系统启动爬虫获取搜索结果链接；

实时或最终展示结果；

任务与参数存数据库，可重复运行。