#!/bin/bash
echo "Configurando proyecto Libertas..."

# 1. Crear directorios principales
mkdir -p {fetcher,classifier,orchestrator,frontend,p2p-network,storage,data,nginx,monitoring}

# 2. Crear Dockerfiles
cat > orchestrator/Dockerfile << 'DOCKERFILE'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
DOCKERFILE

cat > fetcher/Dockerfile << 'DOCKERFILE'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
DOCKERFILE

cat > classifier/Dockerfile << 'DOCKERFILE'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
DOCKERFILE

cat > p2p-network/Dockerfile << 'DOCKERFILE'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 6881
EXPOSE 6881/udp
CMD ["python", "main.py"]
DOCKERFILE

cat > frontend/Dockerfile << 'DOCKERFILE'
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]
DOCKERFILE

# 3. Crear requirements.txt básicos
cat > orchestrator/requirements.txt << 'REQ'
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
redis==5.0.1
minio==7.2.2
python-dotenv==1.0.0
psycopg2-binary==2.9.9
REQ

cat > fetcher/requirements.txt << 'REQ'
requests==2.31.0
beautifulsoup4==4.12.2
redis==5.0.1
python-dotenv==1.0.0
aiohttp==3.9.1
REQ

cat > classifier/requirements.txt << 'REQ'
torch==2.1.0
transformers==4.35.2
scikit-learn==1.3.2
redis==5.0.1
python-dotenv==1.0.0
PyPDF2==3.0.1
REQ

cat > p2p-network/requirements.txt << 'REQ'
libtorrent==2.0.9
redis==5.0.1
python-dotenv==1.0.0
fastapi==0.104.1
REQ

# 4. Crear archivos principales de Python
cat > orchestrator/main.py << 'PYTHON'
from fastapi import FastAPI
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Libertas Orchestrator")

@app.get("/")
async def root():
    return {"message": "Libertas Orchestrator API", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/documents")
async def list_documents():
    return {"documents": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
PYTHON

cat > fetcher/main.py << 'PYTHON'
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DOJFetcher:
    def __init__(self):
        logger.info("Inicializando DOJ Fetcher")
    
    def run(self):
        logger.info("Ejecutando DOJ Fetcher")
        while True:
            logger.info("Simulando descarga de documentos...")
            time.sleep(60)

if __name__ == "__main__":
    fetcher = DOJFetcher()
    fetcher.run()
PYTHON

cat > classifier/main.py << 'PYTHON'
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentClassifier:
    def __init__(self):
        logger.info("Inicializando Clasificador de Documentos")
    
    def run(self):
        logger.info("Ejecutando Clasificador")
        while True:
            logger.info("Simulando clasificación...")
            time.sleep(60)

if __name__ == "__main__":
    classifier = DocumentClassifier()
    classifier.run()
PYTHON

cat > p2p-network/main.py << 'PYTHON'
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class P2PNode:
    def __init__(self):
        logger.info("Inicializando Nodo P2P")
    
    def run(self):
        logger.info("Ejecutando Nodo P2P")
        while True:
            logger.info("Nodo P2P activo...")
            time.sleep(60)

if __name__ == "__main__":
    node = P2PNode()
    node.run()
PYTHON

# 5. Crear frontend básico
cat > frontend/package.json << 'JSON'
{
  "name": "libertas-frontend",
  "version": "1.0.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "14.0.3",
    "react": "18.2.0",
    "react-dom": "18.2.0",
    "axios": "^1.6.2"
  }
}
JSON

cat > frontend/pages/index.js << 'JS'
import { useState, useEffect } from 'react';

export default function Home() {
  const [status, setStatus] = useState('Cargando...');
  
  useEffect(() => {
    fetch('http://localhost:8000/')
      .then(res => res.json())
      .then(data => setStatus(data.message))
      .catch(() => setStatus('Error conectando al backend'));
  }, []);
  
  return (
    <div style={{ padding: '50px', fontFamily: 'Arial' }}>
      <h1>🕊️ Libertas Project</h1>
      <p>Estado del sistema: <strong>{status}</strong></p>
      <div style={{ marginTop: '30px' }}>
        <h3>Servicios:</h3>
        <ul>
          <li>✅ Orquestador API (Puerto 8000)</li>
          <li>📥 Fetcher DOJ</li>
          <li>🏷️ Clasificador ML</li>
          <li>🌐 Red P2P (Puerto 6881)</li>
          <li>🗄️ PostgreSQL + Redis + MinIO</li>
        </ul>
      </div>
    </div>
  );
}
JS

# 6. Crear docker-compose.yml completo
cat > docker-compose.yml << 'COMPOSE'
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: libertas123
      POSTGRES_DB: libertas
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minio123
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  orchestrator:
    build: ./orchestrator
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:libertas123@postgres/libertas
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minio123
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy

  fetcher:
    build: ./fetcher
    environment:
      REDIS_URL: redis://redis:6379/0
      DOJ_USER_AGENT: LibertasResearchBot/1.0
    depends_on:
      redis:
        condition: service_healthy
      orchestrator:
        condition: service_started

  classifier:
    build: ./classifier
    environment:
      REDIS_URL: redis://redis:6379/0
      DATABASE_URL: postgresql://postgres:libertas123@postgres/libertas
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  p2p-node:
    build: ./p2p-network
    ports:
      - "6881:6881"
      - "6881:6881/udp"
    environment:
      REDIS_URL: redis://redis:6379/0
    depends_on:
      redis:
        condition: service_healthy

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://orchestrator:8000
    depends_on:
      orchestrator:
        condition: service_started

volumes:
  postgres_data:
  minio_data:

networks:
  default:
    name: libertas-network
COMPOSE

echo "✅ Estructura creada exitosamente!"
echo ""
echo "Para iniciar el sistema:"
echo "1. docker-compose build"
echo "2. docker-compose up -d"
echo "3. Visita http://localhost:3000"
