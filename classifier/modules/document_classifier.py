"""
Clasificador principal de documentos.
"""
import logging
from typing import List, Dict, Any
import asyncio
from pathlib import Path
import json
from datetime import datetime
from .bert_classifier import BERTDocumentClassifier, Document
from .fallback_classifier import FallbackClassifier
from .keyword_matcher import KeywordMatcher

logger = logging.getLogger(__name__)

class DocumentClassifier:
    """Clasificador principal de documentos"""
    
    def __init__(self, config_path: str = "config/model_config.yaml"):
        """Inicializar clasificador"""
        import yaml
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Inicializar clasificadores
        self.bert_classifier = None
        self.fallback_classifier = None
        self.keyword_matcher = KeywordMatcher()
        
        # Directorios
        self.data_dir = Path(self.config['model']['paths']['data_dir'])
        self.models_dir = Path(self.config['model']['paths']['models_dir'])
        self.output_dir = Path(self.config['model']['paths']['output_dir'])
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Cargar o inicializar modelos
        self._load_models()
    
    def _load_models(self):
        """Cargar o inicializar modelos"""
        # Intentar cargar BERT fine-tuned
        bert_model_path = self.models_dir / "bert_finetuned"
        if bert_model_path.exists():
            try:
                self.bert_classifier = BERTDocumentClassifier()
                self.bert_classifier.load(str(bert_model_path))
                logger.info("✅ Modelo BERT cargado")
            except Exception as e:
                logger.error(f"Error cargando modelo BERT: {e}")
                self.bert_classifier = None
        
        # Intentar cargar clasificador de fallback
        fallback_path = self.models_dir / "fallback"
        if fallback_path.exists():
            try:
                self.fallback_classifier = FallbackClassifier()
                self.fallback_classifier.load(str(fallback_path))
                logger.info("✅ Clasificador de fallback cargado")
            except Exception as e:
                logger.error(f"Error cargando clasificador de fallback: {e}")
                self.fallback_classifier = None
        
        # Si no hay modelos, inicializar BERT base
        if not self.bert_classifier:
            logger.info("Inicializando modelo BERT base...")
            self.bert_classifier = BERTDocumentClassifier(
                model_name=self.config['model']['models']['primary']['model_name']
            )
        
        # Configurar keyword matcher
        categories = self.config['model']['categories']
        for category in categories:
            self.keyword_matcher.add_category(
                category['name'],
                category['keywords'],
                category['description']
            )
    
    def extract_text_from_file(self, file_path: Path) -> str:
        """Extraer texto de archivo procesado"""
        # Buscar archivo de texto procesado
        text_file = file_path.with_suffix('.txt')
        if text_file.exists():
            try:
                with open(text_file, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error leyendo {text_file}: {e}")
        
        # Si no hay archivo de texto, usar metadatos
        metadata_file = file_path.with_suffix('.json')
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    return metadata.get('text', '')
            except Exception as e:
                logger.error(f"Error leyendo {metadata_file}: {e}")
        
        return ""
    
    def load_document(self, file_path: Path) -> Document:
        """Cargar documento desde archivo"""
        # Cargar metadatos
        metadata_file = file_path.with_suffix('.json')
        metadata = {}
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            except Exception as e:
                logger.error(f"Error cargando metadatos de {metadata_file}: {e}")
        
        # Extraer texto
        text = self.extract_text_from_file(file_path)
        
        return Document(
            text=text[:5000],  # Limitar para BERT
            metadata=metadata,
            file_path=str(file_path)
        )
    
    async def classify_document(self, file_path: Path) -> Dict[str, Any]:
        """Clasificar un documento individual"""
        logger.info(f"Clasificando: {file_path.name}")
        
        # Cargar documento
        doc = self.load_document(file_path)
        
        # 1. Intentar con BERT
        if self.bert_classifier and doc.text:
            try:
                category, confidence = self.bert_classifier.predict_single(doc.text)
                
                if confidence >= self.config['model']['inference']['confidence_threshold']:
                    logger.info(f"BERT: {category} ({confidence:.3f})")
                    
                    return {
                        'file_path': str(file_path),
                        'category': category,
                        'confidence': confidence,
                        'method': 'bert',
                        'timestamp': datetime.now().isoformat()
                    }
            except Exception as e:
                logger.error(f"Error en clasificación BERT: {e}")
        
        # 2. Intentar con keyword matching
        if doc.text:
            keyword_result = self.keyword_matcher.classify(doc.text)
            if keyword_result['confidence'] > 0.5:
                logger.info(f"Keyword: {keyword_result['category']} ({keyword_result['confidence']:.3f})")
                
                return {
                    'file_path': str(file_path),
                    'category': keyword_result['category'],
                    'confidence': keyword_result['confidence'],
                    'method': 'keyword',
                    'keywords': keyword_result['matched_keywords'],
                    'timestamp': datetime.now().isoformat()
                }
        
        # 3. Usar fallback si está disponible
        if self.fallback_classifier and doc.text:
            try:
                category, confidence = self.fallback_classifier.predict_single(doc.text)
                
                logger.info(f"Fallback: {category} ({confidence:.3f})")
                
                return {
                    'file_path': str(file_path),
                    'category': category,
                    'confidence': confidence,
                    'method': 'fallback',
                    'timestamp': datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Error en clasificación fallback: {e}")
        
        # 4. Categoría por defecto
        logger.info(f"Usando categoría por defecto")
        
        return {
            'file_path': str(file_path),
            'category': 'unknown',
            'confidence': 0.0,
            'method': 'default',
            'timestamp': datetime.now().isoformat()
        }
    
    async def classify_all(self) -> List[Dict[str, Any]]:
        """Clasificar todos los documentos en el directorio de datos"""
        # Buscar archivos procesados
        json_files = list(self.data_dir.glob("*_processed.json"))
        results = []
        
        logger.info(f"Encontrados {len(json_files)} documentos para clasificar")
        
        # Clasificar en lotes
        batch_size = 10
        for i in range(0, len(json_files), batch_size):
            batch_files = json_files[i:i + batch_size]
            
            # Crear tareas para el lote actual
            tasks = []
            for json_file in batch_files:
                # El archivo PDF correspondiente
                pdf_file = self.data_dir / json_file.name.replace('_processed.json', '')
                if pdf_file.exists():
                    tasks.append(self.classify_document(pdf_file))
                else:
                    tasks.append(asyncio.sleep(0))  # Placeholder
            
            # Ejecutar lote
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Procesar resultados
            for result in batch_results:
                if isinstance(result, dict):
                    results.append(result)
            
            logger.info(f"Procesado lote: {len(results)}/{len(json_files)}")
            
            # Guardar resultados parciales
            self._save_results(results)
        
        logger.info(f"Clasificación completada: {len(results)} documentos")
        
        # Guardar resultados finales
        self._save_results(results)
        
        # Generar reporte
        self._generate_report(results)
        
        return results
    
    def _save_results(self, results: List[Dict[str, Any]]):
        """Guardar resultados de clasificación"""
        output_file = self.output_dir / f"classification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # También guardar en archivo maestro
        master_file = self.output_dir / "classification_master.json"
        all_results = []
        
        if master_file.exists():
            with open(master_file, 'r') as f:
                all_results = json.load(f)
        
        all_results.extend(results)
        
        with open(master_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
    
    def _generate_report(self, results: List[Dict[str, Any]]):
        """Generar reporte de clasificación"""
        report = {
            'total_documents': len(results),
            'categories': {},
            'methods': {},
            'timestamp': datetime.now().isoformat()
        }
        
        for result in results:
            category = result['category']
            method = result['method']
            
            # Contar por categoría
            report['categories'][category] = report['categories'].get(category, 0) + 1
            
            # Contar por método
            report['methods'][method] = report['methods'].get(method, 0) + 1
        
        # Calcular porcentajes
        for category, count in report['categories'].items():
            report['categories'][category] = {
                'count': count,
                'percentage': count / len(results) * 100
            }
        
        for method, count in report['methods'].items():
            report['methods'][method] = {
                'count': count,
                'percentage': count / len(results) * 100
            }
        
        # Guardar reporte
        report_file = self.output_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Reporte guardado en: {report_file}")
        
        # Imprimir resumen
        logger.info("=" * 50)
        logger.info("RESUMEN DE CLASIFICACIÓN")
        logger.info("=" * 50)
        logger.info(f"Total documentos: {report['total_documents']}")
        logger.info("Categorías:")
        for category, data in report['categories'].items():
            logger.info(f"  {category}: {data['count']} ({data['percentage']:.1f}%)")
        logger.info("Métodos:")
        for method, data in report['methods'].items():
            logger.info(f"  {method}: {data['count']} ({data['percentage']:.1f}%)")
        logger.info("=" * 50)

async def main():
    """Función principal"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    classifier = DocumentClassifier()
    results = await classifier.classify_all()
    
    print(f"Clasificados {len(results)} documentos")

if __name__ == "__main__":
    asyncio.run(main())