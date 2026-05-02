FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Chromium for Playwright
RUN playwright install chromium && \
    playwright install-deps chromium

# Copy source
COPY src/ ./src/
COPY streamlit_app.py .

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Hugging Face uses port 7860
EXPOSE 7860

CMD ["uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "7860", \
     "--workers", "1", \
     "--loop", "uvloop"]
