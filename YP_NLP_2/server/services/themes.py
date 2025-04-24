# server/services/themes.py
import re
import json
import numpy as np
from typing import List
from nltk.stem.snowball import SnowballStemmer
from functools import lru_cache
from .semantic import semantic_encoder
import os

file_path = os.path.join(os.path.dirname(__file__), "themes.json")

# Инициализация стеммеров
russian_stemmer = SnowballStemmer("russian")
english_stemmer = SnowballStemmer("english")


# Загружаем словарь тем
with open(file_path, "r", encoding="utf-8") as f:
    theme_map = json.load(f)
    
# Стеммированная карта
def build_stemmed_map():
    reverse, smap = {}, {}
    for theme, words in theme_map.items():
        stems = set()
        for word in words:
            stemmer = russian_stemmer if re.search(r"[а-яА-Я]", word) else english_stemmer
            stem = stemmer.stem(word)
            if stem not in reverse:
                reverse[stem] = theme
                stems.add(stem)
        smap[theme] = stems
    return smap

STEMMED_THEME_MAP = build_stemmed_map()

# Эмбеддинги тем
THEME_EMBEDDINGS = {
    theme: semantic_encoder.encode(" ".join(words))
    for theme, words in theme_map.items()
}

def extract_themes(text: str, top_k: int = 5, sim_threshold: float = 0.5) -> List[str]:
    tokens = re.findall(r"\b\w{3,}\b", text.lower())
    counter = {}

    for token in tokens:
        stemmer = russian_stemmer if re.search(r"[а-яА-Я]", token) else english_stemmer
        stem = stemmer.stem(token)
        for theme, stems in STEMMED_THEME_MAP.items():
            if stem in stems:
                counter[theme] = counter.get(theme, 0) + 1

    rule_based = [t for t, c in counter.items() if c >= 2]

    snippet = " ".join(text.split()[:512])
    emb = semantic_encoder.encode(snippet)
    norm_emb = np.linalg.norm(emb) + 1e-10

    sims = {
        theme: float(np.dot(emb, theme_emb) / (norm_emb * (np.linalg.norm(theme_emb) + 1e-10)))
        for theme, theme_emb in THEME_EMBEDDINGS.items()
    }

    sem_based = [t for t, s in sims.items() if s >= sim_threshold]
    if not sem_based:
        sem_based = [t for t, _ in sorted(sims.items(), key=lambda x: -x[1])[:top_k]]

    themes = []
    for t in rule_based + sem_based:
        if t not in themes:
            themes.append(t)
        if len(themes) >= top_k:
            break

    return themes
