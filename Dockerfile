FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DB_PATH=/app/var/bot.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Изображения (assets/img, assets/png) должны быть подготовлены до сборки —
# см. шаг 0 в README.
COPY bot/ ./bot/
COPY data/ ./data/
COPY assets/ ./assets/

RUN useradd --create-home --uid 10001 botuser \
    && mkdir -p /app/var \
    && chown -R botuser:botuser /app/var
USER botuser

CMD ["python", "-m", "bot.main"]
