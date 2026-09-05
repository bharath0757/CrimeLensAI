# ---- CrimeLensAI: Ledger Service ----
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
USER crimelens

EXPOSE 8003

CMD ["sh", "-c", "python -m app.wait_for_schema && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8003}"]
