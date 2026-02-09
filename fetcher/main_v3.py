#!/usr/bin/env python3
"""
DOJ Epstein Documents Archiver - Versión Sin Límites
Un archivo que intenta descubrir TODOS los datasets y páginas disponibles.
Features: Sin límites en datasets o páginas, descubrimiento automático.
"""
import requests
import os
import time
import argparse
import sys
import json
import random
import hashlib
from urllib.parse import urljoin, urlparse
from pathlib import Path
import logging
from typing import Optional, Tuple, List, Dict, Any, Set
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum
import shutil

# ==================== CONFIGURATION ====================
class DownloadStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class FileMetadata:
    """Metadata for a discovered file"""
    url: str
    filename: str
    dataset: int
    discovered_at: str
    last_checked: Optional[str] = None
    status: DownloadStatus = DownloadStatus.PENDING
    download_path: Optional[str] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    download_attempts: int = 0
    last_error: Optional[str] = None
    downloaded_at: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        data['status'] = DownloadStatus(data['status'])
        return cls(**data)

@dataclass
class CacheState:
    """Global cache state"""
    version: str = "2.0"  # Updated version
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    files: Dict[str, FileMetadata] = field(default_factory=dict)
    datasets_scanned: Set[int] = field(default_factory=set)
    max_dataset_found: int = 0
    total_discovered: int = 0
    total_downloaded: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    
    def to_serializable(self):
        """Convert to JSON-serializable dict"""
        result = asdict(self)
        result['files'] = {url: meta.to_dict() for url, meta in self.files.items()}
        result['datasets_scanned'] = list(self.datasets_scanned)
        return result
    
    @classmethod
    def from_dict(cls, data):
        """Create from dict"""
        files = {url: FileMetadata.from_dict(meta) 
                for url, meta in data.get('files', {}).items()}
        datasets_scanned = set(data.get('datasets_scanned', []))
        
        obj = cls(
            version=data.get('version', '2.0'),
            created_at=data.get('created_at'),
            last_updated=data.get('last_updated'),
            files=files,
            datasets_scanned=datasets_scanned,
            max_dataset_found=data.get('max_dataset_found', 0),
            total_discovered=data.get('total_discovered', 0),
            total_downloaded=data.get('total_downloaded', 0),
            total_failed=data.get('total_failed', 0),
            total_skipped=data.get('total_skipped', 0)
        )
        return obj

# ==================== LOGGING SETUP ====================
def setup_logging(log_dir: Path) -> logging.Logger:
    """Configure comprehensive logging system"""
    logger = logging.getLogger("EpsteinArchiver")
    
    if logger.hasHandlers():
        logger.handlers.clear()
    
    logger.setLevel(logging.DEBUG)
    
    # Formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # File handler
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"archive_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    return logger

