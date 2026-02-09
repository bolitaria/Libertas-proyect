from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear la aplicación FastAPI
app = FastAPI(
    title="Libertas Orchestrator API",
    description="API para el sistema de gestión de documentos Libertas",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "🕊️ Libertas Orchestrator API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "documents": "/api/documents",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }

@app.get("/health")
async def health_check():
    """Endpoint de salud"""
    return {
        "status": "healthy",
        "service": "orchestrator",
        "timestamp": "2024-01-15T00:00:00Z"
    }

@app.get("/api/documents")
async def get_documents():
    """Obtener lista de documentos"""
    return {
        "documents": [
            {"id": 1, "title": "Documento de prueba 1", "status": "processed"},
            {"id": 2, "title": "Documento de prueba 2", "status": "pending"}
        ],
        "count": 2,
        "page": 1
    }

@app.get("/api/status")
async def get_system_status():
    """Obtener estado del sistema"""
    return {
        "services": {
            "orchestrator": "running",
            "database": "connected",
            "redis": "connected",
            "minio": "connected"
        },
        "statistics": {
            "documents_processed": 0,
            "documents_pending": 0,
            "users_online": 0
        }
    }

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    logger.info(f"🚀 Iniciando Libertas Orchestrator en {host}:{port}")
    logger.info(f"📚 Documentación disponible en http://{host}:{port}/docs")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )
