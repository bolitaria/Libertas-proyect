"""
Clasificador de fallback usando TF-IDF y SVM.
"""
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report
from typing import List, Dict, Tuple
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class FallbackClassifier:
    """Clasificador simple usando TF-IDF y SVM"""
    
    def __init__(self):
        """Inicializar clasificador de fallback"""
        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(
                max_features=10000,
                ngram_range=(1, 2),
                stop_words='english'
            )),
            ('svm', SVC(
                kernel='linear',
                probability=True,
                class_weight='balanced'
            ))
        ])
        
        self.categories = []
        self.is_trained = False
    
    def train(self, texts: List[str], labels: List[str]):
        """Entrenar clasificador"""
        logger.info(f"Entrenando clasificador con {len(texts)} documentos")
        
        # Guardar categorías únicas
        self.categories = sorted(set(labels))
        
        # Convertir etiquetas a índices numéricos
        label_to_index = {label: i for i, label in enumerate(self.categories)}
        y = [label_to_index[label] for label in labels]
        
        # Entrenar pipeline
        self.pipeline.fit(texts, y)
        self.is_trained = True
        
        logger.info(f"Clasificador entrenado con {len(self.categories)} categorías")
        
        # Evaluar
        y_pred = self.pipeline.predict(texts)
        report = classification_report(y, y_pred, target_names=self.categories)
        logger.info(f"Reporte de entrenamiento:\n{report}")
    
    def predict(self, texts: List[str]) -> List[Tuple[str, float]]:
        """Predecir categorías para textos"""
        if not self.is_trained:
            raise ValueError("Clasificador no entrenado")
        
        # Predecir probabilidades
        probas = self.pipeline.predict_proba(texts)
        predictions = self.pipeline.predict(texts)
        
        results = []
        for pred_idx, proba in zip(predictions, probas):
            category = self.categories[pred_idx]
            confidence = proba[pred_idx]
            results.append((category, confidence))
        
        return results
    
    def predict_single(self, text: str) -> Tuple[str, float]:
        """Predecir categoría para un solo texto"""
        results = self.predict([text])
        return results[0] if results else ("unknown", 0.0)
    
    def save(self, path: str):
        """Guardar clasificador"""
        model_path = Path(path)
        model_path.mkdir(parents=True, exist_ok=True)
        
        # Guardar pipeline
        with open(model_path / 'classifier.pkl', 'wb') as f:
            pickle.dump(self.pipeline, f)
        
        # Guardar categorías
        with open(model_path / 'categories.pkl', 'wb') as f:
            pickle.dump(self.categories, f)
        
        logger.info(f"Clasificador guardado en: {model_path}")
    
    def load(self, path: str):
        """Cargar clasificador"""
        model_path = Path(path)
        
        with open(model_path / 'classifier.pkl', 'rb') as f:
            self.pipeline = pickle.load(f)
        
        with open(model_path / 'categories.pkl', 'rb') as f:
            self.categories = pickle.load(f)
        
        self.is_trained = True
        logger.info(f"Clasificador cargado desde: {model_path}")
        logger.info(f"Categorías: {self.categories}")

# Ejemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Datos de ejemplo
    texts = [
        "court document legal filing",
        "transcript hearing testimony",
        "evidence photo document",
        "letter email correspondence",
        "financial payment record",
        "press release announcement"
    ]
    
    labels = [
        "legal_filing",
        "court_transcript",
        "evidence_document",
        "correspondence",
        "financial_record",
        "press_release"
    ]
    
    # Entrenar clasificador
    classifier = FallbackClassifier()
    classifier.train(texts, labels)
    
    # Predecir
    test_text = "This is a legal document"
    category, confidence = classifier.predict_single(test_text)
    print(f"Predicción: {category} ({confidence:.3f})")