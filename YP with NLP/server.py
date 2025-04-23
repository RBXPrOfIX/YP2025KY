# server.py

from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.types import BLOB
from datetime import datetime
import numpy as np
import lyricsgenius
import logging.config
import threading
import asyncio
import uvicorn
import re
import json
import hashlib
from functools import lru_cache
from bert_score import score as bertscore
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor

from transformers import (
    AutoTokenizer,
    AutoModel,
    AutoModelForSequenceClassification
)
import torch
from scipy.special import softmax
from nltk.stem.snowball import SnowballStemmer

# --- Конфигурация ---
DEFAULT_DATABASE_URL = "sqlite:///./database.db"
DEFAULT_PORT = 8000
GENIUS_TOKEN = "OheKD5f6K0vm_3aKWGfb5wE8Et4bkt_TTzXRVWcRr1Ywlb8VU1yMxVC6dATKMiw7"

LOGGING_CONFIG = {
    "version": 1,
    "handlers": {
        "file":    {"class": "logging.FileHandler",   "filename": "server.log", "formatter": "default"},
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
    },
    "formatters": {
        "default": {"format": "%(asctime)s - %(levelname)s - %(message)s"},
    },
    "root": {
        "handlers": ["file", "console"],
        "level":    "INFO",
    },
}
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# --- База данных ---
Base = declarative_base()

class Lyrics(Base):
    __tablename__ = "lyrics"
    id         = Column(Integer, primary_key=True)
    track_name = Column(String(200), index=True)
    artist     = Column(String(200), index=True)
    lyrics     = Column(Text)
    embedding  = Column(BLOB)   # numpy float32 → bytes
    emotion    = Column(Float)
    themes     = Column(Text)   # JSON-строка списка тем
    created_at = Column(DateTime, default=datetime.utcnow)

class Log(Base):
    __tablename__ = "logs"
    id          = Column(Integer, primary_key=True)
    timestamp   = Column(DateTime, default=datetime.utcnow)
    ip_address  = Column(String(15))
    operation   = Column(String(50))
    status      = Column(String(20))
    device_info = Column(Text)

