#!/bin/bash
echo "🕊️  Libertas Project - Monitor del Sistema"
echo "=========================================="

echo ""
echo "📊 CONTENEDORES DOCKER:"
docker-compose ps

echo ""
echo "🌐 SERVICIOS WEB:"
echo "Frontend (3000): $(curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000 2>/dev/null || echo "OFFLINE")"
echo "API (8000): $(curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health 2>/dev/null || echo "OFFLINE")"
echo "MinIO (9000): $(curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9000/minio/health/live 2>/dev/null || echo "OFFLINE")"

echo ""
echo "💾 RECURSOS DEL SISTEMA:"
echo "Memoria Docker: $(docker stats --no-stream --format "{{.MemUsage}}" | head -1)"
echo "Contenedores activos: $(docker ps -q | wc -l)"

echo ""
echo "📈 LOGS RECIENTES:"
docker-compose logs --tail=5 orchestrator 2>/dev/null | grep -E "(INFO|ERROR|WARNING)"
