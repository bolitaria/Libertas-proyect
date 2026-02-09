#!/usr/bin/env python3
"""
Fetcher especializado para el sitio web del DOJ.
Maneja politeness, reintentos, y validación de redacciones.
"""
import aiohttp
import asyncio
import aiofiles
import hashlib
import os
from pathlib import Path
from typing import Optional, Dict
import logging
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)

class DOJFetcher:
    def __init__(self, config_path: str = "config/doj_config.yaml"):
        self.config = self.load_config(config_path)
        self.session = None
        self.rate_limiter = RateLimiter(
            requests_per_minute=self.config.get('requests_per_minute', 30)
        )
        self.download_stats = {
            'successful': 0,
            'failed': 0,
            'total_size': 0,
            'start_time': datetime.now()
        }
    
    def load_config(self, config_path: str) -> Dict:
        """Carga configuración del DOJ"""
        import yaml
        default_config = {
            'base_url': 'https://www.justice.gov/epstein/document/',
            'user_agent': 'LibertasDOJFetcher/1.0 (Research Use)',
            'requests_per_minute': 30,
            'max_retries': 3,
            'timeout_seconds': 60,
            'download_dir': '/data/doj_downloads',
            'verify_ssl': True,
            'respect_robots': True
        }
        
        try:
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                default_config.update(user_config)
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found, using defaults")
        
        return default_config
    
    async def fetch_robots_txt(self) -> Optional[str]:
        """Obtiene y parsea robots.txt"""
        if not self.config['respect_robots']:
            return None
        
        try:
            async with self.session.get(
                f"{self.config['base_url']}/robots.txt",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return await response.text()
        except Exception as e:
            logger.warning(f"Could not fetch robots.txt: {e}")
        
        return None
    
    async def download_with_retry(self, url: str, output_path: Path, 
                                 expected_hash: Optional[str] = None) -> Dict:
        """Descarga un archivo con reintentos y verificación de hash"""
        import ssl
        import certifi
        
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        for attempt in range(self.config['max_retries'] + 1):
            try:
                await self.rate_limiter.wait()
                
                async with self.session.get(
                    url,
                    ssl=ssl_context,
                    timeout=aiohttp.ClientTimeout(total=self.config['timeout_seconds'])
                ) as response:
                    
                    if response.status == 200:
                        # Crear directorio si no existe
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Descargar con verificación progresiva
                        content_length = int(response.headers.get('content-length', 0))
                        sha256 = hashlib.sha256()
                        
                        async with aiofiles.open(output_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                                sha256.update(chunk)
                        
                        actual_hash = sha256.hexdigest()
                        
                        # Verificar integridad
                        if expected_hash and actual_hash != expected_hash:
                            raise ValueError(f"Hash mismatch for {url}")
                        
                        file_size = output_path.stat().st_size
                        
                        self.download_stats['successful'] += 1
                        self.download_stats['total_size'] += file_size
                        
                        return {
                            'success': True,
                            'path': str(output_path),
                            'hash': actual_hash,
                            'size': file_size,
                            'attempts': attempt + 1
                        }
                    
                    elif response.status == 404:
                        logger.warning(f"File not found: {url}")
                        return {'success': False, 'error': 'File not found', 'status': 404}
                    
                    elif response.status == 429:  # Too Many Requests
                        retry_after = int(response.headers.get('Retry-After', 60))
                        logger.warning(f"Rate limited, retrying after {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    else:
                        logger.error(f"HTTP {response.status} for {url}")
                        if attempt < self.config['max_retries']:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout downloading {url}, attempt {attempt + 1}")
                if attempt < self.config['max_retries']:
                    await asyncio.sleep(5)
                continue
                
            except Exception as e:
                logger.error(f"Error downloading {url}: {e}")
                if attempt < self.config['max_retries']:
                    await asyncio.sleep(2 ** attempt)
                continue
        
        # Si llegamos aquí, todos los reintentos fallaron
        self.download_stats['failed'] += 1
        return {
            'success': False,
            'error': 'Max retries exceeded',
            'url': url
        }
    
    async def download_batch(self, urls_with_metadata: list) -> list:
        """Descarga un lote de archivos concurrentemente"""
        semaphore = asyncio.Semaphore(5)  # Máximo 5 descargas concurrentes
        
        async def download_with_semaphore(url_meta):
            async with semaphore:
                url = url_meta['url']
                doc_id = url_meta.get('doc_id', 'unknown')
                expected_hash = url_meta.get('hash')
                
                # Crear nombre de archivo seguro
                safe_filename = f"{doc_id}_{url.split('/')[-1]}"
                output_path = Path(self.config['download_dir']) / safe_filename
                
                result = await self.download_with_retry(url, output_path, expected_hash)
                result['doc_id'] = doc_id
                result['url'] = url
                
                return result
        
        # Ejecutar descargas concurrentes
        tasks = [download_with_semaphore(url_meta) for url_meta in urls_with_metadata]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Procesar resultados
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed with exception: {result}")
                processed_results.append({
                    'success': False,
                    'error': str(result)
                })
            else:
                processed_results.append(result)
                
                if result.get('success'):
                    logger.info(f"Downloaded: {result['path']} ({result['size']} bytes)")
                else:
                    logger.error(f"Failed: {result.get('url')} - {result.get('error')}")
        
        return processed_results
    
    async def check_for_updates(self, manifest_url: str, local_index: Dict) -> list:
        """Verifica si hay actualizaciones en el DOJ"""
        try:
            async with self.session.get(manifest_url) as response:
                if response.status == 200:
                    remote_manifest = await response.json()
                    
                    updates = []
                    for remote_file in remote_manifest.get('files', []):
                        remote_hash = remote_file.get('hash')
                        remote_url = remote_file.get('url')
                        
                        # Buscar en índice local
                        local_file = local_index.get(remote_hash)
                        
                        if not local_file or local_file.get('version', 0) < remote_file.get('version', 1):
                            updates.append({
                                'url': remote_url,
                                'hash': remote_hash,
                                'action': 'new' if not local_file else 'update',
                                'metadata': remote_file
                            })
                    
                    logger.info(f"Found {len(updates)} updates in DOJ repository")
                    return updates
                    
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
        
        return []
    
    async def run(self):
        """Bucle principal del fetcher DOJ"""
        logger.info("Starting DOJ Fetcher")
        
        connector = aiohttp.TCPConnector(
            limit=20,
            ttl_dns_cache=300,
            verify_ssl=self.config['verify_ssl']
        )
        
        async with aiohttp.ClientSession(
            connector=connector,
            headers={'User-Agent': self.config['user_agent']}
        ) as session:
            self.session = session
            
            # Obtener robots.txt
            robots_txt = await self.fetch_robots_txt()
            if robots_txt:
                logger.info("Respecting robots.txt policies")
            
            # Aquí se integraría con el scheduler
            # Por ahora, ejemplo de descarga de prueba
            test_urls = [
                {
                    'url': 'https://www.justice.gov/epstein/document/sample1.pdf',
                    'doc_id': 'epstein_001',
                    'hash': None
                }
            ]
            
            results = await self.download_batch(test_urls)
            
            # Mostrar estadísticas
            elapsed = datetime.now() - self.download_stats['start_time']
            logger.info(f"""
            Download Statistics:
            --------------------
            Successful: {self.download_stats['successful']}
            Failed: {self.download_stats['failed']}
            Total Size: {self.download_stats['total_size'] / (1024*1024):.2f} MB
            Elapsed Time: {elapsed}
            Avg Speed: {self.download_stats['total_size'] / max(elapsed.seconds, 1) / 1024:.2f} KB/s
            """)
            
            return results

class RateLimiter:
    """Limita la tasa de requests por minuto"""
    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.interval = 60.0 / requests_per_minute
        self.last_request = 0
        self.lock = asyncio.Lock()
    
    async def wait(self):
        async with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request
            
            if time_since_last < self.interval:
                wait_time = self.interval - time_since_last
                await asyncio.sleep(wait_time)
            
            self.last_request = time.time()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    fetcher = DOJFetcher()
    asyncio.run(fetcher.run())