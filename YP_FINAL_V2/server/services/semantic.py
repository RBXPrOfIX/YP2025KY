import numpy as np
import torch
from functools import lru_cache
from transformers import AutoTokenizer, AutoModel
from torch.quantization import quantize_dynamic
from sentence_transformers import SentenceTransformer

class SemanticEncoder:
    def __init__(self):
        # Инициализация токенизатора и модели E5 с динамической квантзацией
        self.tokenizer = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large")
        model = AutoModel.from_pretrained("intfloat/multilingual-e5-large")
        self.model = quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)

    def encode(self, text: str) -> np.ndarray:
        """
        Кодирует длинный текст в один эмбеддинг E5.
        Делит текст на чанки по ~200 слов, кодирует каждый с max_length=256,
        затем усредняет и нормализует итоговый вектор.
        """
        # Подготовка слов
        words = text.replace("\n", " ").split()
        if not words:
            # Возвращаем вектор нулей, если текст пуст
            hidden_size = self.model.config.hidden_size
            return np.zeros(hidden_size, dtype=np.float32)

        # Разбиение на чанки (~200 слов)
        chunk_size = 200
        embeddings = []
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            prompt = "query: " + chunk.strip()
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=256
            )
            with torch.no_grad():
                output = self.model(**inputs).last_hidden_state[:, 0]
            emb = torch.nn.functional.normalize(output, dim=1)
            embeddings.append(emb.squeeze(0))

        # Усреднение чанковых эмбеддингов и окончательная нормализация
        stacked = torch.stack(embeddings, dim=0)
        pooled = torch.mean(stacked, dim=0, keepdim=True)
        pooled = torch.nn.functional.normalize(pooled, dim=1)
        return pooled.squeeze(0).cpu().numpy().astype(np.float32)

# Объект энкодера
semantic_encoder = SemanticEncoder()

@lru_cache(maxsize=10000)
def get_text_embedding(text: str) -> bytes:
    """
    Возвращает агрегированный эмбеддинг текста в виде байтов для хранения в БД.
    """
    return semantic_encoder.encode(text).tobytes()

# SBERT для тонкой оценки сходства (оставляем без изменений на текущем этапе)
sbert_model = SentenceTransformer("distiluse-base-multilingual-cased-v1")