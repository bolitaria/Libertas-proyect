"""
Procesador de documentos descargados.
"""
import asyncio
import logging
from pathlib import Path
import json
import hashlib
from typing import Dict, List, Optional
import PyPDF2
import pdfplumber
from datetime import datetime

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self, input_dir: str = "/data/downloads", output_dir: str = "/data/processed"):
        """Inicializar procesador de documentos"""
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def extract_pdf_metadata(self, pdf_path: Path) -> Dict:
        """Extraer metadatos de PDF"""
        metadata = {
            'file_name': pdf_path.name,
            'file_size': pdf_path.stat().st_size,
            'file_hash': self.calculate_file_hash(pdf_path),
            'extraction_date': datetime.now().isoformat()
        }
        
        try:
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                
                metadata.update({
                    'page_count': len(pdf_reader.pages),
                    'encrypted': pdf_reader.is_encrypted,
                    'pdf_version': pdf_reader.pdf_header
                })
                
                # Metadatos del PDF
                if pdf_reader.metadata:
                    for key, value in pdf_reader.metadata.items():
                        if value:
                            metadata[f'pdf_{key.lower().replace("/", "_")}'] = str(value)
        
        except Exception as e:
            logger.error(f"Error extrayendo metadatos de {pdf_path}: {e}")
        
        return metadata
    
    def extract_pdf_text(self, pdf_path: Path) -> Optional[str]:
        """Extraer texto de PDF"""
        try:
            text_parts = []
            
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        text_parts.append(f"--- Página {page_num} ---\n{text}")
            
            return "\n\n".join(text_parts) if text_parts else None
        
        except Exception as e:
            logger.error(f"Error extrayendo texto de {pdf_path}: {e}")
            return None
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Calcular hash SHA-256 del archivo"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def analyze_content(self, text: str) -> Dict:
        """Analizar contenido del documento"""
        if not text:
            return {}
        
        # Análisis básico
        words = text.split()
        sentences = text.split('.')
        
        # Palabras clave relacionadas con Epstein
        keywords = ['epstein', 'maxwell', 'trafficking', 'conspiracy', 'victim', 
                   'flight', 'island', 'plea', 'agreement', 'doj', 'justice']
        
        keyword_counts = {}
        for keyword in keywords:
            count = text.lower().count(keyword.lower())
            if count > 0:
                keyword_counts[keyword] = count
        
        return {
            'word_count': len(words),
            'sentence_count': len(sentences),
            'keyword_counts': keyword_counts,
            'contains_epstein': 'epstein' in text.lower(),
            'contains_maxwell': 'maxwell' in text.lower(),
            'contains_doj': 'department of justice' in text.lower() or 'doj' in text.lower()
        }
    
    async def process_document(self, pdf_path: Path) -> Optional[Dict]:
        """Procesar un documento individual"""
        logger.info(f"Procesando: {pdf_path.name}")
        
        # Verificar si ya fue procesado
        output_file = self.output_dir / f"{pdf_path.stem}_processed.json"
        if output_file.exists():
            logger.debug(f"Documento ya procesado: {pdf_path.name}")
            with open(output_file, 'r') as f:
                return json.load(f)
        
        # Extraer metadatos
        metadata = self.extract_pdf_metadata(pdf_path)
        
        # Extraer texto
        text = self.extract_pdf_text(pdf_path)
        metadata['has_text'] = bool(text)
        
        # Analizar contenido
        if text:
            analysis = self.analyze_content(text)
            metadata.update(analysis)
            
            # Guardar texto extraído
            text_file = self.output_dir / f"{pdf_path.stem}_text.txt"
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(text)
            metadata['text_file'] = str(text_file)
        
        # Guardar metadatos procesados
        with open(output_file, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"✅ Procesado: {pdf_path.name}")
        return metadata
    
    async def process_all(self) -> int:
        """Procesar todos los documentos en el directorio de entrada"""
        pdf_files = list(self.input_dir.glob("*.pdf"))
        processed_count = 0
        
        logger.info(f"Encontrados {len(pdf_files)} archivos PDF para procesar")
        
        # Procesar en lotes
        batch_size = 5
        for i in range(0, len(pdf_files), batch_size):
            batch = pdf_files[i:i + batch_size]
            tasks = [self.process_document(pdf) for pdf in batch]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, dict):
                    processed_count += 1
            
            logger.info(f"Procesado lote: {processed_count}/{len(pdf_files)}")
        
        return processed_count

async def main():
    """Función principal del procesador"""
    processor = DocumentProcessor()
    processed = await processor.process_all()
    print(f"Procesados {processed} documentos")

if __name__ == "__main__":
    asyncio.run(main())