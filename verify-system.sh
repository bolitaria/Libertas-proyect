#!/bin/bash
echo "=================================================="
echo "🕊️  LIBERTAS PROJECT - VERIFICACIÓN COMPLETA DEL SISTEMA"
echo "=================================================="

echo ""
echo "📋 1. ESTADO DE CONTENEDORES:"
echo "--------------------------------------------------"
docker-compose ps 2>/dev/null | grep -v "WARN" || docker ps --filter "name=libertas" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "🌐 2. SERVICIOS DISPONIBLES:"
echo "--------------------------------------------------"

check_service() {
    local name=$1
    local url=$2
    local timeout=5
    
    echo -n "• $name: "
    if curl -s -f --max-time $timeout "$url" > /dev/null; then
        echo "✅ ONLINE"
        return 0
    else
        echo "❌ OFFLINE"
        return 1
    fi
}

echo ""
echo "🔍 Probando servicios..."
echo ""

check_service "Frontend (3000)" "http://localhost:3000/health"
check_service "API Backend (8000)" "http://localhost:8000/health"
check_service "MinIO API (9000)" "http://localhost:9000/minio/health/live"

echo ""
echo "📡 3. ACCESOS WEB:"
echo "--------------------------------------------------"
echo "• 🖥️  Frontend:      http://localhost:3000"
echo "• 🔧 API Backend:    http://localhost:8000"
echo "• 📚 API Docs:       http://localhost:8000/docs"
echo "• 📦 MinIO Console:  http://localhost:9001"
echo "• 🏥 Health Check:   http://localhost:8000/health"
echo "• 🌐 P2P Network:    localhost:6881 (TCP/UDP)"

echo ""
echo "🔧 4. CONFIGURACIÓN:"
echo "--------------------------------------------------"
echo "• MinIO Usuario:     minioadmin"
echo "• MinIO Contraseña:  minio123"
echo "• PostgreSQL:        postgres:5432 (libertas/libertas123)"
echo "• Redis:             redis:6379"

echo ""
echo "📊 5. ESTADÍSTICAS DEL SISTEMA:"
echo "--------------------------------------------------"
echo "Contenedores activos: $(docker ps -q | wc -l)"
echo "Servicios Libertas:   $(docker ps --filter "name=libertas" -q | wc -l)"
echo "Uso de memoria:       $(docker stats --no-stream --format "{{.MemUsage}}" 2>/dev/null | head -1 || echo "No disponible")"

echo ""
echo "📝 6. LOGS RECIENTES:"
echo "--------------------------------------------------"
for service in orchestrator frontend fetcher; do
    if docker-compose ps | grep -q "$service"; then
        echo ""
        echo "📋 $service:"
        docker-compose logs --tail=2 "$service" 2>/dev/null | grep -E "(INFO|ERROR|Started|Uvicorn)" || echo "  Sin logs recientes"
    fi
done

echo ""
echo "🚀 7. COMANDOS ÚTILES:"
echo "--------------------------------------------------"
echo "• Ver logs:          docker-compose logs -f [servicio]"
echo "• Reiniciar:         docker-compose restart [servicio]"
echo "• Reconstruir:       docker-compose build [servicio]"
echo "• Ver todos:         docker-compose ps"
echo "• Detener todo:      docker-compose down"
echo "• Iniciar todo:      docker-compose up -d"

echo ""
echo "=================================================="
echo "🎉 ¡SISTEMA LISTO! Visita http://localhost:3000"
echo "=================================================="
