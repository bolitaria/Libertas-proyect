#!/usr/bin/env python3
"""
Nodo P2P para compartir documentos de forma descentralizada.
"""
import asyncio
import logging
import libtorrent as lt
import time
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import aiohttp
from aiohttp import web
import redis
import pickle

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class P2PNode:
    """Nodo P2P para compartir documentos"""
    
    def __init__(self, config_path: str = "config/p2p_config.yaml"):
        """Inicializar nodo P2P"""
        import yaml
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Configuración de sesión libtorrent
        self.session = lt.session()
        self.setup_session()
        
        # Torrents activos
        self.active_torrents: Dict[str, lt.torrent_handle] = {}
        self.torrent_info: Dict[str, Dict] = {}
        
        # Redis para coordinación
        self.redis_client = None
        
        # Directorios
        self.share_dir = Path(self.config['sharing']['share_directory'])
        self.download_dir = Path(self.config['sharing']['download_directory'])
        self.share_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Estadísticas
        self.stats = {
            'shared_files': 0,
            'downloaded_files': 0,
            'active_peers': 0,
            'total_upload': 0,
            'total_download': 0,
            'start_time': datetime.now().isoformat()
        }
        
        # API web
        self.app = web.Application()
        self.setup_routes()
    
    def setup_session(self):
        """Configurar sesión libtorrent"""
        # Configurar puertos
        listen_interfaces = f"0.0.0.0:{self.config['network']['port']}"
        self.session.listen_on(self.config['network']['port'], self.config['network']['port'] + 10)
        
        # Configuración de sesión
        settings = self.session.get_settings()
        
        # Optimizar para documentos
        settings['active_downloads'] = 5
        settings['active_seeds'] = 10
        settings['active_limit'] = 15
        settings['download_rate_limit'] = self.config['network'].get('max_download_speed', 0)
        settings['upload_rate_limit'] = self.config['network'].get('max_upload_speed', 0)
        settings['connections_limit'] = self.config['network'].get('max_peers', 50)
        
        self.session.set_settings(settings)
        
        # Añadir trackers DHT
        for tracker in self.config['network'].get('trackers', []):
            self.session.add_tracker({'url': tracker})
        
        # Añadir nodos DHT bootstrap
        for node in self.config['network'].get('dht_bootstrap_nodes', []):
            self.session.add_dht_node(node)
        
        # Iniciar DHT
        self.session.start_dht()
        self.session.start_lsd()
        self.session.start_upnp()
        self.session.start_natpmp()
    
    async def connect_redis(self):
        """Conectar a Redis"""
        try:
            import os
            redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
            self.redis_client = redis.from_url(redis_url)
            self.redis_client.ping()
            logger.info("✅ Conectado a Redis para coordinación P2P")
        except Exception as e:
            logger.error(f"❌ Error conectando a Redis: {e}")
            self.redis_client = None
    
    async def announce_to_network(self, info_hash: str, metadata: Dict):
        """Anunciar torrent a la red"""
        if not self.redis_client:
            return
        
        try:
            # Registrar en Redis
            key = f"p2p:torrent:{info_hash}"
            self.redis_client.hset(key, mapping={
                'info_hash': info_hash,
                'metadata': json.dumps(metadata),
                'announced_at': datetime.now().isoformat(),
                'node_id': self.config['network'].get('node_id', 'default')
            })
            
            # Añadir a lista de torrents activos
            self.redis_client.sadd('p2p:active_torrents', info_hash)
            
            logger.info(f"✅ Torrent anunciado a la red: {info_hash}")
        except Exception as e:
            logger.error(f"Error anunciando torrent: {e}")
    
    async def discover_torrents(self) -> List[Dict]:
        """Descubrir torrents disponibles en la red"""
        if not self.redis_client:
            return []
        
        try:
            torrent_ids = self.redis_client.smembers('p2p:active_torrents')
            torrents = []
            
            for torrent_id in torrent_ids:
                key = f"p2p:torrent:{torrent_id.decode()}"
                data = self.redis_client.hgetall(key)
                
                if data:
                    torrent_info = {
                        'info_hash': data[b'info_hash'].decode(),
                        'metadata': json.loads(data[b'metadata'].decode()),
                        'announced_at': data[b'announced_at'].decode(),
                        'node_id': data[b'node_id'].decode()
                    }
                    torrents.append(torrent_info)
            
            return torrents
        except Exception as e:
            logger.error(f"Error descubriendo torrents: {e}")
            return []
    
    def create_torrent(self, file_path: Path, description: str = "") -> Optional[lt.torrent_info]:
        """Crear torrent para un archivo"""
        try:
            if not file_path.exists():
                logger.error(f"Archivo no encontrado: {file_path}")
                return None
            
            # Crear metadatos del torrent
            fs = lt.file_storage()
            lt.add_files(fs, str(file_path))
            
            # Crear torrent
            t = lt.create_torrent(fs)
            t.set_creator("Libertas P2P Node")
            t.set_comment(description)
            
            # Añadir trackers
            for tracker in self.config['network'].get('trackers', []):
                t.add_tracker(tracker)
            
            # Configurar privacidad
            t.set_priv(True)  # Torrent privado
            
            # Generar torrent
            lt.set_piece_hashes(t, str(file_path.parent))
            torrent_data = t.generate()
            
            # Guardar archivo .torrent
            torrent_file = file_path.with_suffix('.torrent')
            with open(torrent_file, 'wb') as f:
                f.write(lt.bencode(torrent_data))
            
            logger.info(f"✅ Torrent creado: {torrent_file}")
            
            return lt.torrent_info(torrent_data)
        
        except Exception as e:
            logger.error(f"Error creando torrent: {e}")
            return None
    
    async def share_file(self, file_path: Path, metadata: Dict = None):
        """Compartir archivo a través de P2P"""
        try:
            logger.info(f"Compartiendo archivo: {file_path}")
            
            # Crear torrent
            ti = self.create_torrent(
                file_path,
                description=metadata.get('description', 'Libertas Document') if metadata else 'Libertas Document'
            )
            
            if not ti:
                return None
            
            # Añadir a la sesión
            params = {
                'ti': ti,
                'save_path': str(self.share_dir),
                'storage_mode': lt.storage_mode_t.storage_mode_sparse
            }
            
            handle = self.session.add_torrent(params)
            
            # Guardar información
            info_hash = str(handle.info_hash())
            self.active_torrents[info_hash] = handle
            
            torrent_info = {
                'file_path': str(file_path),
                'file_name': file_path.name,
                'file_size': file_path.stat().st_size,
                'info_hash': info_hash,
                'metadata': metadata or {},
                'added_at': datetime.now().isoformat(),
                'is_seeding': True
            }
            
            self.torrent_info[info_hash] = torrent_info
            
            # Anunciar a la red
            await self.announce_to_network(info_hash, torrent_info)
            
            self.stats['shared_files'] += 1
            
            logger.info(f"✅ Archivo compartido: {file_path.name} ({info_hash})")
            
            return info_hash
        
        except Exception as e:
            logger.error(f"Error compartiendo archivo: {e}")
            return None
    
    async def download_torrent(self, info_hash: str, metadata: Dict = None):
        """Descargar torrent por info_hash"""
        try:
            logger.info(f"Descargando torrent: {info_hash}")
            
            # Crear magnet link
            magnet_link = f"magnet:?xt=urn:btih:{info_hash}"
            
            if metadata and metadata.get('trackers'):
                for tracker in metadata['trackers']:
                    magnet_link += f"&tr={tracker}"
            
            # Añadir magnet a la sesión
            params = {
                'url': magnet_link,
                'save_path': str(self.download_dir),
                'storage_mode': lt.storage_mode_t.storage_mode_sparse
            }
            
            handle = self.session.add_torrent(params)
            
            # Guardar información
            self.active_torrents[info_hash] = handle
            
            download_info = {
                'info_hash': info_hash,
                'metadata': metadata or {},
                'added_at': datetime.now().isoformat(),
                'save_path': str(self.download_dir),
                'status': 'downloading'
            }
            
            self.torrent_info[info_hash] = download_info
            
            self.stats['downloaded_files'] += 1
            
            logger.info(f"✅ Descarga iniciada: {info_hash}")
            
            return info_hash
        
        except Exception as e:
            logger.error(f"Error descargando torrent: {e}")
            return None
    
    async def auto_share_new_documents(self):
        """Compartir automáticamente nuevos documentos"""
        if not self.config['sharing'].get('auto_share_new', False):
            return
        
        logger.info("Buscando nuevos documentos para compartir...")
        
        # Directorio de documentos procesados
        docs_dir = Path("/data/processed")
        
        for doc_file in docs_dir.glob("*.pdf"):
            # Verificar si ya está compartido
            doc_hash = self.calculate_file_hash(doc_file)
            shared_key = f"p2p:shared:{doc_hash}"
            
            if self.redis_client and self.redis_client.exists(shared_key):
                continue
            
            # Crear metadatos
            metadata_file = doc_file.with_suffix('.json')
            metadata = {}
            
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            
            # Compartir archivo
            info_hash = await self.share_file(doc_file, metadata)
            
            if info_hash and self.redis_client:
                # Marcar como compartido
                self.redis_client.setex(shared_key, 86400, info_hash)  # 24 horas
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Calcular hash del archivo"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    async def update_stats(self):
        """Actualizar estadísticas del nodo"""
        # Actualizar estadísticas de torrents activos
        total_upload = 0
        total_download = 0
        active_peers = 0
        
        for handle in self.active_torrents.values():
            try:
                status = handle.status()
                total_upload += status.total_payload_upload
                total_download += status.total_payload_download
                active_peers += status.num_peers
            except:
                continue
        
        self.stats.update({
            'active_peers': active_peers,
            'total_upload': total_upload,
            'total_download': total_download,
            'active_torrents': len(self.active_torrents),
            'updated_at': datetime.now().isoformat()
        })
        
        # Guardar en Redis
        if self.redis_client:
            self.redis_client.set('p2p:node:stats', json.dumps(self.stats))
    
    def setup_routes(self):
        """Configurar rutas de la API web"""
        
        async def handle_status(request):
            """Endpoint de estado del nodo"""
            await self.update_stats()
            return web.json_response(self.stats)
        
        async def handle_torrents(request):
            """Listar torrents activos"""
            torrents = list(self.torrent_info.values())
            return web.json_response({'torrents': torrents, 'count': len(torrents)})
        
        async def handle_share(request):
            """Compartir nuevo archivo"""
            try:
                data = await request.json()
                file_path = Path(data['file_path'])
                
                if not file_path.exists():
                    return web.json_response({'error': 'File not found'}, status=404)
                
                metadata = data.get('metadata', {})
                info_hash = await self.share_file(file_path, metadata)
                
                if info_hash:
                    return web.json_response({
                        'success': True,
                        'info_hash': info_hash,
                        'magnet': f"magnet:?xt=urn:btih:{info_hash}"
                    })
                else:
                    return web.json_response({'error': 'Failed to share file'}, status=500)
                    
            except Exception as e:
                return web.json_response({'error': str(e)}, status=500)
        
        async def handle_discover(request):
            """Descubrir torrents en la red"""
            torrents = await self.discover_torrents()
            return web.json_response({'torrents': torrents, 'count': len(torrents)})
        
        async def handle_download(request):
            """Descargar torrent"""
            try:
                data = await request.json()
                info_hash = data['info_hash']
                metadata = data.get('metadata', {})
                
                result = await self.download_torrent(info_hash, metadata)
                
                if result:
                    return web.json_response({
                        'success': True,
                        'info_hash': info_hash,
                        'status': 'download_started'
                    })
                else:
                    return web.json_response({'error': 'Failed to start download'}, status=500)
                    
            except Exception as e:
                return web.json_response({'error': str(e)}, status=500)
        
        # Registrar rutas
        self.app.router.add_get('/status', handle_status)
        self.app.router.add_get('/torrents', handle_torrents)
        self.app.router.add_get('/discover', handle_discover)
        self.app.router.add_post('/share', handle_share)
        self.app.router.add_post('/download', handle_download)
    
    async def run_web_server(self):
        """Ejecutar servidor web API"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', 6882)
        await site.start()
        
        logger.info(f"🌐 API P2P escuchando en http://0.0.0.0:6882")
    
    async def run(self):
        """Ejecutar nodo P2P"""
        logger.info("🚀 Iniciando nodo P2P...")
        
        # Conectar a Redis
        await self.connect_redis()
        
        # Iniciar servidor web
        await self.run_web_server()
        
        # Ciclo principal
        while True:
            try:
                # Actualizar estadísticas
                await self.update_stats()
                
                # Compartir automáticamente nuevos documentos
                await self.auto_share_new_documents()
                
                # Esperar antes de la siguiente iteración
                await asyncio.sleep(30)
                
            except KeyboardInterrupt:
                logger.info("🛑 Nodo P2P detenido por usuario")
                break
            except Exception as e:
                logger.error(f"💥 Error en ciclo principal: {e}")
                await asyncio.sleep(60)

async def main():
    """Punto de entrada principal"""
    node = P2PNode()
    await node.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Nodo P2P detenido")