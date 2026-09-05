# ---- CrimeLensAI: API Gateway Service ----
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
RUN find app -type f -name '*.py' -exec chmod 644 {} +

FROM base AS test
RUN pip install --no-cache-dir pytest ruff
COPY tests ./tests
RUN find tests -type f -name '*.py' -exec chmod 644 {} +
CMD ["python", "-m", "pytest", "-q"]

FROM base AS production
RUN useradd --create-home --uid 10001 crimelens
RUN mkdir -p /data/uploads /app/uploads && chown crimelens:crimelens /data/uploads /app/uploads
USER crimelens

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
