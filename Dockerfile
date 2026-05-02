# ============================================================
# Dockerfile — Price Comparison Agent (Zepto + Blinkit)
# Multi-stage build for lean production image
# ============================================================

# ── Stage 1: dependency builder ───────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Playwright browser install ───────────────────────
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy AS playwright-base

WORKDIR /app
COPY --from=builder /install /usr/local
RUN playwright install chromium && playwright install-deps chromium


# ── Stage 3: production runtime ───────────────────────────────
FROM playwright-base AS production

WORKDIR /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY src/ ./src/
COPY streamlit_app.py .

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8001 8501

CMD ["uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--no-access-log"]