# ==================== MAIN ARCHIVER CLASS ====================
class UnlimitedEpsteinArchiver:
    """Archiver without limits on datasets or pages"""
    
    def __init__(self, base_url: str = "https://www.justice.gov"):
        self.base_url = base_url.rstrip('/')
        self.base_dir = Path("/data/downloads")
        
        # Directory structure
        self.raw_base_dir = self.base_dir / "raw"
        self.metadata_dir = self.base_dir / "metadata"
        self.cache_dir = self.base_dir / "cache"
        self.log_dir = self.base_dir / "logs"
        
        # Ensure directories exist
        for dir_path in [self.raw_base_dir, self.metadata_dir, self.cache_dir, self.log_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.logger = setup_logging(self.log_dir)
        
        # Cache files
        self.cache_file = self.cache_dir / "archive_cache.json"
        self.backup_cache_file = self.cache_dir / "archive_cache_backup.json"
        
        # Session and state
        self.session = self._init_session()
        self.cache = self._load_cache()
        
        self.logger.info("🚀 Unlimited Epstein Archiver Initialized")
        self.logger.info(f"📁 No dataset or page limits - will discover everything available")
    
    def _init_session(self) -> requests.Session:
        """Initialize HTTP session with realistic headers"""
        session = requests.Session()
        
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
        })
        
        session.cookies.set('justiceGovAgeVerified', 'true', 
                           domain='.justice.gov', path='/')
        
        return session
    
    def _get_dataset_dir(self, dataset_num: int) -> Path:
        """Get the directory path for a specific dataset"""
        dataset_dir = self.raw_base_dir / f"dataset{dataset_num}"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        return dataset_dir
    
    def _load_cache(self) -> CacheState:
        """Load persistent cache from disk"""
        if not self.cache_file.exists():
            self.logger.info("🆕 No cache found, creating new cache state")
            return CacheState()
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cache = CacheState.from_dict(data)
            self.logger.info(f"📂 Cache loaded: {len(cache.files)} files, "
                           f"max dataset found: {cache.max_dataset_found}")
            return cache
            
        except Exception as e:
            self.logger.warning(f"⚠️ Cache corrupted: {e}")
            return CacheState()
    
    def _save_cache(self):
        """Save cache to disk with backup"""
        try:
            self.cache.last_updated = datetime.now().isoformat()
            
            if self.cache_file.exists():
                shutil.copy2(self.cache_file, self.backup_cache_file)
            
            serializable = self.cache.to_serializable()
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(serializable, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"💾 Cache saved")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to save cache: {e}")
    
    def _respectful_delay(self, min_seconds: float = 2.0, max_seconds: float = 5.0) -> None:
        """Add variable delay between requests"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def _make_request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """Make HTTP request with error handling"""
        self._respectful_delay()
        
        if 'timeout' not in kwargs:
            kwargs['timeout'] = (30, 60)
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Stop on 403
            if response.status_code == 403:
                self.logger.warning(f"🔒 Access blocked (403) at {url}")
                return None
            
            return response
            
        except requests.exceptions.Timeout:
            self.logger.error(f"⏱️ Request timeout for {url}")
            return None
        except Exception as e:
            self.logger.error(f"🌐 Network error for {url}: {e}")
            return None
    
    def _extract_file_links(self, html: str, page_url: str, dataset_num: int) -> List[FileMetadata]:
        """Extract file links from HTML"""
        files = []
        patterns = [
            r'href="(/epstein/files/[^"]+\.pdf[^"]*)"',
            r'href="(https?://[^"]*?/epstein/files/[^"]+\.pdf[^"]*)"',
            r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, html, re.IGNORECASE)
            for match in matches:
                file_url = match.group(1)
                
                if file_url.startswith('/'):
                    file_url = f"{self.base_url}{file_url}"
                elif not file_url.startswith('http'):
                    file_url = urljoin(page_url, file_url)
                
                file_url = file_url.replace(' ', '%20')
                
                try:
                    parsed = urlparse(file_url)
                    filename = os.path.basename(parsed.path)
                    
                    if not filename or not filename.lower().endswith('.pdf'):
                        continue
                    
                    filename_lower = filename.lower()
                    if any(unwanted in filename_lower for unwanted in 
                           ['icon', 'logo', 'favicon', 'button', 'arrow', 'small', 'tiny']):
                        continue
                    
                    filename = requests.utils.unquote(filename)
                    
                    metadata = FileMetadata(
                        url=file_url,
                        filename=filename,
                        dataset=dataset_num,
                        discovered_at=datetime.now().isoformat()
                    )
                    
                    files.append(metadata)
                    
                except Exception:
                    continue
        
        return files
    
    def discover_all_datasets(self, start_from: int = 1, max_consecutive_failures: int = 10) -> List[int]:
        """
        Discover ALL available datasets automatically
        Returns list of dataset numbers that exist
        """
        self.logger.info(f"🔍 Starting automatic dataset discovery from {start_from}")
        
        existing_datasets = []
        consecutive_failures = 0
        current_dataset = start_from
        
        while consecutive_failures < max_consecutive_failures:
            url = f"{self.base_url}/epstein/doj-disclosures/data-set-{current_dataset}-files"
            
            self.logger.info(f"  Testing Dataset {current_dataset}...")
            
            try:
                response = self._make_request('GET', url)
                
                if response is None:  # 403
                    self.logger.warning(f"    ⏹️ Dataset {current_dataset}: Access blocked")
                    consecutive_failures += 1
                elif response.status_code == 200:
                    self.logger.info(f"    ✅ Dataset {current_dataset} exists")
                    existing_datasets.append(current_dataset)
                    consecutive_failures = 0
                    
                    # Update max dataset found
                    if current_dataset > self.cache.max_dataset_found:
                        self.cache.max_dataset_found = current_dataset
                elif response.status_code == 404:
                    self.logger.info(f"    📭 Dataset {current_dataset} does not exist")
                    consecutive_failures += 1
                else:
                    self.logger.warning(f"    ⚠️ Dataset {current_dataset}: HTTP {response.status_code}")
                    consecutive_failures += 1
                
            except Exception as e:
                self.logger.error(f"    ❌ Error testing dataset {current_dataset}: {e}")
                consecutive_failures += 1
            
            current_dataset += 1
            
            # Save progress every 10 datasets
            if current_dataset % 10 == 0:
                self._save_cache()
        
        self.logger.info(f"✅ Dataset discovery complete: Found {len(existing_datasets)} datasets")
        self._save_cache()
        
        return existing_datasets
    
    def discover_dataset_pages(self, dataset_num: int, max_pages: int = 1000) -> List[FileMetadata]:
        """
        Discover ALL pages for a dataset
        Continues until no more pages or access blocked
        """
        self.logger.info(f"🔍 Discovering ALL pages for Dataset {dataset_num}")
        
        all_files = []
        page = 0
        consecutive_empty_pages = 0
        max_consecutive_empty = 3
        
        while page < max_pages and consecutive_empty_pages < max_consecutive_empty:
            if page == 0:
                url = f"{self.base_url}/epstein/doj-disclosures/data-set-{dataset_num}-files"
                referer = f"{self.base_url}/epstein/doj-disclosures"
            else:
                url = f"{self.base_url}/epstein/doj-disclosures/data-set-{dataset_num}-files?page={page}"
                referer = f"{self.base_url}/epstein/doj-disclosures/data-set-{dataset_num}-files?page={page-1}"
            
            self.logger.info(f"  📄 Page {page}")
            
            try:
                response = self._make_request('GET', url)
                
                if response is None:  # 403
                    self.logger.warning(f"    🔒 Access blocked at page {page}. Stopping.")
                    break
                
                if response.status_code == 200:
                    files = self._extract_file_links(response.text, url, dataset_num)
                    
                    if files:
                        # Filter out duplicates in this page
                        unique_files = []
                        seen_urls = set()
                        for f in files:
                            if f.url not in seen_urls:
                                seen_urls.add(f.url)
                                unique_files.append(f)
                        
                        all_files.extend(unique_files)
                        self.logger.info(f"    ✅ Found {len(unique_files)} files")
                        consecutive_empty_pages = 0
                    else:
                        self.logger.info(f"    📭 No files on page {page}")
                        consecutive_empty_pages += 1
                        
                elif response.status_code == 404:
                    self.logger.info(f"    📭 Page {page} does not exist. Stopping.")
                    break
                else:
                    self.logger.warning(f"    ⚠️ HTTP {response.status_code} on page {page}")
                    consecutive_empty_pages += 1
                
            except Exception as e:
                self.logger.error(f"    ❌ Error on page {page}: {e}")
                consecutive_empty_pages += 1
            
            page += 1
        
        # Remove global duplicates
        unique_files = []
        seen_urls = set()
        for file_meta in all_files:
            if file_meta.url not in seen_urls:
                seen_urls.add(file_meta.url)
                unique_files.append(file_meta)
        
        # Filter out files already in cache
        new_files = []
        for file_meta in unique_files:
            if file_meta.url not in self.cache.files:
                new_files.append(file_meta)
            else:
                existing = self.cache.files[file_meta.url]
                existing.last_checked = datetime.now().isoformat()
        
        if unique_files:
            self.logger.info(f"✅ Dataset {dataset_num}: {len(unique_files)} unique files ({len(new_files)} new) across {page} pages")
        else:
            self.logger.warning(f"⚠️ Dataset {dataset_num}: No files found")
        
        # Add new files to cache
        for file_meta in new_files:
            self.cache.files[file_meta.url] = file_meta
            self.cache.total_discovered += 1
        
        self.cache.datasets_scanned.add(dataset_num)
        self._save_cache()
        
        return new_files
    
    def _calculate_checksum(self, filepath: Path) -> str:
        """Calculate MD5 checksum"""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _verify_pdf(self, filepath: Path) -> bool:
        """Verify file is a valid PDF"""
        try:
            with open(filepath, 'rb') as f:
                header = f.read(5)
                return header == b'%PDF-'
        except Exception:
            return False
    
    def download_file(self, file_meta: FileMetadata) -> Tuple[bool, Optional[str]]:
        """Download a single file"""
        dataset_dir = self._get_dataset_dir(file_meta.dataset)
        
        # Check if already downloaded
        if (file_meta.status == DownloadStatus.SUCCESS and 
            file_meta.download_path and 
            Path(file_meta.download_path).exists()):
            return False, file_meta.download_path
        
        # Check local directory
        local_file = dataset_dir / file_meta.filename
        if local_file.exists():
            if self._verify_pdf(local_file):
                file_meta.status = DownloadStatus.SUCCESS
                file_meta.download_path = str(local_file)
                file_meta.file_size = local_file.stat().st_size
                file_meta.checksum = self._calculate_checksum(local_file)
                file_meta.downloaded_at = datetime.now().isoformat()
                self.cache.total_skipped += 1
                return False, str(local_file)
        
        # Prepare download
        file_meta.download_attempts += 1
        file_meta.last_checked = datetime.now().isoformat()
        
        self.logger.info(f"⬇️ Downloading [{file_meta.download_attempts}]: {file_meta.filename}")
        
        temp_path = dataset_dir / f"{file_meta.filename}.tmp"
        
        try:
            headers = {
                'Referer': f"{self.base_url}/epstein/doj-disclosures/data-set-{file_meta.dataset}-files",
                'Accept': '*/*'
            }
            
            response = self._make_request('GET', file_meta.url, headers=headers, stream=True)
            
            if response is None or response.status_code != 200:
                error_msg = f"HTTP {response.status_code if response else 'Blocked'}"
                file_meta.last_error = error_msg
                file_meta.status = DownloadStatus.FAILED
                self.cache.total_failed += 1
                return False, None
            
            # Download
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Verify
            if not self._verify_pdf(temp_path):
                temp_path.unlink(missing_ok=True)
                file_meta.last_error = "Invalid PDF"
                file_meta.status = DownloadStatus.FAILED
                self.cache.total_failed += 1
                return False, None
            
            file_size = temp_path.stat().st_size
            if file_size < 1024:
                temp_path.unlink(missing_ok=True)
                file_meta.last_error = "File too small"
                file_meta.status = DownloadStatus.FAILED
                self.cache.total_failed += 1
                return False, None
            
            # Finalize
            final_path = dataset_dir / file_meta.filename
            temp_path.rename(final_path)
            
            file_meta.status = DownloadStatus.SUCCESS
            file_meta.download_path = str(final_path)
            file_meta.file_size = file_size
            file_meta.checksum = self._calculate_checksum(final_path)
            file_meta.downloaded_at = datetime.now().isoformat()
            file_meta.last_error = None
            
            self.cache.total_downloaded += 1
            
            self.logger.info(f"✅ Downloaded: {file_meta.filename} ({file_size:,} bytes)")
            return True, str(final_path)
            
        except Exception as e:
            error_msg = str(e)
            file_meta.last_error = error_msg
            file_meta.status = DownloadStatus.FAILED
            self.cache.total_failed += 1
            
            temp_path.unlink(missing_ok=True)
            
            return False, None
    
    def process_dataset(self, dataset_num: int, download: bool = True) -> Dict[str, Any]:
        """Process a single dataset (ALL pages)"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"📂 PROCESSING DATASET {dataset_num} (ALL PAGES)")
        self.logger.info(f"{'='*60}")
        
        start_time = time.time()
        
        # Discover ALL pages
        files = self.discover_dataset_pages(dataset_num)
        
        results = {
            'dataset': dataset_num,
            'total_files': len(files),
            'downloaded': 0,
            'skipped': 0,
            'failed': 0,
            'total_size': 0,
            'start_time': datetime.now().isoformat(),
            'file_details': []
        }
        
        if not files:
            results['end_time'] = datetime.now().isoformat()
            results['duration'] = time.time() - start_time
            self._save_dataset_metadata(results, dataset_num)
            return results
        
        # Download if requested
        if download:
            self.logger.info(f"💾 Downloading {len(files)} files...")
            
            for i, file_meta in enumerate(files, 1):
                self.logger.info(f"📦 Progress: {i}/{len(files)} - {file_meta.filename}")
                
                success, file_path = self.download_file(file_meta)
                
                file_result = {
                    'filename': file_meta.filename,
                    'url': file_meta.url,
                    'success': success,
                    'file_path': file_path,
                    'size': file_meta.file_size,
                }
                
                results['file_details'].append(file_result)
                
                if success:
                    results['downloaded'] += 1
                    results['total_size'] += file_meta.file_size or 0
                elif file_path:
                    results['skipped'] += 1
                else:
                    results['failed'] += 1
                
                # Save cache periodically
                if i % 10 == 0 or i == len(files):
                    self._save_cache()
                
                # Delay between downloads
                if i < len(files):
                    time.sleep(random.uniform(1, 3))
            
            self.logger.info(f"📊 Dataset {dataset_num}: {results['downloaded']} downloaded")
        
        results['end_time'] = datetime.now().isoformat()
        results['duration'] = time.time() - start_time
        
        self._save_dataset_metadata(results, dataset_num)
        self._save_cache()
        
        return results
    
    def _save_dataset_metadata(self, results: Dict[str, Any], dataset_num: int):
        """Save metadata for a dataset"""
        metadata_file = self.metadata_dir / f"dataset_{dataset_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            self.logger.error(f"❌ Failed to save metadata: {e}")
    
    def discover_and_process_all(self, start_dataset: int = 1, download: bool = True) -> Dict[str, Any]:
        """
        Discover ALL datasets and process ALL pages
        """
        self.logger.info("=" * 70)
        self.logger.info("🚀 UNLIMITED EPSTEIN DOCUMENT ARCHIVER")
        self.logger.info("=" * 70)
        self.logger.info("📊 Mode: COMPLETE DISCOVERY - NO LIMITS")
        self.logger.info(f"   • Starting from dataset: {start_dataset}")
        self.logger.info(f"   • Download: {download}")
        self.logger.info("=" * 70)
        
        # First, discover ALL datasets
        all_datasets = self.discover_all_datasets(start_from=start_dataset)
        
        self.logger.info(f"\n🎯 Found {len(all_datasets)} datasets to process")
        
        all_results = []
        total_start = time.time()
        
        for i, dataset_num in enumerate(all_datasets, 1):
            try:
                self.logger.info(f"\n🎯 Progress: Dataset {i}/{len(all_datasets)} ({dataset_num})")
                
                results = self.process_dataset(dataset_num, download)
                all_results.append(results)
                
                # Pause between datasets
                if i < len(all_datasets):
                    pause = random.uniform(5, 15)
                    self.logger.info(f"⏸️ Pause: {pause:.1f}s...")
                    time.sleep(pause)
                    
            except Exception as e:
                self.logger.error(f"❌ Failed to process dataset {dataset_num}: {e}")
                continue
        
        # Final summary
        total_duration = time.time() - total_start
        
        totals = {
            'total_datasets': len(all_results),
            'total_files': sum(r['total_files'] for r in all_results),
            'total_downloaded': sum(r['downloaded'] for r in all_results),
            'total_skipped': sum(r['skipped'] for r in all_results),
            'total_failed': sum(r['failed'] for r in all_results),
            'total_size': sum(r['total_size'] for r in all_results),
            'total_duration': total_duration,
            'max_dataset_found': self.cache.max_dataset_found
        }
        
        self.logger.info("\n" + "=" * 70)
        self.logger.info("📊 COMPLETE DISCOVERY SUMMARY")
        self.logger.info("=" * 70)
        self.logger.info(f"📁 Total datasets found: {totals['total_datasets']}")
        self.logger.info(f"📄 Total files discovered: {totals['total_files']}")
        self.logger.info(f"✅ Successfully downloaded: {totals['total_downloaded']}")
        self.logger.info(f"📁 Already existed (skipped): {totals['total_skipped']}")
        self.logger.info(f"❌ Failed downloads: {totals['total_failed']}")
        self.logger.info(f"📦 Max dataset number found: {totals['max_dataset_found']}")
        
        if totals['total_size'] > 0:
            size_gb = totals['total_size'] / (1024 * 1024 * 1024)
            self.logger.info(f"📦 Total data size: {totals['total_size']:,} bytes ({size_gb:.2f} GB)")
        
        self.logger.info(f"⏱️ Total duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
        self.logger.info(f"📂 Files location: {self.raw_base_dir}/dataset*/")
        self.logger.info("=" * 70)
        self.logger.info("🎉 Complete discovery process finished!")
        self.logger.info("=" * 70)
        
        # Save final summary
        self._save_final_summary(all_results, totals, total_duration)
        
        return {
            'session_time': datetime.now().isoformat(),
            'results': all_results,
            'totals': totals,
            'cache_stats': {
                'cached_files': len(self.cache.files),
                'datasets_scanned': len(self.cache.datasets_scanned),
                'max_dataset_found': self.cache.max_dataset_found
            }
        }
    
    def _save_final_summary(self, results: List[Dict], totals: Dict, duration: float):
        """Save comprehensive final summary"""
        summary_file = self.metadata_dir / f"complete_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'totals': totals,
            'cache_state': self.cache.to_serializable()
        }
        
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
            self.logger.info(f"💾 Final summary saved: {summary_file}")
        except Exception as e:
            self.logger.error(f"❌ Failed to save final summary: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        total_files = 0
        total_size = 0
        
        for dataset_dir in self.raw_base_dir.glob("dataset*"):
            if dataset_dir.is_dir():
                pdf_files = list(dataset_dir.glob("*.pdf"))
                total_files += len(pdf_files)
                total_size += sum(f.stat().st_size for f in pdf_files)
        
        start_time = datetime.fromisoformat(self.cache.created_at)
        total_duration = (datetime.now() - start_time).total_seconds()
        
        return {
            'local_files': {
                'count': total_files,
                'total_size_gb': total_size / (1024 * 1024 * 1024),
            },
            'cache': {
                'files_tracked': len(self.cache.files),
                'datasets_scanned': len(self.cache.datasets_scanned),
                'max_dataset_found': self.cache.max_dataset_found,
            },
            'session_duration_hours': total_duration / 3600
        }
    
    def cleanup_all(self):
        """Remove ALL dataset directories and cache"""
        self.logger.info("🧹 Starting COMPLETE cleanup of ALL dataset directories...")
        
        cleanup_stats = {
            'directories_removed': 0,
            'files_removed': 0,
            'total_size_freed': 0
        }
        
        # Remove all dataset directories
        for dataset_dir in self.raw_base_dir.glob("dataset*"):
            if dataset_dir.is_dir():
                self.logger.info(f"🧹 Cleaning {dataset_dir}")
                
                # Remove all files in directory
                for item in dataset_dir.iterdir():
                    try:
                        if item.is_file():
                            file_size = item.stat().st_size
                            item.unlink()
                            cleanup_stats['files_removed'] += 1
                            cleanup_stats['total_size_freed'] += file_size
                        elif item.is_dir():
                            shutil.rmtree(item)
                    except Exception as e:
                        self.logger.error(f"❌ Error removing {item}: {e}")
                
                # Remove directory itself
                try:
                    dataset_dir.rmdir()
                    cleanup_stats['directories_removed'] += 1
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not remove directory {dataset_dir}: {e}")
        
        # Clear cache
        self.cache.files.clear()
        self.cache.datasets_scanned.clear()
        self.cache.max_dataset_found = 0
        self.cache.total_discovered = 0
        self.cache.total_downloaded = 0
        self.cache.total_failed = 0
        self.cache.total_skipped = 0
        
        self._save_cache()
        
        # Report statistics
        if cleanup_stats['total_size_freed'] > 0:
            size_gb = cleanup_stats['total_size_freed'] / (1024 * 1024 * 1024)
            self.logger.info(f"📊 Cleanup complete: {cleanup_stats['directories_removed']} directories, "
                           f"{cleanup_stats['files_removed']} files, {size_gb:.2f} GB freed")

# ==================== MAIN FUNCTION ====================
def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='UNLIMITED DOJ Epstein Documents Archiver - No dataset or page limits',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover and process EVERYTHING (all datasets, all pages)
  python archiver_unlimited.py --discover-all
  
  # Discover everything but don't download
  python archiver_unlimited.py --discover-all --discover-only
  
  # Start discovery from specific dataset
  python archiver_unlimited.py --discover-all --start-from 20
  
  # Show statistics
  python archiver_unlimited.py --stats
  
  # Complete cleanup (removes ALL dataset directories)
  python archiver_unlimited.py --cleanup-all
        """
    )
    
    parser.add_argument('--discover-all', action='store_true', 
                       help='Discover ALL datasets and ALL pages (no limits)')
    parser.add_argument('--start-from', type=int, default=1,
                       help='Start dataset discovery from this number (default: 1)')
    parser.add_argument('--discover-only', action='store_true',
                       help='Discover only, do not download')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--cleanup-all', action='store_true',
                       help='Remove ALL dataset directories and cache')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("🚀 UNLIMITED EPSTEIN DOCUMENT ARCHIVER")
    print("=" * 70)
    print("⚠️  NO DATASET OR PAGE LIMITS - WILL ATTEMPT TO DISCOVER EVERYTHING")
    print("=" * 70)
    
    try:
        archiver = UnlimitedEpsteinArchiver()
        
        if args.stats:
            stats = archiver.get_statistics()
            print("\n📊 CURRENT STATISTICS:")
            print(f"   Files downloaded: {stats['local_files']['count']}")
            print(f"   Total data: {stats['local_files']['total_size_gb']:.2f} GB")
            print(f"   Cache: {stats['cache']['files_tracked']} files tracked")
            print(f"   Datasets scanned: {stats['cache']['datasets_scanned']}")
            print(f"   Max dataset found: {stats['cache']['max_dataset_found']}")
            print(f"   Session duration: {stats['session_duration_hours']:.1f} hours")
            print(f"\n📁 Directory structure: /data/downloads/raw/dataset*/")
            return
        
        if args.cleanup_all:
            confirm = input("\n⚠️  WARNING: This will delete ALL dataset directories and cache. Continue? (y/N): ")
            if confirm.lower() == 'y':
                archiver.cleanup_all()
                print("✅ All dataset directories and cache have been removed")
            else:
                print("❌ Cleanup cancelled")
            return
        
        if args.discover_all:
            print(f"\n🎯 STARTING COMPLETE DISCOVERY")
            print(f"   • Starting from dataset: {args.start_from}")
            print(f"   • Mode: {'Discovery only' if args.discover_only else 'Download'}")
            print(f"   • NO LIMITS on datasets or pages")
            print()
            
            download = not args.discover_only
            results = archiver.discover_and_process_all(
                start_dataset=args.start_from,
                download=download
            )
            
            stats = archiver.get_statistics()
            print(f"\n📁 DISCOVERY COMPLETE:")
            print(f"   • Total datasets found: {results['totals']['total_datasets']}")
            print(f"   • Max dataset number: {results['totals']['max_dataset_found']}")
            print(f"   • Total files: {results['totals']['total_files']}")
            print(f"   • Files downloaded: {results['totals']['total_downloaded']}")
            print(f"\n💾 All files saved in: /data/downloads/raw/dataset*/")
            return
        
        print("\n❌ No action specified. Use --discover-all to start discovery.")
        print("   Use --help for all available options.")
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Process interrupted by user")
        print("💾 Cache has been saved")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()