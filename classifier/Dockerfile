FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias para ML
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para mejor caché
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Descargar modelo de spaCy usando pip en lugar del comando spaCy
RUN pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1.tar.gz

# Copiar código
COPY . .

# Crear directorios necesarios
RUN mkdir -p /data/models /data/processed /var/log

# Comando de inicio
CMD ["python", "-m", "classifier.main"]