# 🕊️ libertas-project-fetcher — main_v3.py (Búsqueda paralelizada)

Descripción
-----------
Script principal: `fetcher/main_v3.py`

Versión optimizada con:
- Descubrimiento ilimitado de datasets
- Búsqueda y conteo de archivos por dataset sin descargar (--query-files)
- Búsqueda y descarga paralelizadas (--workers, --page-workers)
- Caché en memoria de páginas para acelerar reconsultas
- Pool de conexiones, timeouts reducidos y retries inteligentes
- Trazabilidad/metadata en `/data/downloads/metadata/traces`

Instalación / Entorno
---------------------
Ejecutar dentro del entorno del proyecto (WSL/Ubuntu):

- Asegúrate de tener dependencias en venv y Docker si corresponde.
- Rutas de output por defecto: `/data/downloads`, `/data/logs`.

Comandos principales
--------------------
- Descubrir datasets disponibles (rápido, paralelo):
  ```bash
  python fetcher/main_v3.py --discover
  ```

- Consultar cuántos archivos hay por cada dataset (no descarga, recomendado):
  ```bash
  python fetcher/main_v3.py --query-files
  ```

- Consultar (rápido) con más concurrencia:
  ```bash
  python fetcher/main_v3.py --query-files --workers 12 --page-workers 6
  ```

- Descargar un dataset (auto-detección del último page):
  ```bash
  python fetcher/main_v3.py --page-ranges "1" --limit 100 --delay 0.5
  ```

- Descargar múltiples rangos explícitos:
  ```bash
  python fetcher/main_v3.py --page-ranges "1 2:5 3:10" --limit 200
  ```

- Procesar TODOS los datasets (sin límite):
  ```bash
  python fetcher/main_v3.py --all --limit 500
  ```

Parámetros útiles
-----------------
- --page-ranges "DS[:start] DS[:start]"  
  Ejemplos aceptados: `"1"`, `"1:1"`, `"1:5"`, `"1 2:5 3:10"`

- --query-files  : cuenta archivos por dataset sin descargarlos  
- --discover     : lista datasets disponibles  
- --workers N    : threads para datasets (recomendado 4–12)  
- --page-workers N: threads para páginas (recomendado 2–6)  
- --limit N      : máximo archivos a descargar  
- --delay S      : espera entre descargas (segundos)  
- --stats        : muestra estadísticas de caché y descargas  
- --clean        : elimina descargas (use --force para evitar confirmación)

Salida y trazas
---------------
- Descargas: `/data/downloads/raw/dataset_<n>/`
- Cache/metadatos: `/data/downloads/metadata/url_cache.json`
- Trazas (JSON): `/data/downloads/metadata/traces/trace_<id>.json`
- Logs: `/data/logs/fetcher_v3_exhaustive.log`

Recomendaciones rápidas
-----------------------
1. Ejecutar `--discover` para verificar datasets.  
2. Ejecutar `--query-files` para medir volumen (2–5 min típicamente).  
3. Probar con `--all --limit 50` o `--page-ranges "1" --limit 10` antes de producción.  
4. Ajustar `--workers` y `--page-workers` según CPU y cortes del servidor (no exceder 16/8).  
5. Monitorizar `/data/logs/` y traces JSON para auditoría.

Ejemplo de flujo recomendado
---------------------------
```bash
# 1) descubrir datasets
python fetcher/main_v3.py --discover

# 2) conocer volumen
python fetcher/main_v3.py --query-files --workers 8 --page-workers 4

# 3) descargar muestra
python fetcher/main_v3.py --all --limit 50 --delay 0.5

# 4) revisar trazas y logs
tail -n 200 /data/logs/fetcher_v3_exhaustive.log
cat /data/downloads/metadata/traces/trace_*.json | jq .
```

Notas técnicas
--------------
- Detección de última página: búsqueda exponencial + binaria (paralelizada).
- Caché en memoria acelera reconsultas durante la misma ejecución.
- Mantener delays y límites razonables para evitar bloquearse del servidor.

Contacto / mantenimiento
------------------------
- Archivo principal: `fetcher/main_v3.py`  
- Actualizaciones: mantener coherencia entre README y las opciones del script.

Versión
-------
main_v3.py — Febrero 2026 (Búsqueda paralelizada, consulta rápida de archivos)