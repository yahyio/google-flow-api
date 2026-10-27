FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .

RUN mkdir -p /app/auth && chmod -R 777 /app/auth

ENV PYTHONUNBUFFERED=1
ENV HEADLESS=true
ENV SESSION_STORAGE_PATH=/app/auth/session.json
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
