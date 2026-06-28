FROM rust:1-bookworm AS apkeep-builder

RUN cargo install apkeep --locked


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libssl3 \
        aapt \
        file \
        unzip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=apkeep-builder /usr/local/cargo/bin/apkeep /usr/local/bin/apkeep

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic

RUN mkdir -p /app/artifacts/tmp/apks \
    && mkdir -p /app/artifacts/tmp/uploads \
    && mkdir -p /app/artifacts/apks \
    && mkdir -p /app/artifacts/public/icons \
    && mkdir -p /app/artifacts/comparisons \
    && mkdir -p /app/artifacts/reports/mobsf \
    && mkdir -p /app/artifacts/reports/mastg \
    && mkdir -p /app/artifacts/reports/comparisons

EXPOSE 8088

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088"]