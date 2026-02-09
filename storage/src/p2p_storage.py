#!/usr/bin/env python3
"""
Sistema de almacenamiento con capacidades P2P.
Permite compartir documentos entre usuarios de forma descentralizada.
"""
import os
import json
import hashlib
import asyncio
from typing import Dict, List, Optional
from pathlib import Path
import logging
from datetime import datetime
import sqlite3

logger = logging.getLogger(__name__)

class P2PStorage:
    def __init__(self, storage_root: str = "/data/p2p_storage"):
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        
        # Base de datos para metadatos P2P
        self.db_path = self.storage_root / "p2p_network.db"
        self.init_database()
        
        # Configuración P2P
        self.peer_id = self.generate_peer_id()
        self.shared_files = {}  # file_hash -> metadata
        self.connected_peers = {}  # peer_id -> connection_info
        
    def generate_peer_id(self) -> str:
        """Genera un ID único para este peer"""
        import socket
        import random
        
        hostname = socket.gethostname()
        timestamp = int(datetime.now().timestamp())
        random_suffix = random.randint(1000, 9999)
        
        peer_string = f"{hostname}_{timestamp}_{random_suffix}"
        return hashlib.sha256(peer_string.encode()).hexdigest()[:20]
    
    def init_database(self):
        """Inicializa la base de datos P2P"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de archivos compartidos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shared_files (
                file_hash TEXT PRIMARY KEY,
                original_name TEXT,
                file_size INTEGER,
                mime_type TEXT,
                encrypted BOOLEAN,
                encryption_key TEXT,
                shared_at TIMESTAMP,
                download_count INTEGER DEFAULT 0,
                peer_count INTEGER DEFAULT 1
            )
        ''')
        
        # Tabla de peers conocidos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS known_peers (
                peer_id TEXT PRIMARY KEY,
                ip_address TEXT,
                port INTEGER,
                last_seen TIMESTAMP,
                shared_files_count INTEGER DEFAULT 0,
                reputation_score INTEGER DEFAULT 50
            )
        ''')
        
        # Tabla de descargas P2P
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS p2p_downloads (
                download_id TEXT PRIMARY KEY,
                file_hash TEXT,
                source_peer TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                status TEXT,
                download_path TEXT,
                FOREIGN KEY (file_hash) REFERENCES shared_files(file_hash)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    async def share_file(self, file_path: Path, metadata: Dict) -> Dict:
        """Prepara un archivo para compartir P2P"""
        if not file_path.exists():
            return {'success': False, 'error': 'File not found'}
        
        # Calcular hash del archivo
        file_hash = self.calculate_file_hash(file_path)
        
        # Cifrar archivo (opcional)
        encrypted_path, encryption_key = await self.encrypt_file(file_path, file_hash)
        
        # Crear torrent file
        torrent_info = self.create_torrent_info(
            file_path=encrypted_path,
            file_hash=file_hash,
            metadata=metadata
        )
        
        # Guardar torrent file
        torrent_path = self.storage_root / "torrents" / f"{file_hash}.torrent"
        torrent_path.parent.mkdir(exist_ok=True)
        
        with open(torrent_path, 'wb') as f:
            import bencodepy
            f.write(bencodepy.encode(torrent_info))
        
        # Registrar en base de datos
        self.register_shared_file(
            file_hash=file_hash,
            original_name=file_path.name,
            file_size=file_path.stat().st_size,
            mime_type=self.get_mime_type(file_path),
            encrypted=bool(encryption_key),
            encryption_key=encryption_key,
            metadata=metadata
        )
        
        # Anunciar a la red P2P
        await self.announce_to_network(file_hash, torrent_path)
        
        return {
            'success': True,
            'file_hash': file_hash,
            'torrent_path': str(torrent_path),
            'magnet_link': self.create_magnet_link(file_hash, metadata.get('name')),
            'encrypted': bool(encryption_key)
        }
    
    async def encrypt_file(self, file_path: Path, file_hash: str) -> tuple:
        """Cifra un archivo para compartir seguro"""
        from cryptography.fernet import Fernet
        import base64
        
        # Generar clave de cifrado basada en el hash del archivo
        key_material = file_hash.encode() + b"libertas_p2p_salt"
        key = base64.urlsafe_b64encode(hashlib.sha256(key_material).digest())
        
        cipher = Fernet(key)
        
        # Leer y cifrar archivo
        with open(file_path, 'rb') as f:
            original_data = f.read()
        
        encrypted_data = cipher.encrypt(original_data)
        
        # Guardar cifrado
        encrypted_path = self.storage_root / "encrypted" / f"{file_hash}.enc"
        encrypted_path.parent.mkdir(exist_ok=True)
        
        with open(encrypted_path, 'wb') as f:
            f.write(encrypted_data)
        
        return encrypted_path, key.decode()
    
    def create_torrent_info(self, file_path: Path, file_hash: str, metadata: Dict) -> Dict:
        """Crea información para archivo torrent"""
        import os
        
        return {
            'info': {
                'name': metadata.get('name', f"libertas_{file_hash[:8]}"),
                'length': os.path.getsize(file_path),
                'piece length': 262144,  # 256KB
                'pieces': self.calculate_piece_hashes(file_path),
                'private': 1,
                'libertas_metadata': {
                    'document_id': metadata.get('document_id', ''),
                    'source': metadata.get('source', ''),
                    'classification': metadata.get('classification', {}),
                    'version': metadata.get('version', 1),
                    'requires_auth': metadata.get('requires_auth', True)
                }
            },
            'announce': 'http://tracker.libertas-p2p.org:6969/announce',
            'announce-list': [
                ['http://tracker.libertas-p2p.org:6969/announce'],
                ['udp://tracker.libertas-p2p.org:6969/announce']
            ],
            'created by': 'Libertas P2P v1.0',
            'creation date': int(datetime.now().timestamp()),
            'comment': 'Libertas P2P Network - Secure Document Sharing',
            'encoding': 'UTF-8'
        }
    
    def calculate_piece_hashes(self, file_path: Path) -> str:
        """Calcula hashes SHA1 de piezas para torrent"""
        piece_length = 262144
        piece_hashes = b''
        
        with open(file_path, 'rb') as f:
            while True:
                piece = f.read(piece_length)
                if not piece:
                    break
                piece_hashes += hashlib.sha1(piece).digest()
        
        return piece_hashes.hex()
    
    def create_magnet_link(self, file_hash: str, name: str) -> str:
        """Crea un enlace magnet para el archivo"""
        import base64
        import urllib.parse
        
        # Crear info_hash para magnet
        info_hash = file_hash[:40].lower()  # Tomar primeros 40 chars para BT
        
        magnet_parts = [
            f"magnet:?xt=urn:btih:{info_hash}",
            f"dn={urllib.parse.quote(name)}",
            "tr=http://tracker.libertas-p2p.org:6969/announce",
            "tr=udp://tracker.libertas-p2p.org:6969/announce",
            "ws=https://p2p.libertas-project.org/share/" + info_hash
        ]
        
        return '&'.join(magnet_parts)
    
    def register_shared_file(self, **kwargs):
        """Registra un archivo compartido en la base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO shared_files 
            (file_hash, original_name, file_size, mime_type, encrypted, 
             encryption_key, shared_at, download_count, peer_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            kwargs['file_hash'],
            kwargs['original_name'],
            kwargs['file_size'],
            kwargs['mime_type'],
            kwargs['encrypted'],
            kwargs.get('encryption_key'),
            datetime.now(),
            0,  # download_count
            1   # peer_count
        ))
        
        conn.commit()
        conn.close()
    
    async def announce_to_network(self, file_hash: str, torrent_path: Path):
        """Anuncia un archivo a la red P2P"""
        import aiohttp
        
        # Enviar a trackers
        trackers = [
            'http://tracker.libertas-p2p.org:6969/announce',
            'udp://tracker.libertas-p2p.org:6969/announce'
        ]
        
        for tracker in trackers:
            try:
                async with aiohttp.ClientSession() as session:
                    params = {
                        'info_hash': file_hash[:20],
                        'peer_id': self.peer_id,
                        'port': 6881,
                        'uploaded': 0,
                        'downloaded': 0,
                        'left': 0,
                        'compact': 1,
                        'event': 'started'
                    }
                    
                    async with session.get(tracker, params=params) as response:
                        if response.status == 200:
                            logger.info(f"Announced to {tracker}")
            except Exception as e:
                logger.debug(f"Could not announce to {tracker}: {e}")
        
        # Publicar en DHT si está disponible
        await self.publish_to_dht(file_hash)
    
    async def publish_to_dht(self, file_hash: str):
        """Publica en DHT distribuido"""
        try:
            import asyncio_dht
            from asyncio_dht import Node
            
            # Configurar nodo DHT
            node = await Node.create(
                node_id=self.peer_id.encode(),
                bootstrap_nodes=[
                    ('router.bittorrent.com', 6881),
                    ('dht.transmissionbt.com', 6881),
                    ('router.utorrent.com', 6881)
                ]
            )
            
            # Almacenar información en DHT
            await node.set(
                key=file_hash.encode(),
                value=json.dumps({
                    'peer_id': self.peer_id,
                    'timestamp': datetime.now().isoformat(),
                    'libertas_network': True
                }).encode()
            )
            
            logger.info(f"Published to DHT: {file_hash}")
            
        except ImportError:
            logger.warning("asyncio-dht not available, skipping DHT publishing")
        except Exception as e:
            logger.error(f"Error publishing to DHT: {e}")
    
    async def search_p2p(self, query: str, max_results: int = 50) -> List[Dict]:
        """Busca archivos en la red P2P"""
        results = []
        
        # Buscar en base de datos local
        local_results = self.search_local(query, max_results // 2)
        results.extend(local_results)
        
        # Buscar en DHT
        dht_results = await self.search_dht(query, max_results // 2)
        results.extend(dht_results)
        
        # Eliminar duplicados
        seen_hashes = set()
        unique_results = []
        
        for result in results:
            if result['file_hash'] not in seen_hashes:
                seen_hashes.add(result['file_hash'])
                unique_results.append(result)
        
        return unique_results[:max_results]
    
    def search_local(self, query: str, limit: int) -> List[Dict]:
        """Busca en base de datos local"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM shared_files 
            WHERE original_name LIKE ? OR file_hash LIKE ?
            ORDER BY shared_at DESC
            LIMIT ?
        ''', (f'%{query}%', f'%{query}%', limit))
        
        rows = cursor.fetchall()
        results = []
        
        for row in rows:
            results.append({
                'file_hash': row['file_hash'],
                'name': row['original_name'],
                'size': row['file_size'],
                'mime_type': row['mime_type'],
                'encrypted': bool(row['encrypted']),
                'shared_at': row['shared_at'],
                'download_count': row['download_count'],
                'peer_count': row['peer_count'],
                'source': 'local'
            })
        
        conn.close()
        return results
    
    async def search_dht(self, query: str, limit: int) -> List[Dict]:
        """Busca en DHT distribuido"""
        try:
            import asyncio_dht
            from asyncio_dht import Node
            
            node = await Node.create()
            
            # Buscar en DHT
            found_items = await node.get(query.encode())
            
            results = []
            for item in found_items[:limit]:
                try:
                    value = json.loads(item.value.decode())
                    if value.get('libertas_network'):
                        results.append({
                            'file_hash': item.key.decode(),
                            'name': f"DHT Result: {item.key.decode()[:8]}",
                            'size': 0,  # Desconocido desde DHT
                            'mime_type': 'application/octet-stream',
                            'encrypted': True,
                            'shared_at': value.get('timestamp'),
                            'download_count': 0,
                            'peer_count': 1,
                            'source': 'dht',
                            'peer_id': value.get('peer_id')
                        })
                except:
                    continue
            
            return results
            
        except ImportError:
            logger.warning("asyncio-dht not available, skipping DHT search")
            return []
        except Exception as e:
            logger.error(f"Error searching DHT: {e}")
            return []
    
    async def download_from_peer(self, file_hash: str, peer_id: str) -> Optional[Path]:
        """Descarga un archivo de un peer específico"""
        import aiohttp
        
        # Obtener información del peer
        peer_info = await self.get_peer_info(peer_id)
        if not peer_info:
            return None
        
        try:
            # Conectar al peer
            async with aiohttp.ClientSession() as session:
                # Solicitar archivo
                url = f"http://{peer_info['ip']}:{peer_info['port']}/download/{file_hash}"
                
                async with session.get(url, timeout=60) as response:
                    if response.status == 200:
                        # Descargar archivo
                        download_path = self.storage_root / "downloads" / file_hash
                        download_path.parent.mkdir(exist_ok=True)
                        
                        with open(download_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        
                        # Verificar hash
                        downloaded_hash = self.calculate_file_hash(download_path)
                        if downloaded_hash == file_hash:
                            logger.info(f"Downloaded {file_hash} from {peer_id}")
                            
                            # Registrar descarga
                            self.record_download(file_hash, peer_id, download_path)
                            
                            return download_path
                        else:
                            logger.error(f"Hash mismatch for {file_hash}")
                            download_path.unlink()
                            return None
        
        except Exception as e:
            logger.error(f"Error downloading from peer {peer_id}: {e}")
            return None
    
    async def get_peer_info(self, peer_id: str) -> Optional[Dict]:
        """Obtiene información de un peer"""
        # Buscar en base de datos local
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM known_peers WHERE peer_id = ?',
            (peer_id,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'peer_id': row['peer_id'],
                'ip': row['ip_address'],
                'port': row['port'],
                'last_seen': row['last_seen']
            }
        
        # Buscar en DHT
        try:
            import asyncio_dht
            from asyncio_dht import Node
            
            node = await Node.create()
            result = await node.get(peer_id.encode())
            
            if result:
                value = json.loads(result[0].value.decode())
                return {
                    'peer_id': peer_id,
                    'ip': value.get('ip', '0.0.0.0'),
                    'port': value.get('port', 6881),
                    'last_seen': value.get('timestamp')
                }
        
        except:
            pass
        
        return None
    
    def record_download(self, file_hash: str, source_peer: str, file_path: Path):
        """Registra una descarga P2P"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        download_id = hashlib.md5(
            f"{file_hash}_{source_peer}_{datetime.now().timestamp()}".encode()
        ).hexdigest()
        
        cursor.execute('''
            INSERT INTO p2p_downloads 
            (download_id, file_hash, source_peer, started_at, 
             completed_at, status, download_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            download_id,
            file_hash,
            source_peer,
            datetime.now(),
            datetime.now(),
            'completed',
            str(file_path)
        ))
        
        # Actualizar contador de descargas
        cursor.execute('''
            UPDATE shared_files 
            SET download_count = download_count + 1
            WHERE file_hash = ?
        ''', (file_hash,))
        
        conn.commit()
        conn.close()
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Calcula hash SHA-256 de un archivo"""
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def get_mime_type(self, file_path: Path) -> str:
        """Determina el tipo MIME de un archivo"""
        import mimetypes
        
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type or 'application/octet-stream'
    
    async def run_p2p_server(self, port: int = 6881):
        """Ejecuta servidor P2P para compartir archivos"""
        from aiohttp import web
        import aiofiles
        
        async def handle_download(request):
            """Maneja solicitudes de descarga"""
            file_hash = request.match_info.get('file_hash')
            
            if not file_hash:
                return web.Response(status=400, text="File hash required")
            
            # Verificar que tenemos el archivo
            file_path = self.find_local_file(file_hash)
            if not file_path or not file_path.exists():
                return web.Response(status=404, text="File not found")
            
            # Verificar autenticación si es requerida
            auth_token = request.headers.get('Authorization')
            if not await self.verify_download_auth(file_hash, auth_token):
                return web.Response(status=401, text="Authentication required")
            
            # Servir archivo
            return web.FileResponse(file_path)
        
        async def handle_peer_info(request):
            """Proporciona información de este peer"""
            info = {
                'peer_id': self.peer_id,
                'version': 'Libertas P2P v1.0',
                'shared_files': len(self.shared_files),
                'uptime': self.get_uptime(),
                'features': ['encrypted_sharing', 'dht', 'tracker']
            }
            
            return web.json_response(info)
        
        # Configurar aplicación web
        app = web.Application()
        app.router.add_get('/download/{file_hash}', handle_download)
        app.router.add_get('/peer', handle_peer_info)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        
        logger.info(f"P2P server started on port {port}")
        await site.start()
        
        # Mantener servidor corriendo
        while True:
            await asyncio.sleep(3600)
    
    def find_local_file(self, file_hash: str) -> Optional[Path]:
        """Busca un archivo local por hash"""
        # Buscar en archivos cifrados
        encrypted_path = self.storage_root / "encrypted" / f"{file_hash}.enc"
        if encrypted_path.exists():
            return encrypted_path
        
        # Buscar en otros directorios
        for root, dirs, files in os.walk(self.storage_root):
            for file in files:
                if file_hash in file:
                    return Path(root) / file
        
        return None
    
    async def verify_download_auth(self, file_hash: str, auth_token: Optional[str]) -> bool:
        """Verifica autenticación para descarga"""
        # En una implementación real, esto verificaría tokens JWT o similares
        # Por ahora, permitir descargas locales sin autenticación
        
        # Verificar si es una solicitud local
        if auth_token == "local_trusted":
            return True
        
        # Verificar en base de datos si el archivo requiere autenticación
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT encrypted FROM shared_files WHERE file_hash = ?',
            (file_hash,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:  # Si está cifrado
            return auth_token is not None  # Requiere algún tipo de autenticación
        
        return True  # Archivos no cifrados son públicos
    
    def get_uptime(self) -> int:
        """Obtiene tiempo de actividad en segundos"""
        if hasattr(self, '_start_time'):
            return int((datetime.now() - self._start_time).total_seconds())
        return 0

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    storage = P2PStorage()
    
    # Ejemplo de uso
    async def example():
        # Compartir un archivo
        result = await storage.share_file(
            Path("/data/documents/epstein_doc1.pdf"),
            {
                'name': 'Epstein Document 1',
                'source': 'DOJ',
                'document_id': 'epstein_001',
                'classification': {'topics': ['legal', 'financial']},
                'requires_auth': True
            }
        )
        
        print(f"Shared file: {result}")
        
        # Buscar archivos
        results = await storage.search_p2p("epstein", 10)
        print(f"Found {len(results)} files")
        
        # Descargar un archivo
        if results:
            file_hash = results[0]['file_hash']
            peer_id = results[0].get('peer_id')
            
            if peer_id:
                downloaded = await storage.download_from_peer(file_hash, peer_id)
                print(f"Downloaded to: {downloaded}")
        
        # Iniciar servidor P2P
        await storage.run_p2p_server()
    
    asyncio.run(example())