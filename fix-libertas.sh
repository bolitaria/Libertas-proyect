#!/bin/bash
echo "🔧 Reparando Libertas Project..."
echo ""

# 1. Limpiar
echo "🧹 Limpiando contenedores viejos..."
docker-compose down 2>/dev/null
docker rm -f libertas-project-frontend-simple-1 2>/dev/null || true
docker-compose --remove-orphans 2>/dev/null

# 2. Liberar puerto 3000
echo "🚪 Liberando puerto 3000..."
sudo fuser -k 3000/tcp 2>/dev/null || true
sudo fuser -k 3001/tcp 2>/dev/null || true
sudo fuser -k 3002/tcp 2>/dev/null || true

# 3. Reconstruir
echo "🔨 Reconstruyendo servicios..."
docker-compose build classifier fetcher p2p-node frontend

# 4. Iniciar
echo "🚀 Iniciando servicios..."
docker-compose up -d

# 5. Esperar
echo "⏳ Esperando inicialización..."
sleep 20

# 6. Verificar
echo "🔍 Verificando estado..."
docker-compose ps

echo ""
echo "🌐 URLs:"
echo "• Frontend: http://localhost:3000 (o 3001/3002 si cambiaste)"
echo "• API: http://localhost:8000"
echo "• MinIO: http://localhost:9001"
echo "• API Docs: http://localhost:8000/docs"

echo ""
echo "📋 Logs disponibles con:"
echo "• docker-compose logs fetcher"
echo "• docker-compose logs frontend"
echo "• docker-compose logs -f (todos)"
