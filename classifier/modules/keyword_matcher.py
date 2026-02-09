"""
Clasificador basado en palabras clave.
"""
import re
from typing import List, Dict, Tuple
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class KeywordMatcher:
    """Clasificador por palabras clave"""
    
    def __init__(self):
        self.categories = {}
        self.keyword_patterns = {}
    
    def add_category(self, name: str, keywords: List[str], description: str = ""):
        """Añadir categoría con sus palabras clave"""
        self.categories[name] = {
            'keywords': keywords,
            'description': description,
            'patterns': [re.compile(r'\b' + re.escape(kw.lower()) + r'\b', re.IGNORECASE) 
                        for kw in keywords]
        }
    
    def classify(self, text: str) -> Dict[str, any]:
        """Clasificar texto basado en palabras clave"""
        text_lower = text.lower()
        scores = defaultdict(int)
        matched_keywords = defaultdict(list)
        
        # Calcular puntaje para cada categoría
        for category_name, category_info in self.categories.items():
            for pattern, keyword in zip(category_info['patterns'], category_info['keywords']):
                matches = pattern.findall(text_lower)
                if matches:
                    scores[category_name] += len(matches)
                    matched_keywords[category_name].extend(matches)
        
        # Encontrar categoría con mayor puntaje
        if scores:
            best_category = max(scores.items(), key=lambda x: x[1])
            total_matches = sum(scores.values())
            
            return {
                'category': best_category[0],
                'confidence': best_category[1] / max(total_matches, 1),
                'score': best_category[1],
                'total_matches': total_matches,
                'matched_keywords': list(set(matched_keywords[best_category[0]])),
                'method': 'keyword'
            }
        else:
            return {
                'category': 'unknown',
                'confidence': 0.0,
                'score': 0,
                'total_matches': 0,
                'matched_keywords': [],
                'method': 'keyword'
            }
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extraer entidades nombradas basadas en palabras clave"""
        entities = defaultdict(list)
        
        # Patrones para tipos específicos
        patterns = {
            'date': r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',
            'money': r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+(?:\.\d{2})? (?:dollars|USD)',
            'case_number': r'Case No\.?\s*[:#]?\s*[A-Z0-9\-]+',
            'docket_number': r'Docket No\.?\s*[:#]?\s*[A-Z0-9\-:]+',
            'citation': r'\d+\s+[A-Z]+\s+\d+',
        }
        
        for entity_type, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                entities[entity_type].extend(list(set(matches)))
        
        return dict(entities)

# Ejemplo de uso
if __name__ == "__main__":
    matcher = KeywordMatcher()
    
    # Definir categorías Epstein
    matcher.add_category(
        "legal_filing",
        ["complaint", "motion", "affidavit", "order", "subpoena", "writ", "pleading", "brief"],
        "Documentos legales formales"
    )
    
    matcher.add_category(
        "evidence",
        ["exhibit", "evidence", "photo", "document", "record", "email", "text message", "recording"],
        "Material de evidencia"
    )
    
    # Clasificar texto
    text = "This is a legal complaint filed as Exhibit A in the case."
    result = matcher.classify(text)
    
    print(f"Categoría: {result['category']}")
    print(f"Confianza: {result['confidence']:.2f}")
    print(f"Palabras clave: {result['matched_keywords']}")
    
    # Extraer entidades
    entities = matcher.extract_entities("Case No: 20-cr-300, Date: 2023-01-15, Amount: $1,000,000")
    print(f"Entidades: {entities}")