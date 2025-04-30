import numpy as np
import torch
from functools import lru_cache
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from torch.quantization import quantize_dynamic

class DeepEmotionModel:
    def __init__(self):
        # Мультиязычная модель GoEmotions на базе multilingual BERT
        self.tokenizer = AutoTokenizer.from_pretrained(
            "SchuylerH/bert-multilingual-go-emtions"
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            "SchuylerH/bert-multilingual-go-emtions"
        )
        # Динамическая квантизация для ускорения вывода
        self.model = quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
        # Словари для вычисления scalar_emotion
        self.label2id = model.config.label2id
        self.id2label = {int(k): v for k, v in model.config.id2label.items()}

    def analyze(self, text: str) -> np.ndarray:
        """
        Возвращает вектор вероятностей каждой из 28 эмоций по GoEmotions.
        """
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512
        )
        with torch.no_grad():
            logits = self.model(**inputs).logits[0]
        # Мульти-лейбл: применяем сигмоиду к каждому логиту
        probs = torch.sigmoid(logits)
        return probs.cpu().numpy().astype(np.float32)

# Синглтон-модель для всего приложения
emotion_model = DeepEmotionModel()

@lru_cache(maxsize=10000)
def get_emotion_vector(text: str) -> bytes:
    """
    Возвращает байтовое представление вектора вероятностей эмоций.
    """
    vec = emotion_model.analyze(text)
    return vec.tobytes()