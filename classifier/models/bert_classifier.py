"""
Clasificador de documentos usando BERT.
"""
import torch
from transformers import BertTokenizer, BertForSequenceClassification
from transformers import Trainer, TrainingArguments
import numpy as np
from typing import List, Dict, Tuple
import logging
from dataclasses import dataclass
from torch.utils.data import Dataset
import json
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class Document:
    """Estructura de documento"""
    text: str
    metadata: Dict
    file_path: str
    category: str = None
    confidence: float = 0.0

class DocumentDataset(Dataset):
    """Dataset para documentos"""
    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]
        
        encoding = self.tokenizer(
            text,
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }

class BERTDocumentClassifier:
    """Clasificador de documentos usando BERT"""
    
    def __init__(self, model_name="bert-base-uncased", num_labels=6, cache_dir="./cache"):
        """Inicializar clasificador BERT"""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Usando dispositivo: {self.device}")
        
        self.model_name = model_name
        self.num_labels = num_labels
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Inicializar tokenizer y modelo
        self.tokenizer = BertTokenizer.from_pretrained(model_name)
        self.model = BertForSequenceClassification.from_pretrained(
            model_name, 
            num_labels=num_labels
        )
        self.model.to(self.device)
        
        # Categorías
        self.categories = [
            "legal_filing",
            "court_transcript", 
            "evidence_document",
            "correspondence",
            "financial_record",
            "press_release"
        ]
        
        self.category_to_id = {cat: i for i, cat in enumerate(self.categories)}
        self.id_to_category = {i: cat for cat, i in self.category_to_id.items()}
    
    def prepare_training_data(self, documents: List[Document]):
        """Preparar datos de entrenamiento"""
        texts = [doc.text[:2000] for doc in documents]  # Limitar longitud
        labels = [self.category_to_id[doc.category] for doc in documents]
        
        return texts, labels
    
    def train(self, train_documents: List[Document], eval_documents: List[Document] = None):
        """Entrenar el modelo"""
        logger.info(f"Entrenando con {len(train_documents)} documentos")
        
        # Preparar datos
        train_texts, train_labels = self.prepare_training_data(train_documents)
        
        if eval_documents:
            eval_texts, eval_labels = self.prepare_training_data(eval_documents)
            eval_dataset = DocumentDataset(eval_texts, eval_labels, self.tokenizer)
        else:
            eval_dataset = None
        
        # Crear datasets
        train_dataset = DocumentDataset(train_texts, train_labels, self.tokenizer)
        
        # Configurar entrenamiento
        training_args = TrainingArguments(
            output_dir=str(self.cache_dir / "training"),
            num_train_epochs=10,
            per_device_train_batch_size=8,
            per_device_eval_batch_size=8,
            warmup_steps=500,
            weight_decay=0.01,
            logging_dir=str(self.cache_dir / "logs"),
            logging_steps=10,
            evaluation_strategy="epoch" if eval_dataset else "no",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="accuracy",
            greater_is_better=True,
        )
        
        # Crear trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            tokenizer=self.tokenizer,
        )
        
        # Entrenar
        trainer.train()
        
        # Guardar modelo
        model_path = self.cache_dir / "fine_tuned_model"
        self.model.save_pretrained(model_path)
        self.tokenizer.save_pretrained(model_path)
        
        logger.info(f"Modelo guardado en: {model_path}")
        
        return trainer
    
    def predict(self, documents: List[Document], batch_size=8) -> List[Document]:
        """Predecir categorías para documentos"""
        self.model.eval()
        
        predictions = []
        
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i+batch_size]
            batch_texts = [doc.text[:2000] for doc in batch_docs]
            
            # Tokenizar
            encoding = self.tokenizer(
                batch_texts,
                truncation=True,
                padding=True,
                max_length=512,
                return_tensors='pt'
            )
            
            # Mover al dispositivo
            input_ids = encoding['input_ids'].to(self.device)
            attention_mask = encoding['attention_mask'].to(self.device)
            
            # Predecir
            with torch.no_grad():
                outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=-1)
                preds = torch.argmax(probs, dim=-1)
                
                # Convertir a categorías
                for j, doc in enumerate(batch_docs):
                    pred_idx = preds[j].item()
                    confidence = probs[j][pred_idx].item()
                    
                    doc.category = self.id_to_category[pred_idx]
                    doc.confidence = confidence
                    
                    predictions.append(doc)
                    
                    logger.debug(f"Documento clasificado: {doc.category} ({confidence:.3f})")
        
        return predictions
    
    def predict_single(self, text: str) -> Tuple[str, float]:
        """Predecir categoría para un solo texto"""
        doc = Document(text=text, metadata={}, file_path="")
        results = self.predict([doc], batch_size=1)
        
        if results:
            return results[0].category, results[0].confidence
        else:
            return "unknown", 0.0
    
    def save(self, path: str):
        """Guardar modelo"""
        model_path = Path(path)
        model_path.mkdir(parents=True, exist_ok=True)
        
        self.model.save_pretrained(model_path)
        self.tokenizer.save_pretrained(model_path)
        
        # Guardar mapeo de categorías
        category_info = {
            'categories': self.categories,
            'category_to_id': self.category_to_id,
            'id_to_category': self.id_to_category
        }
        
        with open(model_path / 'category_info.json', 'w') as f:
            json.dump(category_info, f)
        
        logger.info(f"Modelo guardado en: {model_path}")
    
    def load(self, path: str):
        """Cargar modelo"""
        model_path = Path(path)
        
        self.model = BertForSequenceClassification.from_pretrained(model_path)
        self.tokenizer = BertTokenizer.from_pretrained(model_path)
        self.model.to(self.device)
        
        # Cargar mapeo de categorías
        with open(model_path / 'category_info.json', 'r') as f:
            category_info = json.load(f)
        
        self.categories = category_info['categories']
        self.category_to_id = {k: int(v) for k, v in category_info['category_to_id'].items()}
        self.id_to_category = {int(k): v for k, v in category_info['id_to_category'].items()}
        
        logger.info(f"Modelo cargado desde: {model_path}")
        logger.info(f"Categorías: {self.categories}")

# Ejemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Ejemplo de documentos de prueba
    sample_docs = [
        Document(
            text="IN THE UNITED STATES DISTRICT COURT FOR THE SOUTHERN DISTRICT OF NEW YORK...",
            metadata={},
            file_path="sample1.pdf",
            category="legal_filing"
        ),
        Document(
            text="TRANSCRIPT OF PROCEEDINGS BEFORE THE HONORABLE JUDGE...",
            metadata={},
            file_path="sample2.pdf",
            category="court_transcript"
        ),
    ]
    
    # Inicializar clasificador
    classifier = BERTDocumentClassifier()
    
    # Entrenar con datos de ejemplo
    classifier.train(sample_docs)
    
    # Predecir
    test_text = "This is a legal document filed in the court..."
    category, confidence = classifier.predict_single(test_text)
    print(f"Predicción: {category} ({confidence:.3f})")