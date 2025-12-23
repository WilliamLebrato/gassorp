FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir aiohttp asyncio

COPY main.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
