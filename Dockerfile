# Lowball — single-process Flask + voice backend (one Kuzu lock).
# Runs serve.py, which seeds the graph on boot and serves dashboard + voice
# webhooks on $PORT. Render sets $PORT; serve.py reads it.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render provides $PORT; serve.py binds 0.0.0.0:$PORT.
CMD ["python", "serve.py"]
