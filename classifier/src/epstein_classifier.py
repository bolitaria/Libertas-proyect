#!/usr/bin/env python3
"""
Clasificador especializado para documentos Epstein.
Detección de temas legales, financieros, PII, y validación de redacciones.
"""
import os
import json
import re
from typing import Dict, List, Tuple
import logging
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)

class EpsteinClassifier:
    def __init__(self, model_dir: str = "models/epstein/"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Cargar modelos
        self.topic_model = self.load_topic_model()
        self.pii_detector = self.load_pii_detector()
        self.ner_model = self.load_ner_model()
        
        # Reglas específicas para Epstein
        self.epstein_keywords = {
            'victims': ['victim', 'survivor', 'complainant', 'witness'],
            'perpetrators': ['epstein', 'maxwell', 'accomplice', 'co-conspirator'],
            'locations': ['island', 'ranch', 'mansion', 'estate', 'residence'],
            'activities': ['trafficking', 'abuse', 'exploitation', 'conspiracy'],
            'entities': ['jeffrey', 'ghislaine', 'virgin islands', 'palm beach']
        }
    
    def load_topic_model(self):
        """Carga modelo de clasificación de temas"""
        try:
            from transformers import pipeline
            return pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli"
            )
        except ImportError:
            logger.warning("Transformers not available, using rule-based classification")
            return None
    
    def load_pii_detector(self):
        """Carga detector de información personal"""
        try:
            from presidio_analyzer import AnalyzerEngine
            return AnalyzerEngine()
        except ImportError:
            logger.warning("Presidio not available, using regex for PII")
            return None
    
    def load_ner_model(self):
        """Carga modelo de reconocimiento de entidades"""
        try:
            import spacy
            return spacy.load("en_core_web_lg")
        except:
            logger.warning("SpaCy NER model not available")
            return None
    
    def classify_epstein_document(self, text: str, file_path: str) -> Dict:
        """Clasifica un documento Epstein"""
        results = {
            'file': file_path,
            'topics': [],
            'entities': [],
            'pii_found': False,
            'redaction_issues': [],
            'risk_level': 'low'
        }
        
        # 1. Clasificación de temas
        if self.topic_model and len(text) > 100:
            candidate_topics = [
                "legal proceedings",
                "financial transactions", 
                "personal correspondence",
                "travel logs",
                "medical records",
                "law enforcement reports",
                "court documents",
                "witness statements"
            ]
            
            try:
                topic_result = self.topic_model(text[:5000], candidate_topics)
                results['topics'] = [
                    {'topic': topic, 'score': score}
                    for topic, score in zip(
                        topic_result['labels'][:3],
                        topic_result['scores'][:3]
                    )
                ]
            except:
                pass
        
        # 2. Detección de PII
        pii_results = self.detect_pii(text)
        results['pii_found'] = len(pii_results) > 0
        results['pii_details'] = pii_results
        
        if results['pii_found']:
            results['risk_level'] = 'high'
        
        # 3. Reconocimiento de entidades específicas
        entities = self.extract_epstein_entities(text)
        results['entities'] = entities
        
        # 4. Validación de redacciones
        redaction_issues = self.validate_redactions(text)
        results['redaction_issues'] = redaction_issues
        
        if redaction_issues:
            results['risk_level'] = 'high' if results['risk_level'] != 'high' else 'critical'
        
        # 5. Análisis de sentimiento/tono
        results['tone'] = self.analyze_tone(text)
        
        return results
    
    def detect_pii(self, text: str) -> List[Dict]:
        """Detecta información personal identificable"""
        pii_list = []
        
        # Patrones regex para PII común
        patterns = {
            'SSN': r'\b\d{3}-\d{2}-\d{4}\b',
            'Phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            'Email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'Credit Card': r'\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b',
            'DOB': r'\b(0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])[-/.](\d{4}|\d{2})\b'
        }
        
        for pii_type, pattern in patterns.items():
            matches = re.findall(pattern, text)
            if matches:
                pii_list.append({
                    'type': pii_type,
                    'count': len(matches),
                    'samples': list(set(matches))[:3]  # Muestra única
                })
        
        # Usar Presidio si está disponible
        if self.pii_detector:
            try:
                analyzer_results = self.pii_detector.analyze(
                    text=text,
                    language='en',
                    entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", 
                             "US_SSN", "CREDIT_CARD", "DATE_TIME",
                             "US_PASSPORT", "US_DRIVER_LICENSE"]
                )
                
                presidio_results = []
                for result in analyzer_results:
                    entity_text = text[result.start:result.end]
                    presidio_results.append({
                        'type': result.entity_type,
                        'text': entity_text,
                        'score': result.score
                    })
                
                if presidio_results:
                    pii_list.append({
                        'type': 'Presidio_Detections',
                        'count': len(presidio_results),
                        'details': presidio_results[:5]
                    })
            except Exception as e:
                logger.error(f"Error with Presidio: {e}")
        
        return pii_list
    
    def extract_epstein_entities(self, text: str) -> List[Dict]:
        """Extrae entidades relevantes para el caso Epstein"""
        entities = []
        
        # Palabras clave específicas
        for category, keywords in self.epstein_keywords.items():
            found = []
            for keyword in keywords:
                pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
                matches = pattern.findall(text)
                if matches:
                    found.extend(list(set(matches)))
            
            if found:
                entities.append({
                    'category': category,
                    'keywords': found[:10]  # Limitar a 10
                })
        
        # Reconocimiento de entidades con spaCy
        if self.ner_model and len(text) > 100:
            try:
                doc = self.ner_model(text[:10000])  # Limitar texto para performance
                
                entity_types = ['PERSON', 'ORG', 'GPE', 'LOC', 'DATE']
                for ent in doc.ents:
                    if ent.label_ in entity_types:
                        entities.append({
                            'type': ent.label_,
                            'text': ent.text,
                            'start': ent.start_char,
                            'end': ent.end_char
                        })
            except Exception as e:
                logger.error(f"Error with NER: {e}")
        
        return entities
    
    def validate_redactions(self, text: str) -> List[Dict]:
        """Valida que las redacciones sean efectivas"""
        issues = []
        
        # Buscar patrones que parezcan redacciones fallidas
        # 1. Texto entre corchetes que no sea [REDACTED]
        bad_redaction_patterns = [
            r'\[[^\]]{1,20}\]',  # Texto corto entre corchetes
            r'\([^)]{1,20}\)',   # Texto corto entre paréntesis
            r'\*\*\*',           # Asteriscos
            r'XXX',              # X repetidas
            r'___',              # Guiones bajos
        ]
        
        for pattern in bad_redaction_patterns:
            matches = re.findall(pattern, text)
            if matches:
                issues.append({
                    'type': 'suspicious_redaction',
                    'pattern': pattern,
                    'count': len(matches),
                    'samples': list(set(matches))[:3]
                })
        
        # 2. Buscar espacio en blanco excesivo que podría ocultar texto
        consecutive_spaces = re.findall(r'\s{10,}', text)
        if consecutive_spaces:
            issues.append({
                'type': 'excessive_whitespace',
                'count': len(consecutive_spaces),
                'max_length': max(len(s) for s in consecutive_spaces)
            })
        
        return issues
    
    def analyze_tone(self, text: str) -> Dict:
        """Analiza el tono/sentimiento del texto"""
        from collections import Counter
        import nltk
        from nltk.sentiment import SentimentIntensityAnalyzer
        
        try:
            nltk.data.find('sentiment/vader_lexicon.zip')
            sia = SentimentIntensityAnalyzer()
            sentiment = sia.polarity_scores(text[:5000])
            
            return {
                'positive': sentiment['pos'],
                'negative': sentiment['neg'],
                'neutral': sentiment['neu'],
                'compound': sentiment['compound']
            }
        except:
            # Análisis simple basado en palabras
            positive_words = ['good', 'positive', 'success', 'approved', 'legal']
            negative_words = ['bad', 'negative', 'failure', 'denied', 'illegal']
            
            text_lower = text.lower()
            pos_count = sum(text_lower.count(word) for word in positive_words)
            neg_count = sum(text_lower.count(word) for word in negative_words)
            
            total = pos_count + neg_count
            if total > 0:
                return {
                    'positive': pos_count / total,
                    'negative': neg_count / total,
                    'neutral': 1 - (pos_count + neg_count) / len(text.split()),
                    'method': 'word_count'
                }
        
        return {'method': 'none'}
    
    def generate_summary(self, text: str, max_length: int = 500) -> str:
        """Genera un resumen del documento"""
        # Método simple: tomar primeras oraciones
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        summary = ''
        for sentence in sentences:
            if len(summary) + len(sentence) < max_length:
                summary += sentence + '. '
            else:
                break
        
        return summary.strip()
    
    def process_document_batch(self, file_paths: List[str]) -> List[Dict]:
        """Procesa un lote de documentos"""
        results = []
        
        for file_path in file_paths:
            try:
                # Leer archivo
                if file_path.endswith('.txt'):
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                elif file_path.endswith('.pdf'):
                    text = self.extract_text_from_pdf(file_path)
                else:
                    logger.warning(f"Unsupported file type: {file_path}")
                    continue
                
                # Clasificar
                classification = self.classify_epstein_document(text, file_path)
                
                # Generar resumen
                classification['summary'] = self.generate_summary(text)
                
                # Calcular hash del contenido
                content_hash = hashlib.sha256(text.encode()).hexdigest()
                classification['content_hash'] = content_hash
                
                results.append(classification)
                
                logger.info(f"Processed: {file_path} - Topics: {[t['topic'] for t in classification.get('topics', [])]}")
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                results.append({
                    'file': file_path,
                    'error': str(e),
                    'processed': False
                })
        
        return results
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extrae texto de PDFs (nativos o escaneados)"""
        try:
            import PyPDF2
            
            text = ""
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            # Si es PDF escaneado (poco texto), usar OCR
            if len(text.strip()) < 100:
                try:
                    import pytesseract
                    from pdf2image import convert_from_path
                    
                    images = convert_from_path(pdf_path)
                    ocr_text = ""
                    for image in images:
                        ocr_text += pytesseract.image_to_string(image) + "\n"
                    
                    if ocr_text:
                        text = ocr_text
                except ImportError:
                    logger.warning("OCR libraries not available")
            
            return text
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
            return ""
    
    def save_classification_results(self, results: List[Dict], output_dir: str):
        """Guarda resultados de clasificación"""
        output_path = Path(output_dir) / "classifications.json"
        
        # Cargar existentes si hay
        existing_results = []
        if output_path.exists():
            with open(output_path, 'r') as f:
                existing_results = json.load(f)
        
        # Combinar resultados
        all_results = existing_results + results
        
        # Guardar
        with open(output_path, 'w') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(results)} classifications to {output_path}")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    classifier = EpsteinClassifier()
    
    # Ejemplo de uso
    test_files = [
        "/data/documents/epstein_sample1.pdf",
        "/data/documents/epstein_sample2.txt"
    ]
    
    results = classifier.process_document_batch(test_files)
    
    for result in results:
        print(f"\nFile: {result['file']}")
        print(f"Topics: {[t['topic'] for t in result.get('topics', [])]}")
        print(f"PII Found: {result.get('pii_found', False)}")
        print(f"Risk Level: {result.get('risk_level', 'unknown')}")
    
    # Guardar resultados
    classifier.save_classification_results(results, "/data/results")