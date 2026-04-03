FROM python:3.12-slim AS base

RUN groupadd -r mcp && useradd -r -g mcp -d /app -s /sbin/nologin mcp

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY data/endpoint_catalog.json data/endpoint_catalog.json

RUN mkdir -p data logs && chown -R mcp:mcp /app

USER mcp

EXPOSE 8000

CMD ["python", "app/main.py"]
