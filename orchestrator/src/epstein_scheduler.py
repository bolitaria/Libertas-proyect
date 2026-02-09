#!/usr/bin/env python3
"""
Programador especializado para archivos Epstein del DOJ.
Maneja la escala masiva (3.5M páginas) y problemas de redacción.
"""
import asyncio
import aiohttp
import json
from datetime import datetime
import logging
from typing import List, Dict
import hashlib

logger = logging.getLogger(__name__)

class EpsteinScheduler:
    def __init__(self, config):
        self.config = config
        self.session = None
        self.processed_count = 0
        
    async def fetch_manifest(self) -> List[Dict]:
        """Obtiene el manifiesto de documentos del DOJ"""
        try:
            async with self.session.get(self.config['urls']['manifest']) as response:
                if response.status == 200:
                    manifest = await response.json()
                    logger.info(f"Manifiesto obtenido: {len(manifest.get('files', []))} archivos")
                    
                    # Filtrar por tipos soportados
                    supported_ext = {'.pdf', '.jpg', '.png', '.mp4', '.txt'}
                    filtered_files = [
                        file for file in manifest.get('files', [])
                        if any(file['url'].lower().endswith(ext) for ext in supported_ext)
                    ]
                    
                    # Ordenar por fecha (más reciente primero)
                    filtered_files.sort(
                        key=lambda x: x.get('date', '2000-01-01'), 
                        reverse=True
                    )
                    
                    return filtered_files[:1000]  # Limitar para prueba inicial
                else:
                    logger.error(f"Error obteniendo manifiesto: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Excepción obteniendo manifiesto: {e}")
            return []
    
    async def validate_redaction(self, file_path: str) -> Dict:
        """Valida que las redacciones sean efectivas"""
        import re
        import PyPDF2
        
        issues = []
        
        # Patrones de información sensible
        pii_patterns = {
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'phone': r'\b\d{3}[.-]?\d{3}[.-]?\d{4}\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'credit_card': r'\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b'
        }
        
        try:
            if file_path.endswith('.pdf'):
                # Extraer texto del PDF
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                
                # Buscar PII no redactado
                for pii_type, pattern in pii_patterns.items():
                    matches = re.findall(pattern, text)
                    if matches:
                        issues.append({
                            'type': pii_type,
                            'count': len(matches),
                            'samples': matches[:3]
                        })
                
                # Verificar áreas negras (redacciones)
                # Esta sería una implementación más compleja con análisis de imágenes
                
        except Exception as e:
            logger.error(f"Error validando redacción: {e}")
        
        return {
            'file': file_path,
            'issues': issues,
            'needs_review': len(issues) > 0
        }
    
    async def schedule_downloads(self, files: List[Dict]):
        """Programa descargas con prioridad inteligente"""
        from redis import Redis
        redis_client = Redis(host='redis', port=6379, decode_responses=True)
        
        # Priorizar documentos recientes y PDFs
        for file in files:
            priority = 5  # Default
            
            # Aumentar prioridad para documentos recientes
            if 'date' in file:
                file_date = datetime.fromisoformat(file['date'].replace('Z', '+00:00'))
                days_old = (datetime.now() - file_date).days
                if days_old < 30:
                    priority = 1  # Muy alta
                elif days_old < 90:
                    priority = 3  # Alta
            
            # Aumentar prioridad para PDFs (más contenido)
            if file['url'].endswith('.pdf'):
                priority = max(1, priority - 1)
            
            # Crear job
            job_id = f"epstein_{hashlib.md5(file['url'].encode()).hexdigest()[:8]}"
            
            job_data = {
                'job_id': job_id,
                'url': file['url'],
                'source': 'epstein_doj',
                'priority': priority,
                'metadata': json.dumps(file),
                'created_at': datetime.now().isoformat(),
                'status': 'queued'
            }
            
            # Encolar en Redis según prioridad
            if priority <= 2:
                redis_client.lpush('queue:high', json.dumps(job_data))
            else:
                redis_client.lpush('queue:normal', json.dumps(job_data))
            
            logger.info(f"Job encolado: {job_id} (prioridad: {priority})")
    
    async def run(self):
        """Ejecuta el scheduler para Epstein"""
        logger.info("Iniciando Epstein Scheduler")
        
        connector = aiohttp.TCPConnector(limit=5)
        timeout = aiohttp.ClientTimeout(total=300)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': self.config['politeness']['user_agent']}
        ) as session:
            self.session = session
            
            # Obtener manifiesto
            files = await self.fetch_manifest()
            
            if files:
                logger.info(f"Programando {len(files)} descargas")
                await self.schedule_downloads(files)
                
                # Monitorear progreso
                await self.monitor_progress(files)
    
    async def monitor_progress(self, files: List[Dict]):
        """Monitorea el progreso de descarga"""
        from redis import Redis
        redis_client = Redis(host='redis', port=6379, decode_responses=True)
        
        total_files = len(files)
        check_interval = 60  # segundos
        
        while True:
            # Contar trabajos completados
            completed = redis_client.scard('jobs:completed')
            failed = redis_client.scard('jobs:failed')
            
            progress = (completed / total_files) * 100 if total_files > 0 else 0
            
            logger.info(
                f"Progreso: {progress:.1f}% | "
                f"Completados: {completed}/{total_files} | "
                f"Fallidos: {failed}"
            )
            
            # Actualizar dashboard
            redis_client.hset('system:stats', 'epstein_progress', progress)
            redis_client.hset('system:stats', 'epstein_completed', completed)
            redis_client.hset('system:stats', 'epstein_total', total_files)
            
            if completed + failed >= total_files:
                logger.info("¡Todas las descargas Epstein completadas!")
                break
            
            await asyncio.sleep(check_interval)

if __name__ == "__main__":
    import yaml
    
    # Cargar configuración
    with open('config/sources/epstein_doj.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    scheduler = EpsteinScheduler(config)
    asyncio.run(scheduler.run())