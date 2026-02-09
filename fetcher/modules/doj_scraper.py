"""
Módulo para scrapear documentos del Departamento de Justicia (DOJ)
sobre el caso Epstein.
"""
import asyncio
import aiohttp
import aiofiles
import yaml
import logging
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import hashlib
import json
from urllib.parse import urljoin, urlparse
import time

logger = logging.getLogger(__name__)

class DOJScraper:
    def __init__(self, config_path: str = "config/doj_config.yaml"):
        """Inicializar scraper DOJ"""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.session = None
        self.downloaded_count = 0
        self.output_dir = Path(self.config['download']['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Estadísticas
        self.stats = {
            'total_found': 0,
            'downloaded': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': None,
            'end_time': None
        }
    
    async def __aenter__(self):
        """Context manager entry"""
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': self.config['sources'][0]['user_agent']},
            timeout=aiohttp.ClientTimeout(total=self.config['download']['timeout_seconds'])
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.session:
            await self.session.close()
    
    def _should_download(self, url: str, content_type: str) -> bool:
        """Determinar si se debe descargar el recurso"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Verificar tipo de archivo
        valid_extensions = [f'.{ext}' for ext in self.config['sources'][0]['document_types']]
        if not any(path.endswith(ext) for ext in valid_extensions):
            return False
        
        # Verificar tamaño máximo
        # (se verifica después de descargar los headers)
        
        return True
    
    async def fetch_url(self, url: str) -> Optional[bytes]:
        """Descargar URL con manejo de errores"""
        for attempt in range(self.config['download']['retry_attempts']):
            try:
                async with self.session.get(url, ssl=self.config['download']['verify_ssl']) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # Verificar tamaño
                        max_size = self.config['download']['max_file_size_mb'] * 1024 * 1024
                        if len(content) > max_size:
                            logger.warning(f"Archivo demasiado grande: {url} ({len(content)/1024/1024:.2f}MB)")
                            return None
                        
                        return content
                    else:
                        logger.warning(f"HTTP {response.status} para {url}")
            except Exception as e:
                logger.error(f"Error en intento {attempt + 1} para {url}: {e}")
                if attempt < self.config['download']['retry_attempts'] - 1:
                    await asyncio.sleep(2 ** attempt)  # Backoff exponencial
        
        return None
    
    async def search_doj_press_releases(self) -> List[str]:
        """Buscar comunicados de prensa del DOJ"""
        base_url = self.config['sources'][0]['base_url']
        search_paths = self.config['sources'][0]['search_paths']
        search_terms = self.config['sources'][0]['search_terms']
        
        found_urls = []
        
        for path in search_paths:
            search_url = urljoin(base_url, path)
            logger.info(f"Buscando en: {search_url}")
            
            try:
                async with self.session.get(search_url) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # Búsqueda simple por términos (en producción usar BeautifulSoup)
                        for term in search_terms:
                            if term.lower() in html.lower():
                                # Extraer URLs de documentos PDF
                                # Esto es un ejemplo simplificado
                                import re
                                pdf_urls = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, re.IGNORECASE)
                                for pdf_url in pdf_urls:
                                    full_url = urljoin(search_url, pdf_url)
                                    if full_url not in found_urls:
                                        found_urls.append(full_url)
                                        logger.info(f"Encontrado documento: {full_url}")
                        
                        # Respetar rate limiting
                        await asyncio.sleep(self.config['sources'][0]['rate_limit']['delay_between_requests'])
            except Exception as e:
                logger.error(f"Error buscando en {search_url}: {e}")
        
        return found_urls
    
    async def download_document(self, url: str) -> Optional[Dict]:
        """Descargar y procesar un documento individual"""
        if not self._should_download(url, ""):
            logger.debug(f"Saltando descarga no permitida: {url}")
            self.stats['skipped'] += 1
            return None
        
        content = await self.fetch_url(url)
        if not content:
            self.stats['failed'] += 1
            return None
        
        # Generar nombre de archivo único
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        parsed_url = urlparse(url)
        filename = parsed_url.path.split('/')[-1] or f"document_{url_hash}"
        safe_filename = "".join(c for c in filename if c.isalnum() or c in '.-_ ').rstrip()
        filepath = self.output_dir / f"{url_hash}_{safe_filename}"
        
        # Guardar archivo
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(content)
        
        # Extraer metadatos
        metadata = {
            'url': url,
            'filename': safe_filename,
            'hash': url_hash,
            'download_date': datetime.now().isoformat(),
            'file_size': len(content),
            'source': 'DOJ',
            'file_path': str(filepath)
        }
        
        # Guardar metadatos
        metadata_file = filepath.with_suffix('.json')
        async with aiofiles.open(metadata_file, 'w') as f:
            await f.write(json.dumps(metadata, indent=2))
        
        self.downloaded_count += 1
        self.stats['downloaded'] += 1
        
        logger.info(f"Descargado: {safe_filename} ({len(content)/1024:.1f}KB)")
        
        return metadata
    
    async def run(self):
        """Ejecutar el proceso completo de scraping"""
        logger.info("Iniciando scraper DOJ...")
        self.stats['start_time'] = datetime.now().isoformat()
        
        # Buscar documentos
        logger.info("Buscando documentos...")
        urls = await self.search_doj_press_releases()
        self.stats['total_found'] = len(urls)
        
        logger.info(f"Encontrados {len(urls)} documentos potenciales")
        
        # Descargar documentos
        download_tasks = []
        for url in urls:
            task = self.download_document(url)
            download_tasks.append(task)
            
            # Control de tasa de descargas
            if len(download_tasks) % 5 == 0:
                results = await asyncio.gather(*download_tasks, return_exceptions=True)
                download_tasks = []
                
                # Respetar rate limiting
                await asyncio.sleep(self.config['sources'][0]['rate_limit']['delay_between_requests'])
        
        # Procesar tareas restantes
        if download_tasks:
            await asyncio.gather(*download_tasks, return_exceptions=True)
        
        self.stats['end_time'] = datetime.now().isoformat()
        
        # Reporte final
        logger.info(f"Proceso completado. Estadísticas: {json.dumps(self.stats, indent=2)}")
        
        return self.stats

async def main():
    """Función principal"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async with DOJScraper() as scraper:
        stats = await scraper.run()
        return stats

if __name__ == "__main__":
    asyncio.run(main())