engine       = create_engine(DEFAULT_DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(bind=engine)

# --- Семантическая модель (E5) ---
class SemanticModel:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large")
        self.model     = AutoModel.from_pretrained("intfloat/multilingual-e5-large")

    def encode(self, text: str) -> np.ndarray:
        prompt = "query: " + text.strip().replace("\n", " ")
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            output = self.model(**inputs).last_hidden_state[:, 0]
        emb = torch.nn.functional.normalize(output, dim=1)
        return emb.squeeze().cpu().numpy().astype(np.float32)

semantic_model = SemanticModel()

# --- Эмоциональная модель (multilingual sentiment) ---
class EmotionModel:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("cardiffnlp/twitter-xlm-roberta-base-sentiment")
        self.model     = AutoModelForSequenceClassification.from_pretrained("cardiffnlp/twitter-xlm-roberta-base-sentiment")

    def get_emotion_score(self, text: str) -> float:
        # Разбиваем на строки, анализируем каждую
        parts  = [line.strip() for line in text.split("\n") if line.strip()]
        scores = []
        for part in parts:
            inputs = self.tokenizer(part, return_tensors="pt", truncation=True, max_length=128)
            with torch.no_grad():
                logits = self.model(**inputs).logits
            probs = softmax(logits[0].cpu().numpy())
            # score = P(positive) - P(negative)
            scores.append(probs[2] - probs[0])
        return round(float(np.mean(scores)) if scores else 0.0, 4)

emotion_model = EmotionModel()

# --- Темы: словарь и построение stem-версии ---
russian_stemmer = SnowballStemmer("russian")
english_stemmer = SnowballStemmer("english")

theme_map = {
    "любовь": {"любовь", "love", "любить", "romance", "heart", "relationship", "crush"},
    "разлука": {"разлука", "separation", "goodbye", "farewell", "parting", "breaking", "breakup"},
    "измена": {"измена", "cheat", "unfaithful", "infidelity"},
    "деньги": {"деньги", "money", "cash", "rich", "wealth", "банкноты", "золото"},
    "предательство": {"предательство", "betrayal", "lie", "deception", "treason"},
    "власть": {"власть", "power", "control", "leader", "king"},
    "успех": {"успех", "success", "achieve", "win", "goal"},
    "провал": {"провал", "fail", "loser", "failure", "drop"},
    "друзья": {"друзья", "friends", "friendship", "bro", "homies"},
    "семья": {"семья", "family", "родители", "брат", "сестра", "mother", "father"},
    "одиночество": {"одиночество", "loneliness", "alone", "solitude"},
    "печаль": {"печаль", "sadness", "sorrow", "crying", "tears"},
    "счастье": {"счастье", "happiness", "joy", "smile", "радость"},
    "боль": {"боль", "pain", "hurt", "ache", "страдание"},
    "страх": {"страх", "fear", "scared", "panic", "ужас"},
    "гнев": {"гнев", "anger", "rage", "furious"},
    "зависть": {"зависть", "envy", "jealousy", "hate"},
    "тоска": {"тоска", "melancholy", "yearning", "homesick"},
    "надежда": {"надежда", "hope", "faith", "believe"},
    "вера": {"вера", "god", "prayer", "молитва", "религия"},
    "музыка": {"музыка", "music", "melody", "sound", "beat"},
    "алкоголь": {"алкоголь", "vodka", "drink", "wine", "бухать"},
    "наркотики": {"наркотики", "drugs", "weed", "cocaine", "addiction"},
    "секс": {"секс", "intimacy", "bedroom", "lust"},
    "мечта": {"мечта", "dream", "ambition", "goal"},
    "работа": {"работа", "job", "office", "career"},
    "тусовка": {"вечеринка", "party", "club", "танцы", "dance"},
    "машины": {"машины", "cars", "авто", "drive", "engine"},
    "преступление": {"преступление", "crime", "robbery", "gun", "shooting"},
    "тюрьма": {"тюрьма", "prison", "cell", "sentence", "jail"},
    "насилие": {"насилие", "violence", "fight", "beating", "abuse"},
    "смерть": {"смерть", "death", "grave", "die", "funeral"},
    "искушение": {"искушение", "temptation", "desire", "sin"},
    "зависимость": {"зависимость", "addiction", "need", "obsession"},
    "одежда": {"мода", "fashion", "style", "outfit"},
    "звезды": {"звезды", "stars", "moon", "sky", "небо"},
    "технологии": {"технологии", "ai", "robot", "gadget", "digital"},
    "интернет": {"интернет", "social", "network", "online"},
    "игры": {"игры", "games", "play", "console"},
    "время": {"время", "time", "moment", "hour", "clock"},
    "место": {"место", "place", "location", "where"},
    "дорога": {"дорога", "road", "highway", "path", "journey"},
    "город": {"город", "city", "town", "улица", "neon"},
    "дом": {"дом", "house", "home", "roof"},
    "природа": {"природа", "nature", "forest", "tree", "green"},
    "животные": {"животные", "animals", "dog", "cat", "beast"},
    "искусство": {"искусство", "art", "painting", "drawing"},
    "погода": {"погода", "weather", "rain", "storm", "cold"},
    "праздник": {"праздник", "holiday", "christmas", "birthday", "подарки"},
    "детство": {"детство", "childhood", "kid", "school", "baby"},
    "загадка": {"загадка", "mystery", "secret", "unknown", "dark"},
    "революция": {"революция", "change", "protest", "riot"},
    "война": {"война", "war", "battle", "soldier", "gun"},
    "прощение": {"прощение", "forgive", "извинение", "apology"},
    "обида": {"обида", "offense", "resentment", "hurt"},
    "грув": {"грув", "groove", "vibe", "atmosphere"},
    "свет": {"свет", "light", "shine", "bright"},
    "тьма": {"тьма", "dark", "shadow", "black"},
    "огонь": {"огонь", "fire", "burn", "flame"},
    "вода": {"вода", "water", "sea", "ocean", "river"},
    "бунт": {"бунт", "rebellion", "riot", "protest"},
    "преданность": {"преданность", "loyalty", "devotion"},
    "история": {"история", "story", "past", "flashback"},
    "маска": {"маска", "mask", "hidden", "false"},
    "токсичность": {"токсичность", "toxic", "harmful", "painful"},
    "предсказание": {"предсказание", "prophecy", "future", "vision"},
    "эмоции": {"эмоции", "feelings", "emotion", "мимика"},
    "вдохновение": {"вдохновение", "inspiration", "muse", "творчество"},
    "зов": {"зов", "call", "voice", "shout", "cry"},
    "тишина": {"тишина", "silence", "mute", "quiet"},
    "гордость": {"гордость", "pride", "dignity", "honor"},
    "страсть": {"страсть", "passion", "intensity", "urge"},
    "контроль": {"контроль", "control", "manipulate", "dominate"},
    "саморазрушение": {"саморазрушение", "self-destruction", "harm", "burnout"},
    "мотивация": {"мотивация", "motivation", "push", "drive"},
    "расставание": {"расставание", "breakup", "leave", "part"},
    "искупление": {"искупление", "redemption", "regret", "atonement"},
    "судьба": {"судьба", "destiny", "fate", "chosen"},
    "массовка": {"массовка", "crowd", "background", "множество"},
    "кризис": {"кризис", "crisis", "collapse", "ruin"},
    "пыль": {"пыль", "dust", "ash", "decay"},
    "цифры": {"цифры", "numbers", "score", "math"},
    "иллюзия": {"иллюзия", "illusion", "mirage", "fake"},
    "транспорт": {"транспорт", "transport", "subway", "bus", "train"},
    "движение": {"движение", "motion", "move", "speed"},
    "дьявол": {"дьявол", "devil", "evil", "demon"},
    "ангел": {"ангел", "angel", "wings", "heaven"},
    "уход": {"уход", "leaving", "quit", "farewell"},
    "открытие": {"открытие", "discovery", "open", "explore"},
    "поиск": {"поиск", "search", "find", "looking"},
    "решение": {"решение", "solution", "choice", "decision"},
    "вопросы": {"вопросы", "questions", "why", "what", "how"},
    "прошлое": {"прошлое", "past", "memories", "history"},
    "будущее": {"будущее", "future", "plans", "dreams"},
    "настоящее": {"настоящее", "now", "current", "real"},
    "ценности": {"ценности", "values", "morals", "ethics"},
    "уязвимость": {"уязвимость", "vulnerability", "weakness", "fragility"},
    "развод": {"развод", "divorce", "split", "separate", "family break"},
    "расизм": {"расизм", "racism", "discrimination", "racial"},
    "полиция": {"полиция", "police", "cop", "officer", "law"},
    "слава": {"слава", "fame", "glory", "recognition", "популярность"},
    "забвение": {"забвение", "oblivion", "forgotten", "fade"},
    "тюрьма": {"тюрьма", "prison", "cell", "bars", "sentence"},
    "одобрение": {"одобрение", "approval", "acceptance", "validation"},
    "хейт": {"хейт", "hate", "hater", "negativity"},
    "уход из жизни": {"уход из жизни", "suicide", "self-harm", "die"},
    "зависимость от славы": {"зависимость от славы", "fame addiction", "spotlight", "celebrity"},
    "паранойя": {"паранойя", "paranoia", "suspicion", "distrust"},
    "индустрия": {"индустрия", "industry", "label", "contracts"},
    "лицемерие": {"лицемерие", "hypocrisy", "two-faced", "fake"},
    "представление": {"представление", "performance", "stage", "show"},
    "авиаперелет": {"авиаперелет", "flight", "airport", "plane"},
    "дождь": {"дождь", "rain", "pour", "drizzle"},
    "психоз": {"психоз", "psychosis", "breakdown", "madness"},
    "деньги за славу": {"деньги за славу", "money for fame", "deal", "cash"},
    "непризнание": {"непризнание", "rejection", "denial", "ignore"},
    "злоба": {"злоба", "rage", "hate", "anger", "wrath"},
    "травма": {"травма", "trauma", "shock", "scar"},
    "горе": {"горе", "grief", "mourning", "loss"},
    "революция чувств": {"революция чувств", "emotional revolution", "upheaval"},
    "превосходство": {"превосходство", "superiority", "ego", "dominance"},
    "воспитание": {"воспитание", "upbringing", "parenting", "childhood"},
    "школа": {"школа", "school", "classroom", "lesson"},
    "институт": {"институт", "university", "college", "student"},
    "тренировка": {"тренировка", "training", "gym", "workout"},
    "потеря близких": {"потеря близких", "loss", "death of loved one"},
    "соседи": {"соседи", "neighbors", "apartment", "neighborhood"},
    "любовный треугольник": {"любовный треугольник", "love triangle", "third wheel"},
    "фанаты": {"фанаты", "fans", "audience", "listeners"},
    "тур": {"тур", "tour", "concert", "gig"},
    "тишина в душе": {"тишина в душе", "silence inside", "emptiness", "quiet"},
    "восстание": {"восстание", "uprising", "resistance", "fight"},
    "гордость улиц": {"гордость улиц", "street pride", "block", "hood"},
    "исповедь": {"исповедь", "confession", "truth", "reveal"},
    "иллюминаты": {"иллюминаты", "illuminati", "secret society"},
    "ментальное здоровье": {"ментальное здоровье", "mental health", "psyche", "therapy"},
    "больница": {"больница", "hospital", "ward", "sick"},
    "тишина": {"тишина", "silence", "calm", "hush"},
    "стыд": {"стыд", "shame", "embarrassment", "humiliation"},
    "одиночный путь": {"одиночный путь", "solo journey", "alone", "independent"},
    "спасение": {"спасение", "salvation", "rescue", "save"},
    "зло": {"зло", "evil", "darkness", "demon"},
    "песчаная буря": {"песчаная буря", "sandstorm", "desert", "storm"},
    "воля": {"воля", "will", "freedom", "inner strength"},
    "успокоение": {"успокоение", "calm", "relief", "peace"},
    "раздвоение": {"раздвоение", "split", "dualism", "conflict"},
    "игнор": {"игнор", "ignore", "ghost", "silent treatment"},
    "зомби": {"зомби", "zombie", "undead", "infection"},
    "блокировка": {"блокировка", "block", "ban", "mute"},
    "смена маски": {"смена маски", "mask change", "persona", "pretend"},
    "любовь к себе": {"любовь к себе", "self-love", "confidence", "esteem"},
    "стриминг": {"стриминг", "stream", "Spotify", "Apple Music"},
    "съёмка": {"съёмка", "shoot", "video", "camera"},
    "обман": {"обман", "trick", "lie", "mislead"},
    "исчезновение": {"исчезновение", "disappearance", "gone", "missing"},
    "путь к вершине": {"путь к вершине", "rise", "climb", "elevation"},
    "падение": {"падение", "fall", "collapse", "drop"},
    "ограничения": {"ограничения", "restrictions", "limits", "borders"},
    "цифровая жизнь": {"цифровая жизнь", "digital life", "online world"},
    "стресс": {"стресс", "stress", "pressure", "burnout"},
    "интим": {"интим", "intimate", "private", "close"},
    "внутренний голос": {"внутренний голос", "inner voice", "instinct", "conscience"},
    "подарок": {"подарок", "gift", "present", "surprise"},
    "воспитание улиц": {"воспитание улиц", "street raised", "block", "gang"},
    "честность": {"честность", "honesty", "truth", "real"},
    "ложь": {"ложь", "lie", "false", "deceive"},
    "внезапность": {"внезапность", "sudden", "unexpected", "shock"},
    "жара": {"жара", "heat", "hot", "burn"},
    "одурманенность": {"одурманенность", "numb", "high", "dazed"},
    "одежда брендов": {"одежда брендов", "brands", "fashion label", "drip"},
    "реклама": {"реклама", "ad", "promotion", "sellout"},
    "социальные роли": {"социальные роли", "roles", "expectations", "persona"},
    "молчание": {"молчание", "silence", "quiet", "mute"},
    "обещания": {"обещания", "promises", "oath", "vow"},
    "падшие ангелы": {"падшие ангелы", "fallen angels", "dark beings"},
    "неудовлетворённость": {"неудовлетворённость", "dissatisfaction", "unfulfilled"},
    "изгнание": {"изгнание", "exile", "banish", "alienate"},
    "голос улиц": {"голос улиц", "voice of streets", "underground", "urban"},
    "смысл жизни": {"смысл жизни", "meaning of life", "purpose", "existence"},
    "кома": {"кома", "coma", "unconscious", "void"},
    "реальность": {"реальность", "reality", "real life", "true"},
    "беспомощность": {"беспомощность", "helpless", "hopeless", "weak"}
}


def build_stemmed_theme_map():
    reverse = {}  # stem → theme
    smap = {}

    for theme, words in theme_map.items():
        stems = set()
        for w in words:
            stemmer = russian_stemmer if re.search(r"[а-яА-Я]", w) else english_stemmer
            stem = stemmer.stem(w)
            if stem not in reverse:  # один stem — одна тема
                reverse[stem] = theme
                stems.add(stem)
        smap[theme] = stems
    return smap


STEMMED_THEME_MAP = build_stemmed_theme_map()

def extract_themes(text: str) -> list[str]:
    tokens = re.findall(r"\b\w{3,}\b", text.lower())  # игнорим короткие
    counter = {}

    for t in tokens:
        stemmer = russian_stemmer if re.search(r"[а-яА-Я]", t) else english_stemmer
        stem = stemmer.stem(t)
        for theme, stems in STEMMED_THEME_MAP.items():
            if stem in stems:
                counter[theme] = counter.get(theme, 0) + 1

    # Фильтрация по количеству совпадений (X = 2)
    themes = [k for k, v in counter.items() if v >= 2]
    return themes


def is_text_valid(text: str) -> bool:
    words = text.split()
    if len(words) < 10:
        return False
    banned = ["инструментал", "intro", "при�ев"]
    return not any(b in text.lower() for b in banned)

# --- FastAPI и Genius ---
app = FastAPI()
genius = lyricsgenius.Genius(GENIUS_TOKEN)
genius.verbose = False
genius.remove_section_headers = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def fetch_lyrics(track: str, artist: str) -> str:
    try:
        song = genius.search_song(track, artist)
        return song.lyrics or ""
    except Exception as e:
        logger.error(f"Genius error: {e}")
        return ""

@app.get("/get_lyrics")
async def get_lyrics(request: Request, track_name: str, artist: str, db: Session = Depends(get_db)):
    text = await fetch_lyrics(track_name, artist)
    if not is_text_valid(text):
        raise HTTPException(status_code=404, detail="Недостаточно текста для анализа")
    emb     = semantic_model.encode(text)
    emotion = emotion_model.get_emotion_score(text)
    themes  = extract_themes(text)

    item = db.query(Lyrics).filter_by(track_name=track_name, artist=artist).first()
    if not item:
        item = Lyrics(
            track_name=track_name,
            artist=artist,
            lyrics=text,
            embedding=emb.tobytes(),
            emotion=emotion,
            themes=json.dumps(themes)
        )
        db.add(item)
    else:
        item.lyrics    = text
        item.embedding = emb.tobytes()
        item.emotion   = emotion
        item.themes    = json.dumps(themes)
    db.commit()

    db.add(Log(
        ip_address=request.client.host,
        operation="get_lyrics",
        status="success",
        device_info=request.headers.get("User-Agent", "-")
    ))
    db.commit()

    return {"track": item.track_name, "artist": item.artist, "lyrics": item.lyrics}

# --- Кэширование BERTScore ---
@lru_cache(maxsize=1000)
def cached_bertscore(text_a: str, text_b: str) -> float:
    try:
        _, _, f1 = bertscore(
            [text_a], [text_b],
            lang="ru",
            model_type="xlm-roberta-base",
            verbose=False,
            rescale_with_baseline=True
        )
        return float(f1[0])
    except Exception as e:
        logger.warning(f"BERTScore failed: {e}")
        return 0.0

# --- Функция параллельной оценки ---
def evaluate_candidate(args):
    i, src_vec, src_emotion, src_themes, src_text, candidate = args
    vec, emo, themes, lyrics, title, artist = candidate

    vec = vec / (np.linalg.norm(vec) + 1e-10)
    cosine_sim = float(np.dot(src_vec, vec))
    emo_diff = abs(src_emotion - emo)
    common = src_themes & themes
    theme_bonus = 1 + 0.05 * len(common)

    # Усечение текста до 400 слов
    def trim(text): return " ".join(text.split()[:400])
    bert_sim = cached_bertscore(trim(src_text), trim(lyrics))

    score = (
        0.5 * bert_sim +
        0.4 * cosine_sim +
        0.1 * (1 - emo_diff)
    ) * theme_bonus

    return {
        "track": title,
        "artist": artist,
        "similarity": round(min(max(score, 0.0), 1.0) * 100, 2),
        "bert_score": round(bert_sim * 100, 2),
        "cosine_similarity": round(cosine_sim * 100, 2),
        "tone_difference": round(emo_diff, 3),
        "shared_themes": list(common)
    }

@app.get("/find_similar")
async def find_similar(request: Request, track_name: str, artist: str, db: Session = Depends(get_db)):
    source = db.query(Lyrics).filter_by(track_name=track_name, artist=artist).first()
    if not source or not source.embedding:
        raise HTTPException(status_code=404, detail="Сначала вызовите /get_lyrics")

    src_vec = np.frombuffer(source.embedding, dtype=np.float32)
    src_vec = src_vec / (np.linalg.norm(src_vec) + 1e-10)
    src_text = " ".join(source.lyrics.strip().split()[:400])
    src_emotion = source.emotion
    src_themes = set(json.loads(source.themes))

    all_tracks = db.query(Lyrics).filter(Lyrics.id != source.id).all()

    # Подготовка кандидатов
    candidates = []
    for song in all_tracks:
        if not song.embedding or not song.lyrics or len(song.lyrics.split()) < 10:
            continue
        vec = np.frombuffer(song.embedding, dtype=np.float32)
        vec = vec / (np.linalg.norm(vec) + 1e-10)
        cosine_sim = float(np.dot(src_vec, vec))
        candidates.append((cosine_sim, (
            vec,
            song.emotion,
            set(json.loads(song.themes)),
            " ".join(song.lyrics.strip().split()[:400]),
            song.track_name,
            song.artist,
            len(song.lyrics.split())
        )))

    # Топ-30 по cosine
    top_candidates = sorted(candidates, key=lambda x: -x[0])[:30]

    def evaluate(args):
        vec, emo, themes, lyrics, title, artist, text_len = args
        cosine_sim = float(np.dot(src_vec, vec))
        emo_diff = abs(src_emotion - emo)
        theme_intersection = src_themes & themes
        theme_union = src_themes | themes
        overlap_ratio = len(theme_intersection) / len(theme_union) if theme_union else 0
        theme_bonus = 1 + 0.1 * len(theme_intersection) + 0.01 * overlap_ratio

        bert_sim = cached_bertscore(src_text, lyrics)
        text_len_bonus = min(text_len, 400) / 400

        score = (
            0.5 * bert_sim +
            0.4 * cosine_sim +
            0.1 * (1 - emo_diff)
        ) * theme_bonus * text_len_bonus

        return {
            "track": title,
            "artist": artist,
            "similarity": round(min(max(score, 0.0), 1.0) * 100, 2),
            "bert_score": round(bert_sim * 100, 2),
            "cosine_similarity": round(cosine_sim * 100, 2),
            "tone_difference": round(emo_diff, 3),
            "shared_themes": list(theme_intersection)
        }

    from concurrent.futures import ThreadPoolExecutor, as_completed
    args = [cand for _, cand in top_candidates]

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(evaluate, arg) for arg in args]
        results = [f.result() for f in as_completed(futures)]

    results = sorted(results, key=lambda x: -x["similarity"])[:5]

    db.add(Log(
        ip_address=request.client.host,
        operation="find_similar",
        status="success",
        device_info=request.headers.get("User-Agent", "-")
    ))
    db.commit()

    return {"similar_tracks": results}




