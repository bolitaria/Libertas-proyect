from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import aiohttp

app = FastAPI(title="Libertas Frontend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def root():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🕊️ Libertas Project</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                min-height: 100vh;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                padding: 40px;
                border-radius: 20px;
                backdrop-filter: blur(10px);
            }
            .status-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }
            .status-card {
                background: rgba(255, 255, 255, 0.15);
                padding: 20px;
                border-radius: 10px;
            }
            .btn {
                display: inline-block;
                background: white;
                color: #667eea;
                padding: 12px 24px;
                border-radius: 50px;
                text-decoration: none;
                font-weight: bold;
                margin: 10px 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🕊️ Libertas Project v1.0</h1>
            <p>Sistema de investigación documental descentralizado</p>
            
            <div class="status-grid">
                <div class="status-card">
                    <h3>🔧 API Backend</h3>
                    <p id="api-status">Verificando...</p>
                </div>
                <div class="status-card">
                    <h3>🗄️ Base de Datos</h3>
                    <p>✅ PostgreSQL</p>
                </div>
                <div class="status-card">
                    <h3>📦 Almacenamiento</h3>
                    <p>✅ MinIO</p>
                </div>
                <div class="status-card">
                    <h3>🔴 Cache</h3>
                    <p>✅ Redis</p>
                </div>
            </div>
            
            <h2>🚀 Acceso a Servicios</h2>
            <div>
                <a href="http://localhost:8000/docs" class="btn" target="_blank">📚 API Documentation</a>
                <a href="http://localhost:9001" class="btn" target="_blank">📦 MinIO Console</a>
                <a href="http://localhost:8000/health" class="btn" target="_blank">🏥 Health Check</a>
            </div>
        </div>
        <script>
            async function checkAPIStatus() {
                try {
                    const response = await fetch('http://localhost:8000/health');
                    const data = await response.json();
                    document.getElementById('api-status').innerHTML = '✅ ' + data.status;
                } catch (error) {
                    document.getElementById('api-status').innerHTML = '❌ Error de conexión';
                }
            }
            checkAPIStatus();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "frontend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
