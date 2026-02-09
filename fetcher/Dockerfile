FROM python:3.12-slim

WORKDIR /app

# Instalar solo dependencias esenciales
RUN apt-get update && apt-get install -y \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero (para mejor caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código
COPY main_v3.py .

# Crear directorios necesarios
RUN mkdir -p /data/logs /data/downloads

# Comando por defecto
CMD ["python", "main_v3.py", "--help"]