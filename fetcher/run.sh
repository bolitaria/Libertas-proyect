#!/bin/bash
# Script de ejecución para libertas-project/fetcher/
# Ubicación: libertas-project/fetcher/run.sh

set -e

# Cambiar al directorio del script
cd "$(dirname "$0")"

echo "🔨 Construyendo imagen Docker..."
docker compose build

echo ""
echo "🚀 Comandos disponibles:"
echo ""
echo "1. Todos los datasets (1-9) con máximo 50 páginas:"
echo "   docker compose run --rm fetcher python main_v3.py --all --max-pages 50"
echo ""
echo "2. Solo descubrimiento:"
echo "   docker compose run --rm fetcher python main_v3.py --all --max-pages 50 --discover-only"
echo ""
echo "3. Datasets específicos:"
echo "   docker compose run --rm fetcher python main_v3.py --datasets 1 3 5 --max-pages 30"
echo ""
echo "4. Ver estadísticas:"
echo "   docker compose run --rm fetcher python main_v3.py --stats"
echo ""
echo "5. Rango específico:"
echo "   docker compose run --rm fetcher python main_v3.py --start 2 --end 7 --max-pages 20"
echo ""

# Ejecutar comando si se proporciona
if [ $# -eq 0 ]; then
    echo "📝 Ejecutando comando por defecto: --all --max-pages 50"
    echo ""
    docker compose run --rm fetcher python main_v3.py --all --max-pages 50
else
    echo "📝 Ejecutando: $@"
    echo ""
    docker compose run --rm fetcher python main_v3.py "$@"
fi