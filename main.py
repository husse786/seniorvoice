for service in stt-service llm-service action-service tts-service logger-dashboard; do

cat > services/$service/main.py << EOF
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"service": "$service", "status": "ok"}
EOF

cat > services/$service/Dockerfile << EOF
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

cat > services/$service/requirements.txt << EOF
fastapi
uvicorn
EOF

done