# --- GUI для управления сервером ---
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QStatusBar, QMessageBox
)
from PyQt5.QtCore import QObject, pyqtSignal

class ServerSignals(QObject):
    server_started = pyqtSignal()
    server_stopped = pyqtSignal()

class ServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.server_thread = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Server Control Panel")
        self.setGeometry(300, 300, 400, 200)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.port_entry = QLineEdit(str(DEFAULT_PORT))
        self.db_entry   = QLineEdit(DEFAULT_DATABASE_URL)
        inp = QHBoxLayout(); inp.addWidget(QLabel("Порт:")); inp.addWidget(self.port_entry)
        dbp = QHBoxLayout(); dbp.addWidget(QLabel("Путь к БД:")); dbp.addWidget(self.db_entry)

        self.start_btn = QPushButton("Start Server")
        self.stop_btn  = QPushButton("Stop Server"); self.stop_btn.setEnabled(False)
        self.exit_btn  = QPushButton("Exit")
        self.status_bar= QStatusBar()

        layout.addLayout(inp); layout.addLayout(dbp)
        layout.addWidget(self.start_btn); layout.addWidget(self.stop_btn)
        layout.addWidget(self.exit_btn); layout.addWidget(self.status_bar)

        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)
        self.exit_btn.clicked.connect(self.close)

    def start_server(self):
        if not self.server_thread or not self.server_thread.is_alive():
            port = int(self.port_entry.text())
            self.server_thread = threading.Thread(
                target=lambda: uvicorn.run(app, host="0.0.0.0", port=port, log_config=LOGGING_CONFIG),
                daemon=True
            )
            self.server_thread.start()
            self.status_bar.showMessage(f"Сервер запущен на порту {port}")
            self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)
            QMessageBox.information(self, "Info", f"Сервер запущен на порту {port}")

    def stop_server(self):
        if self.server_thread and self.server_thread.is_alive():
            asyncio.run_coroutine_threadsafe(self.shutdown_server(), asyncio.new_event_loop())
            self.status_bar.showMessage("Сервер остановлен")
            self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
            QMessageBox.information(self, "Info", "Сервер остановлен")

    @staticmethod
    async def shutdown_server():
        await uvicorn.Server(uvicorn.Config(app)).shutdown()

if __name__ == "__main__":
    import sys
    app_qt = QApplication(sys.argv)
    gui    = ServerGUI()
    gui.show()
    sys.exit(app_qt.exec_())