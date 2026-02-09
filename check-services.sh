#!/bin/bash
echo "🔍 Verificando servicios Libertas..."
echo ""

# Verificar contenedores
echo "🐳 Contenedores:"
docker-compose ps 2>/dev/null | grep -v "WARN" || echo "Usa: docker ps | grep libertas"

echo ""
echo "🌐 Puertos en uso:"
echo "• 3000: $(sudo lsof -i:3000 2>/dev/null | grep LISTEN | wc -l) procesos"
echo "• 3001: $(sudo lsof -i:3001 2>/dev/null | grep LISTEN | wc -l) procesos"
echo "• 8000: $(sudo lsof -i:8000 2>/dev/null | grep LISTEN | wc -l) procesos"
echo "• 9000: $(sudo lsof -i:9000 2>/dev/null | grep LISTEN | wc -l) procesos"
echo "• 9001: $(sudo lsof -i:9001 2>/dev/null | grep LISTEN | wc -l) procesos"

echo ""
echo "🚪 Intentando conexiones:"
for port in 3000 3001 8000 9000 9001; do
    if timeout 2 curl -s http://localhost:$port >/dev/null 2>&1; then
        echo "✅ Puerto $port: ACCESIBLE"
    else
        echo "❌ Puerto $port: NO ACCESIBLE"
    fi
done
