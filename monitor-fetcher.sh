#!/bin/bash
echo "📥 MONITOR DE DESCARGAS DOJ EPSTEIN - TIEMPO REAL"
echo "=================================================="

echo ""
echo "1. 🐳 ESTADO DEL FETCHER:"
docker-compose ps fetcher

echo ""
echo "2. 📋 LOGS EN TIEMPO REAL (Ctrl+C para salir):"
echo "----------------------------------------------"
docker-compose logs -f fetcher
