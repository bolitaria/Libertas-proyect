#!/usr/bin/env python3
"""
Fetcher DOJ Epstein - Versión Completa con Control Total del Usuario
Descarga archivos de todos los datasets con selección flexible.
"""
import requests
import os
import time
import argparse
import sys
import json
import random
from urllib.parse import urljoin, urlparse
from pathlib import Path
import logging
from typing import Optional, Tuple, List, Dict, Any
import re
from datetime import datetime

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/data/logs/fetcher_enhanced.log')
    ]
)
logger = logging.getLogger(__name__)

class AdvancedEpsteinFetcher:
    def __init__(self, base_url="https://www.justice.gov"):
        self.base_url = base_url
        
        # Configurar directorios
        self.base_download_dir = Path("/data/downloads")
        self.raw_dir = self.base_download_dir / "raw"
        self.pdf_dir = self.raw_dir / "pdf"
        self.images_dir = self.raw_dir / "images"
        self.metadata_dir = self.base_download_dir / "metadata"
        
        # Asegurar directorios
        for dir_path in [self.pdf_dir, self.images_dir, self.metadata_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Inicializar sesión
        self.session = None
        self.initialize_session()
        
        # Cache de archivos descargados
        self.downloaded_cache = self._load_cache()
        
    def _load_cache(self) -> set:
        """Cargar cache de archivos descargados."""
        cache_file = self.metadata_dir / "downloaded_files.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('files', []))
            except:
                return set()
        return set()
    
    def _save_cache(self, filename: str = None):
        """Guardar cache."""
        cache_file = self.metadata_dir / "downloaded_files.json"
        cache_data = {
            'files': list(self.downloaded_cache),
            'last_updated': datetime.now().isoformat(),
            'total_files': len(self.downloaded_cache)
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        if filename:
            logger.debug(f"💾 Cache actualizado: {filename} añadido")
    
    def initialize_session(self):
        """Inicializar sesión con cookies correctas."""
        self.session = requests.Session()
        
        # Headers exactos del navegador
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Cookies críticas observadas
        cookies = {
            'justiceGovAgeVerified': 'true',
            'ak_bmsc': '349926C5815D1ED40C433455FCE597B6~000000000000000000000000000000~YAAQCVUQYHrI2yScAQAA7w1hPx6j8eHAKLmpImRNS73Pif3Unyr6XiaT0upqbR7msFhVKJzQqKgp5TcGKpGuCyWQoXwbhfMXOOrm4Qr2cugG8Ya11ZuInugrc/iqp74xJ5fm6sqiKgglSSB8L6BVgTNcNcuWUPWYskYsHHUV8fs6VgCKb0aybKt3MGojnCWxPITjzyPH07sp9qHECVuRI2ykZVSeIS+yWABVQW4t6TmnEcDZ8/4YXMxqRAAOqGyk7MXt1DHNWrKl8jzrrrURwdOwEkIsuBmg/lzQkBJyex0lx5sldDQxX+RPjEMWyF49TRESl1fPTdvPX0XZchszs4ZCrBg5Cq3diwDSY9JeRZ+KxR/S0DprHA5j2jkJjuTeZnxeSw==',
        }
        
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain='.justice.gov', path='/')
        
        logger.info("✅ Sesión inicializada con cookies válidas")
    
    def discover_all_files_in_dataset(self, dataset_num: int, max_pages: int = 50) -> List[Dict]:
        """
        Descubre TODOS los archivos en un dataset específico.
        """
        all_files = []
        page_num = 1
        consecutive_empty = 0
        
        logger.info(f"🔍 Explorando Dataset {dataset_num}...")
        
        while page_num <= max_pages and consecutive_empty < 3:
            url = f"{self.base_url}/epstein/doj-disclosures/data-set-{dataset_num}-files"
            if page_num > 1:
                url += f"?page={page_num}"
            
            try:
                response = self.session.get(url, timeout=30)
                if response.status_code != 200:
                    logger.warning(f"⚠️  Error en página {page_num}: {response.status_code}")
                    consecutive_empty += 1
                    page_num += 1
                    continue
                
                # Extraer enlaces
                file_links = self._extract_file_links(response.text, url)
                
                if not file_links:
                    consecutive_empty += 1
                    logger.debug(f"📭 Página {page_num} vacía")
                else:
                    consecutive_empty = 0
                    all_files.extend(file_links)
                    logger.info(f"   📄 Página {page_num}: {len(file_links)} archivos encontrados")
                
                page_num += 1
                time.sleep(0.5)  # Pausa corta
                
            except Exception as e:
                logger.error(f"❌ Error explorando página {page_num}: {e}")
                consecutive_empty += 1
        
        logger.info(f"✅ Dataset {dataset_num}: {len(all_files)} archivos encontrados")
        return all_files
    
    def discover_files_in_datasets(self, datasets: List[int], max_pages: int = 50) -> Dict[int, List[Dict]]:
        """
        Descubre archivos en múltiples datasets.
        """
        all_datasets_files = {}
        
        for dataset_num in datasets:
            files = self.discover_all_files_in_dataset(dataset_num, max_pages)
            all_datasets_files[dataset_num] = files
            
            # Pausa entre datasets
            if dataset_num != datasets[-1]:
                time.sleep(1)
        
        total_files = sum(len(files) for files in all_datasets_files.values())
        logger.info(f"📊 Total general: {total_files} archivos en {len(datasets)} datasets")
        
        return all_datasets_files
    
    def _extract_file_links(self, html_content: str, page_url: str) -> List[Dict]:
        """
        Extrae enlaces a archivos del HTML.
        """
        # Patrón mejorado para capturar enlaces
        patterns = [
            r'href="(https?://[^"]*?/epstein/files/[^"]+\.(pdf|jpg|jpeg|png|gif|bmp|tiff))"',
            r'href="(/epstein/files/[^"]+\.(pdf|jpg|jpeg|png|gif|bmp|tiff))"'
        ]
        
        file_links = []
        
        for pattern in patterns:
            matches = re.finditer(pattern, html_content, re.IGNORECASE)
            for match in matches:
                file_url = match.group(1)
                
                # Convertir URL relativa a absoluta si es necesario
                if file_url.startswith('/'):
                    file_url = urljoin(self.base_url, file_url)
                
                # Extraer información
                parsed_url = urlparse(file_url)
                filename = os.path.basename(parsed_url.path)
                file_ext = os.path.splitext(filename)[1].lower()
                
                # Determinar tipo
                file_type = 'pdf' if file_ext == '.pdf' else 'image'
                
                # Extraer dataset de la URL
                dataset_match = re.search(r'/DataSet\s*(\d+)/', file_url, re.IGNORECASE)
                dataset_num = int(dataset_match.group(1)) if dataset_match else 1
                
                file_info = {
                    'url': file_url,
                    'filename': filename,
                    'type': file_type,
                    'extension': file_ext,
                    'dataset': dataset_num,
                    'size_bytes': None
                }
                
                # Evitar duplicados
                if not any(f['filename'] == filename for f in file_links):
                    file_links.append(file_info)
        
        return file_links
    
    def select_files(self, all_files: List[Dict], selection_type: str = 'firsts', 
                    count: int = None, dataset_num: int = None) -> List[Dict]:
        """
        Selecciona archivos según criterio.
        
        Args:
            all_files: Lista completa de archivos
            selection_type: 'firsts', 'lasts', 'random', o 'all'
            count: Número de archivos a seleccionar
            dataset_num: Filtrar por dataset específico
        """
        # Filtrar por dataset si se especifica
        if dataset_num is not None:
            filtered_files = [f for f in all_files if f['dataset'] == dataset_num]
            logger.info(f"🎯 Filtrado dataset {dataset_num}: {len(filtered_files)} archivos")
        else:
            filtered_files = all_files
        
        # Eliminar archivos ya descargados
        available_files = [f for f in filtered_files if f['filename'] not in self.downloaded_cache]
        
        if not available_files:
            logger.warning("⚠️  No hay archivos nuevos disponibles")
            return []
        
        # Seleccionar según tipo
        if selection_type == 'firsts':
            selected = available_files[:count] if count else available_files
        elif selection_type == 'lasts':
            selected = available_files[-count:] if count else available_files
        elif selection_type == 'random':
            if count and count < len(available_files):
                selected = random.sample(available_files, count)
            else:
                selected = available_files
        elif selection_type == 'all':
            selected = available_files
        else:
            logger.error(f"❌ Tipo de selección inválido: {selection_type}")
            return []
        
        logger.info(f"🎯 Seleccionados {len(selected)} archivos (tipo: {selection_type})")
        return selected
    
    def download_file(self, file_info: Dict, force: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Descarga un archivo individual.
        """
        # Verificar cache (a menos que force sea True)
        if not force and file_info['filename'] in self.downloaded_cache:
            logger.debug(f"⏭️  Ya en caché: {file_info['filename']}")
            return False, None
        
        save_path = self.pdf_dir / file_info['filename'] if file_info['type'] == 'pdf' else self.images_dir / file_info['filename']
        
        # Verificar si ya existe físicamente
        if not force and save_path.exists():
            self.downloaded_cache.add(file_info['filename'])
            self._save_cache()
            return False, str(save_path)
        
        logger.info(f"⬇️  Descargando: {file_info['filename']}")
        
        try:
            # Headers específicos para descarga
            headers = {
                'Referer': f'{self.base_url}/epstein/doj-disclosures/data-set-{file_info["dataset"]}-files',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate, br',
            }
            
            response = self.session.get(
                file_info['url'],
                headers=headers,
                timeout=30,
                stream=True
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Error {response.status_code} para {file_info['filename']}")
                return False, None
            
            # Guardar archivo
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verificar tamaño
            file_size = save_path.stat().st_size
            if file_size == 0:
                logger.error(f"❌ Archivo vacío: {file_info['filename']}")
                save_path.unlink()
                return False, None
            
            # Verificar PDF válido si es PDF
            if file_info['type'] == 'pdf':
                with open(save_path, 'rb') as f:
                    header = f.read(5)
                    if header != b'%PDF-':
                        logger.error(f"❌ No es PDF válido: {file_info['filename']}")
                        save_path.unlink()
                        return False, None
            
            # Actualizar cache
            self.downloaded_cache.add(file_info['filename'])
            self._save_cache(file_info['filename'])
            
            file_info['size_bytes'] = file_size
            logger.info(f"✅ Descargado: {file_info['filename']} ({file_size:,} bytes)")
            return True, str(save_path)
            
        except Exception as e:
            logger.error(f"❌ Error descargando {file_info['filename']}: {e}")
            if save_path.exists():
                save_path.unlink()
            return False, None
    
    def download_selected_files(self, files_to_download: List[Dict], 
                              force: bool = False, 
                              delay: float = 1.0) -> Dict[str, Any]:
        """
        Descarga múltiples archivos.
        """
        results = {
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'total_size_bytes': 0,
            'files': [],
            'start_time': time.time()
        }
        
        for i, file_info in enumerate(files_to_download, 1):
            logger.info(f"📦 Progreso: {i}/{len(files_to_download)}")
            
            success, file_path = self.download_file(file_info, force)
            
            if success:
                results['successful'] += 1
                results['total_size_bytes'] += file_info.get('size_bytes', 0)
                results['files'].append({
                    'filename': file_info['filename'],
                    'path': file_path,
                    'dataset': file_info['dataset'],
                    'size_bytes': file_info.get('size_bytes')
                })
            elif file_path:  # Ya existía
                results['skipped'] += 1
            else:
                results['failed'] += 1
            
            # Pausa entre descargas (excepto la última)
            if i < len(files_to_download):
                time.sleep(delay)
        
        results['end_time'] = time.time()
        results['duration_seconds'] = results['end_time'] - results['start_time']
        
        return results
    
    def clean_downloads(self, confirm: bool = True) -> bool:
        """
        Limpia todos los archivos descargados y resetea el cache.
        
        Args:
            confirm: Pedir confirmación al usuario
        """
        if confirm:
            print("\n⚠️  ADVERTENCIA: Esto eliminará TODOS los archivos descargados.")
            print(f"   PDFs: {self.pdf_dir}")
            print(f"   Imágenes: {self.images_dir}")
            response = input("\n¿Continuar? (sí/no): ").strip().lower()
            if response not in ['si', 'sí', 'yes', 'y']:
                logger.info("❌ Limpieza cancelada por el usuario")
                return False
        
        try:
            # Eliminar archivos PDF
            pdf_count = 0
            for pdf_file in self.pdf_dir.glob("*.pdf"):
                pdf_file.unlink()
                pdf_count += 1
            
            # Eliminar imágenes
            img_count = 0
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp', '*.tiff']:
                for img_file in self.images_dir.glob(ext):
                    img_file.unlink()
                    img_count += 1
            
            # Resetear cache
            self.downloaded_cache.clear()
            self._save_cache()
            
            # Eliminar archivos de metadata antiguos
            for meta_file in self.metadata_dir.glob("session_*.json"):
                if meta_file.name != "downloaded_files.json":
                    meta_file.unlink()
            
            logger.info(f"🧹 Limpieza completada: {pdf_count} PDFs y {img_count} imágenes eliminados")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error durante la limpieza: {e}")
            return False
    
    def get_download_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de descargas."""
        pdf_files = list(self.pdf_dir.glob("*.pdf"))
        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif']:
            image_files.extend(self.images_dir.glob(ext))
        
        total_size = 0
        for pdf in pdf_files:
            total_size += pdf.stat().st_size
        
        return {
            'pdf_count': len(pdf_files),
            'image_count': len(image_files),
            'total_files': len(pdf_files) + len(image_files),
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'cached_files': len(self.downloaded_cache)
        }
    
    def run_complete_pipeline(self, datasets: List[int], 
                            selection_type: str = 'firsts',
                            file_count: int = None,
                            force: bool = False,
                            delay: float = 1.0) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo.
        """
        logger.info("🚀 Iniciando pipeline de descarga completo")
        logger.info(f"📊 Parámetros: datasets={datasets}, selección={selection_type}, cantidad={file_count}")
        
        # 1. Descubrir archivos
        all_datasets_files = self.discover_files_in_datasets(datasets)
        
        # Aplanar lista de archivos
        all_files = []
        for dataset_files in all_datasets_files.values():
            all_files.extend(dataset_files)
        
        if not all_files:
            logger.error("❌ No se encontraron archivos")
            return {'error': 'No files found'}
        
        # 2. Seleccionar archivos
        selected_files = self.select_files(
            all_files, 
            selection_type=selection_type,
            count=file_count,
            dataset_num=None  # Todos los datasets
        )
        
        if not selected_files:
            logger.warning("⚠️  No hay archivos nuevos para descargar")
            return {'warning': 'No new files to download'}
        
        # 3. Descargar archivos
        download_results = self.download_selected_files(
            selected_files, 
            force=force,
            delay=delay
        )
        
        # 4. Guardar metadatos de la sesión
        session_data = {
            'timestamp': datetime.now().isoformat(),
            'parameters': {
                'datasets': datasets,
                'selection_type': selection_type,
                'file_count': file_count,
                'force': force
            },
            'results': download_results,
            'stats': self.get_download_stats()
        }
        
        session_file = self.metadata_dir / f"session_{int(time.time())}.json"
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        
        # 5. Mostrar resumen
        self._print_summary(download_results)
        
        return session_data
    
    def _print_summary(self, results: Dict[str, Any]):
        """Imprime un resumen de los resultados."""
        print("\n" + "="*60)
        print("📊 RESUMEN DE DESCARGA")
        print("="*60)
        print(f"✅ Exitosas: {results['successful']}")
        print(f"⏭️  Saltadas: {results['skipped']}")
        print(f"❌ Fallidas: {results['failed']}")
        print(f"📦 Total tamaño: {results['total_size_bytes']:,} bytes")
        print(f"⏱️  Duración: {results['duration_seconds']:.1f} segundos")
        print(f"📁 PDFs descargados: {self.get_download_stats()['pdf_count']}")
        print("="*60)

def main():
    """Función principal con interfaz de línea de comandos."""
    parser = argparse.ArgumentParser(
        description='Fetcher avanzado para archivos DOJ Epstein - Control total de descargas',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Descargar primeros 100 archivos de todos los datasets
  python main.py --datasets 1 2 3 4 5 --count 100 --selection firsts
  
  # Descargar últimos 50 archivos del dataset 2
  python main.py --datasets 2 --count 50 --selection lasts
  
  # Descargar 30 archivos aleatorios del dataset 3
  python main.py --datasets 3 --count 30 --selection random
  
  # Descargar TODOS los archivos del dataset 1
  python main.py --datasets 1 --selection all
  
  # Limpiar todos los archivos descargados
  python main.py --clean
  
  # Forzar redescarga (ignorar cache)
  python main.py --datasets 1 --count 10 --force
  
  # Ver estadísticas actuales
  python main.py --stats
        """
    )
    
    parser.add_argument('--datasets', type=int, nargs='+', default=[1, 2],
                       help='Números de datasets a procesar (por defecto: 1 2)')
    
    parser.add_argument('--count', type=int,
                       help='Número de archivos a descargar (si no se especifica, descarga todos los disponibles)')
    
    parser.add_argument('--selection', choices=['firsts', 'lasts', 'random', 'all'], default='firsts',
                       help='Tipo de selección: primeros, últimos, aleatorios o todos (por defecto: firsts)')
    
    parser.add_argument('--force', action='store_true',
                       help='Forzar redescarga incluso si el archivo ya existe')
    
    parser.add_argument('--clean', action='store_true',
                       help='Limpiar todos los archivos descargados')
    
    parser.add_argument('--stats', action='store_true',
                       help='Mostrar estadísticas de descargas actuales')
    
    parser.add_argument('--delay', type=float, default=3.0,
                       help='Delay entre descargas en segundos (por defecto: 3.0)')
    
    parser.add_argument('--max-pages', type=int, default=50,
                       help='Máximo de páginas a explorar por dataset (por defecto: 50)')
    
    args = parser.parse_args()
    
    # Mostrar banner
    print("\n" + "="*60)
    print("🕊️  LIBERTAS PROJECT - FETCHER DOJ EPSTEIN AVANZADO")
    print("="*60)
    
    try:
        fetcher = AdvancedEpsteinFetcher()
        
        # Modo estadísticas
        if args.stats:
            stats = fetcher.get_download_stats()
            print("\n📊 ESTADÍSTICAS ACTUALES")
            print(f"   PDFs descargados: {stats['pdf_count']}")
            print(f"   Imágenes descargadas: {stats['image_count']}")
            print(f"   Archivos en cache: {stats['cached_files']}")
            print(f"   Tamaño total: {stats['total_size_mb']:.2f} MB")
            return
        
        # Modo limpieza
        if args.clean:
            fetcher.clean_downloads(confirm=True)
            return
        
        # Modo descarga
        print(f"\n🎯 Configuración:")
        print(f"   Datasets: {args.datasets}")
        print(f"   Selección: {args.selection}")
        print(f"   Cantidad: {args.count if args.count else 'Todos'}")
        print(f"   Forzar: {'Sí' if args.force else 'No'}")
        print()
        
        # Ejecutar pipeline
        results = fetcher.run_complete_pipeline(
            datasets=args.datasets,
            selection_type=args.selection,
            file_count=args.count,
            force=args.force,
            delay=args.delay
        )
        
        # Mostrar ubicación de archivos
        stats = fetcher.get_download_stats()
        print(f"\n📁 Archivos guardados en:")
        print(f"   PDFs: {fetcher.pdf_dir}")
        print(f"   Imágenes: {fetcher.images_dir}")
        print(f"   Metadatos: {fetcher.metadata_dir}")
        
        if stats['total_files'] > 0:
            print(f"\n✅ Proceso completado exitosamente!")
        else:
            print(f"\nℹ️  No se descargaron archivos nuevos.")
        
    except KeyboardInterrupt:
        print("\n⏹️  Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()