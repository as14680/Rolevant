FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# DATA_DIR is where the SQLite db lives.
# Mount a persistent volume here on Railway/Render/Fly.
ENV DATA_DIR=/data
ENV ENVIRONMENT=production

EXPOSE 8000

CMD ["python3", "run.py", "serve"]
