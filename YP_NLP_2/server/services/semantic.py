# server/services/semantic.py
import numpy as np
import torch
from functools import lru_cache
from transformers import AutoTokenizer, AutoModel
from torch.quantization import quantize_dynamic
from sentence_transformers import SentenceTransformer

class SemanticEncoder:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large")
        model = AutoModel.from_pretrained("intfloat/multilingual-e5-large")
        self.model = quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)

    def encode(self, text: str) -> np.ndarray:
        prompt = "query: " + text.replace("\n", " ").strip()
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=256)
        with torch.no_grad():
            output = self.model(**inputs).last_hidden_state[:, 0]
        embedding = torch.nn.functional.normalize(output, dim=1)
        return embedding.squeeze().cpu().numpy().astype(np.float32)

semantic_encoder = SemanticEncoder()

@lru_cache(maxsize=10000)
def get_text_embedding(text: str) -> bytes:
    return semantic_encoder.encode(text).tobytes()

# SBERT для сходства
sbert_model = SentenceTransformer("distiluse-base-multilingual-cased-v1")
