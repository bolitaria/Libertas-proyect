#!/usr/bin/env python3
"""
Orquestador para red P2P - G compartición descentralizada.
"""
import asyncio
import json
import hashlib
from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class P2POrchestrator:
    def __init__(self):
        self.peers = {}  # {peer_id: {ip: str, port: int, files: List[str]}}
        self.file_index = {}  # {file_hash: {peers: List[str], metadata: Dict}}
        self.announce_url = "http://tracker.libertas-p2p.org:6969/announce"
        
    async def announce_peer(self, peer_id: str, port: int, shared_files: List[str]):
        """Anuncia un peer a la red"""
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'peer_id': peer_id,
                    'port': port,
                    'uploaded': 0,
                    'downloaded': 0,
                    'left': 0,
                    'compact': 1,
                    'no_peer_id': 1,
                    'event': 'started',
                    'info_hash': hashlib.sha1(b'libertas_network').hexdigest()
                }
                
                async with session.get(self.announce_url, params=params) as response:
                    if response.status == 200:
                        data = await response.read()
                        # Parsear respuesta del tracker
                        peers = self.parse_tracker_response(data)
                        self.peers[peer_id] = {
                            'ip': '0.0.0.0',  # Sería la IP real
                            'port': port,
                            'files': shared_files,
                            'last_seen': datetime.now()
                        }
                        
                        # Actualizar índice de archivos
                        for file_hash in shared_files:
                            if file_hash not in self.file_index:
                                self.file_index[file_hash] = {'peers': [], 'metadata': {}}
                            self.file_index[file_hash]['peers'].append(peer_id)
                        
                        logger.info(f"Peer {peer_id} anunciado con {len(shared_files)} archivos")
                        return peers
        except Exception as e:
            logger.error(f"Error anunciando peer: {e}")
            return []
    
    def parse_tracker_response(self, data: bytes) -> List[Dict]:
        """Parsea respuesta del tracker BitTorrent"""
        import struct
        
        peers = []
        try:
            # Formato compacto: <ip (4 bytes)><port (2 bytes)>
            for i in range(0, len(data), 6):
                if i + 6 <= len(data):
                    ip_bytes = data[i:i+4]
                    port_bytes = data[i+4:i+6]
                    
                    ip = '.'.join(str(b) for b in ip_bytes)
                    port = struct.unpack(">H", port_bytes)[0]
                    
                    peers.append({'ip': ip, 'port': port})
        except:
            # Intentar formato no compacto
            try:
                decoded = json.loads(data.decode('utf-8', errors='ignore'))
                if 'peers' in decoded:
                    peers = decoded['peers']
            except:
                pass
        
        return peers
    
    async def search_file(self, file_hash: str) -> List[Dict]:
        """Busca archivos en la red P2P"""
        if file_hash in self.file_index:
            peers_info = []
            for peer_id in self.file_index[file_hash]['peers']:
                if peer_id in self.peers:
                    peer = self.peers[peer_id]
                    peers_info.append({
                        'peer_id': peer_id,
                        'ip': peer['ip'],
                        'port': peer['port'],
                        'last_seen': peer['last_seen']
                    })
            return peers_info
        return []
    
    async def sync_with_other_nodes(self, bootstrap_nodes: List[str]):
        """Sincroniza con otros nodos de la red"""
        import aiohttp
        
        for node_url in bootstrap_nodes:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{node_url}/api/p2p/peers") as response:
                        if response.status == 200:
                            remote_peers = await response.json()
                            
                            # Fusionar información de peers
                            for peer_id, peer_info in remote_peers.items():
                                if peer_id not in self.peers:
                                    self.peers[peer_id] = peer_info
                                    
                            logger.info(f"Sincronizado con {node_url}: {len(remote_peers)} peers")
            except Exception as e:
                logger.debug(f"No se pudo conectar a {node_url}: {e}")
    
    async def share_document(self, document_id: str, file_path: str):
        """Prepara un documento para compartir P2P"""
        import os
        
        # Calcular hash del archivo
        file_hash = self.calculate_file_hash(file_path)
        
        # Crear torrent file
        torrent_info = {
            'info': {
                'name': f"libertas_{document_id}",
                'length': os.path.getsize(file_path),
                'piece length': 262144,  # 256KB
                'pieces': self.calculate_piece_hashes(file_path),
                'private': 1  # Red privada
            },
            'announce': self.announce_url,
            'created by': 'Libertas P2P',
            'creation date': int(datetime.now().timestamp()),
            'encoding': 'UTF-8',
            'libertas_metadata': {
                'document_id': document_id,
                'source': 'epstein_doj',
                'encrypted': True,
                'requires_auth': True
            }
        }
        
        # Guardar archivo .torrent
        torrent_path = f"/data/torrents/{document_id}.torrent"
        with open(torrent_path, 'wb') as f:
            import bencodepy
            f.write(bencodepy.encode(torrent_info))
        
        # Registrar en índice local
        if file_hash not in self.file_index:
            self.file_index[file_hash] = {'peers': [], 'metadata': {}}
        
        # Añadir este peer como seeder
        peer_id = self.get_peer_id()
        self.file_index[file_hash]['peers'].append(peer_id)
        
        logger.info(f"Documento {document_id} preparado para P2P: {torrent_path}")
        return torrent_path
    
    def calculate_file_hash(self, file_path: str) -> str:
        """Calcula hash SHA-256 de un archivo"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def calculate_piece_hashes(self, file_path: str) -> str:
        """Calcula hashes de piezas para torrent"""
        import os
        piece_length = 262144
        piece_hashes = b''
        
        with open(file_path, 'rb') as f:
            while True:
                piece = f.read(piece_length)
                if not piece:
                    break
                piece_hashes += hashlib.sha1(piece).digest()
        
        return piece_hashes.hex()
    
    def get_peer_id(self) -> str:
        """Genera un ID único para este peer"""
        import socket
        hostname = socket.gethostname()
        timestamp = int(datetime.now().timestamp())
        return hashlib.md5(f"{hostname}_{timestamp}".encode()).hexdigest()[:20]
    
    async def run_tracker(self, port: int = 6969):
        """Ejecuta un tracker BitTorrent simple"""
        from aiohttp import web
        import asyncio
        
        async def handle_announce(request):
            """Maneja anuncios de peers"""
            params = request.query
            
            peer_id = params.get('peer_id', '')
            port = int(params.get('port', 6881))
            uploaded = int(params.get('uploaded', 0))
            downloaded = int(params.get('downloaded', 0))
            left = int(params.get('left', 0))
            event = params.get('event', '')
            
            # Registrar/actualizar peer
            self.peers[peer_id] = {
                'ip': request.remote,
                'port': port,
                'uploaded': uploaded,
                'downloaded': downloaded,
                'left': left,
                'last_announce': datetime.now()
            }
            
            # Responder con lista de peers
            peer_list = []
            for pid, info in self.peers.items():
                if pid != peer_id:  # No incluir al propio peer
                    peer_list.append({
                        'peer id': pid,
                        'ip': info['ip'],
                        'port': info['port']
                    })
            
            # Formato compacto para respuesta
            import struct
            response_data = b''
            for peer in peer_list[:50]:  # Limitar a 50 peers
                ip_parts = peer['ip'].split('.')
                response_data += struct.pack('!BBBBH', 
                    int(ip_parts[0]), int(ip_parts[1]), 
                    int(ip_parts[2]), int(ip_parts[3]), 
                    peer['port']
                )
            
            return web.Response(body=response_data, content_type='application/octet-stream')
        
        async def handle_scrape(request):
            """Maneja peticiones scrape (estadísticas)"""
            stats = {
                'files': {
                    'libertas_network': {
                        'complete': len([p for p in self.peers.values() if p['left'] == 0]),
                        'downloaded': sum(p['downloaded'] for p in self.peers.values()),
                        'incomplete': len([p for p in self.peers.values() if p['left'] > 0])
                    }
                }
            }
            
            import bencodepy
            return web.Response(
                body=bencodepy.encode(stats),
                content_type='application/octet-stream'
            )
        
        # Configurar servidor
        app = web.Application()
        app.router.add_get('/announce', handle_announce)
        app.router.add_get('/scrape', handle_scrape)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        
        logger.info(f"Tracker P2P iniciado en puerto {port}")
        await site.start()
        
        # Mantener el tracker corriendo
        while True:
            await asyncio.sleep(3600)  # Esperar 1 hora
    
    async def run(self):
        """Ejecuta el orquestador P2P"""
        logger.info("Iniciando orquestador P2P")
        
        # Iniciar tracker en segundo plano
        tracker_task = asyncio.create_task(self.run_tracker())
        
        # Sincronizar con nodos de bootstrap
        bootstrap_nodes = [
            "http://p2p1.libertas-project.org",
            "http://p2p2.libertas-project.org",
            "http://p2p3.libertas-project.org"
        ]
        
        while True:
            try:
                await self.sync_with_other_nodes(bootstrap_nodes)
                
                # Limpiar peers inactivos (más de 1 hora)
                current_time = datetime.now()
                inactive_peers = []
                for peer_id, peer_info in self.peers.items():
                    last_seen = peer_info.get('last_seen', peer_info.get('last_announce'))
                    if isinstance(last_seen, str):
                        last_seen = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                    
                    if (current_time - last_seen).seconds > 3600:
                        inactive_peers.append(peer_id)
                
                for peer_id in inactive_peers:
                    del self.peers[peer_id]
                    # Remover de índice de archivos
                    for file_hash in self.file_index:
                        if peer_id in self.file_index[file_hash]['peers']:
                            self.file_index[file_hash]['peers'].remove(peer_id)
                
                if inactive_peers:
                    logger.info(f"Limpiados {len(inactive_peers)} peers inactivos")
                
                # Publicar estadísticas
                stats = {
                    'total_peers': len(self.peers),
                    'total_files': len(self.file_index),
                    'active_seeders': len([p for p in self.peers.values() if p.get('left', 1) == 0])
                }
                
                logger.info(f"Estadísticas P2P: {stats}")
                
                await asyncio.sleep(300)  # Esperar 5 minutos
                
            except Exception as e:
                logger.error(f"Error en orquestador P2P: {e}")
                await asyncio.sleep(60)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    orchestrator = P2POrchestrator()
    asyncio.run(orchestrator.run())