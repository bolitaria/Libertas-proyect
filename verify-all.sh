#!/bin/bash
echo "🕊️  LIBERTAS PROJECT - ESTADO COMPLETO"
echo "========================================"

echo ""
echo "1. 🐳 ESTADO DE CONTENEDORES:"
echo "------------------------------"
docker-compose ps 2>/dev/null || echo "Error al verificar contenedores"

echo ""
echo "2. 🌐 PRUEBAS DE CONEXIÓN:"
echo "------------------------------"

# Función para probar servicios
test_service() {
    local name=$1
    local url=$2
    local port=$3
    
    echo -n "• $name ($port): "
    if curl -s -f --max-time 5 "$url" >/dev/null 2>&1; then
        echo "✅ ONLINE"
        return 0
    else
        echo "❌ OFFLINE"
        return 1
    fi
}

echo ""
echo "3. 🔗 SERVICIOS WEB:"
test_service "Frontend" "http://localhost:3001" "3001"
test_service "API Backend" "http://localhost:8000" "8000"
test_service "API Health" "http://localhost:8000/health" "8000"
test_service "API Docs" "http://localhost:8000/docs" "8000"
test_service "MinIO Console" "http://localhost:9001" "9001"
test_service "MinIO Health" "http://localhost:9000/minio/health/live" "9000"

echo ""
echo "4. 📊 LOGS DE SERVICIOS:"
echo "------------------------------"
for service in orchestrator fetcher frontend; do
    echo ""
    echo "📋 $service:"
    docker-compose logs --tail=3 "$service" 2>/dev/null | grep -v "WARN" || echo "  No hay logs recientes"
done

echo ""
echo "5. 🎯 ACCESOS RÁPIDOS:"
echo "------------------------------"
echo "• 🌐 Frontend Web:    http://localhost:3001"
echo "• 🔧 API Backend:     http://localhost:8000"
echo "• 📚 API Docs:        http://localhost:8000/docs"
echo "• 📦 MinIO Console:   http://localhost:9001"
echo "• 👤 MinIO Login:     minioadmin / minio123"
echo "• 🌐 P2P Network:     localhost:6881 (TCP/UDP)"

echo ""
echo "6. 🛠️  COMANDOS ÚTILES:"
echo "------------------------------"
echo "• Ver logs fetcher:    docker-compose logs -f fetcher"
echo "• Shell en fetcher:    docker-compose exec fetcher sh"
echo "• Ejecutar fetcher:    docker-compose exec fetcher python main.py"
echo "• Ver datos:          docker-compose exec fetcher ls -la /data/downloads/"
echo "• Reiniciar todo:      docker-compose restart"

echo ""
echo "========================================"
echo "🎉 SISTEMA VERIFICADO - LIBERTAS PROJECT"
