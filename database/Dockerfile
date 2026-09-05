FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /bootstrap
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir bcrypt==4.3.0 psycopg2-binary==2.9.10
COPY database /database
COPY data/synthetic /datasets
COPY database/bootstrap.py /bootstrap/bootstrap.py
RUN useradd --create-home --uid 10001 crimelens && chown -R crimelens:crimelens /bootstrap
USER crimelens
CMD ["python", "/bootstrap/bootstrap.py"]
