FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY services/case-api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/case-api/app ./app
COPY database /database
COPY data/synthetic /datasets
COPY database/bootstrap.py /bootstrap/bootstrap.py

RUN useradd --create-home --uid 10001 crimelens \
    && mkdir -p /data/uploads \
    && chown -R crimelens:crimelens /data /app /bootstrap
USER crimelens

EXPOSE 10000
CMD ["sh", "-c", "python /bootstrap/bootstrap.py && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
