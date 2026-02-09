#!/bin/bash
echo "==============================================="
echo "🕊️  LIBERTAS PROJECT - ESTADO COMPLETO"
echo "==============================================="

echo ""
echo "1. 🐳 TODOS LOS CONTENEDORES:"
echo "--------------------------------"
docker-compose ps 2>/dev/null || echo "Error: ejecuta 'docker-compose ps' manualmente"

echo ""
echo "2. 🌐 PUNTOS DE ACCESO:"
echo "--------------------------------"
echo "• Frontend:      http://localhost:3000"
echo "• API Backend:   http://localhost:8000"
echo "• API Docs:      http://localhost:8000/docs"
echo "• MinIO Console: http://localhost:9001"
echo "• MinIO API:     http://localhost:9000"
echo "• PostgreSQL:    localhost:5432"
echo "• Redis:         localhost:6379"
echo "• P2P Node:      localhost:6881 (TCP/UDP)"

echo ""
echo "3. 🔍 PRUEBAS DE CONECTIVIDAD:"
echo "--------------------------------"
# Probar API
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ API Backend: Funcionando"
else
    echo "❌ API Backend: No responde"
fi

# Probar MinIO
if curl -s http://localhost:9000/minio/health/live > /dev/null; then
    echo "✅ MinIO: Funcionando"
else
    echo "❌ MinIO: No responde"
fi

# Probar Frontend
if curl -s http://localhost:3000 > /dev/null; then
    echo "✅ Frontend: Funcionando"
else
    echo "⚠️  Frontend: Puede estar iniciando..."
fi

echo ""
echo "4. 📈 LOGS DE INICIALIZACIÓN:"
echo "--------------------------------"
for service in orchestrator fetcher classifier p2p-node frontend frontend-simple; do
    if docker-compose ps | grep -q "$service"; then
        echo "📋 $service:"
        docker-compose logs --tail=2 "$service" 2>/dev/null | grep -v "WARN" || echo "  (sin logs recientes)"
    fi
done

echo ""
echo "5. 🎯 ACCIONES RECOMENDADAS:"
echo "--------------------------------"
echo "1. Acceder a http://localhost:8000/docs para ver la API"
echo "2. Acceder a http://localhost:9001 para configurar MinIO"
echo "3. Ver logs: docker-compose logs -f [servicio]"
echo "4. Reconstruir: docker-compose build [servicio]"
echo "5. Reiniciar: docker-compose restart [servicio]"

echo ""
echo "==============================================="
