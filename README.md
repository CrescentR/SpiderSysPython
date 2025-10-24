python .\run_crawler.py


python -m uvicorn MultiSpiders.asgi:application --reload --host 0.0.0.0 --port 8000
