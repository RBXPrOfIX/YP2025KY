# server/services/emotion.py
import numpy as np
import torch
from functools import lru_cache
from transformers import AutoModelForSequenceClassification, XLMRobertaTokenizer
from torch.quantization import quantize_dynamic
from scipy.special import softmax

class DeepEmotionModel:
    def __init__(self):
        self.tokenizer = XLMRobertaTokenizer.from_pretrained(
            "cardiffnlp/twitter-xlm-roberta-base-sentiment"
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            "cardiffnlp/twitter-xlm-roberta-base-sentiment"
        )
        self.model = quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)

    def analyze(self, text: str) -> float:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            logits = self.model(**inputs).logits[0].cpu().numpy()
        probs = softmax(logits)
        base_score = probs[2] - probs[0]
        diversity = len(set(text.split())) / max(1, len(text.split()))
        return round(float(base_score * (1 + 0.3 * diversity)), 4)

emotion_model = DeepEmotionModel()

@lru_cache(maxsize=10000)
def get_deep_emotion(text: str) -> float:
    return emotion_model.analyze(text)
