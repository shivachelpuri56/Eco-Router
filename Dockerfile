FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY eco_router/ ./eco_router/
COPY regions/ ./regions/
COPY scripts/ ./scripts/
COPY .env.example .env

EXPOSE 8000

ENV PYTHONUTF8=1
ENV PYTHONIOENCODING=utf-8

CMD ["uvicorn", "eco_router.main:app", "--host", "0.0.0.0", "--port", "8000"]
