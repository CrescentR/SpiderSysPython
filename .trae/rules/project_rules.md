---
description: 该规则解释了 Python 编码、最佳实践、 整洁高效的代码模式.
globs: **/*.py
alwaysApply: false
---

# Python 规则

- 遵循 PEP 8 风格指南和命名约定
- 使用类型注解增强代码可读性和类型安全性
- 使用虚拟环境管理依赖：
  - 优先使用 `venv` 或 `poetry` 进行环境隔离
  - 使用 `requirements.txt` 或 `pyproject.toml` 记录依赖
- 使用上下文管理器处理资源（如文件操作）
- 优先使用列表推导式、生成器表达式和字典推导式
- 使用 `pytest` 进行测试，保持高测试覆盖率
- 使用文档字符串（docstrings）记录函数、类和模块
- 遵循面向对象设计原则（SOLID）
- 使用异常处理保证程序健壮性

---
description: AI 辅助补全建议.
globs: **/*.py
alwaysApply: false
pattern: "**/*.py",
---
- "ai_instructions": 
- "生成代码时优先使用 requests + BeautifulSoup 或 httpx + lxml。",
- "如果检测到 JSON 响应，请自动推荐解析路径与字段映射逻辑。",
- "对翻页逻辑，自动补全 next_cursor 提取语句。",
- "自动生成 type hints 和 docstring。"

---
"pattern": "**/*.py",
"description": "异常与日志规则",
---
"guidelines": [
    "所有外部请求必须捕获异常并记录日志。",
    "日志使用 logging 模块，统一格式为：'%(asctime)s - %(levelname)s - %(message)s'。",
    "错误级别分为 info, warning, error, critical 四类。"
]

---
"pattern": "**/*.py",
"description": "Python 爬虫项目代码规范",
---
所有爬虫类文件必须放在 `spider_core/` 目录下，并在 `crawler.py` 的基础上修改。",
"函数和变量命名使用 snake_case，类名使用 PascalCase。",
"每个函数必须包含 docstring，说明参数和返回值。",
"禁止在主逻辑中使用 print，请使用 logging 模块。",
"网络请求使用 requests 或 aiohttp的异步爬取，如果有必要可以使用playwright，必须加超时与重试逻辑。",
"分页接口应实现 cursor 或 page 参数逻辑，并明确停止条件。",
"数据解析部分必须与请求逻辑分离，使用 parse_* 函数封装。",
"请为每个 spider 添加 __main__ 入口用于单独调试。"