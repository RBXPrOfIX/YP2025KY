import hashlib
import time
from typing import Tuple

import numpy as np
from sqlalchemy.orm import Session

from config import logger, GENIUS_TOKEN
from models import Lyrics, Log
from .semantic import get_text_embedding, sbert_model
from .emotion import get_emotion_vector, emotion_model
from .themes import extract_themes
from .lastfm import fetch_tags_lastfm, choose_most_popular_version
import lyricsgenius
from services.faiss_index import faiss_service
from config import GENIUS_TOKEN

genius = lyricsgenius.Genius(GENIUS_TOKEN)
genius.verbose = False
genius.remove_section_headers = True
genius.timeout = 10


def fetch_lyrics_from_genius(track: str, artist: str, retries: int = 3, delay: float = 2.0) -> Tuple[str, str]:
    for attempt in range(retries):
        try:
            song = genius.search_song(track, artist)
            if not song:
                return "", artist
            lyrics = song.lyrics or ""
            actual_artist = song.primary_artist.name if hasattr(song, "primary_artist") else artist
            return lyrics, actual_artist
        except Exception as e:
            logger.warning(f"Genius request failed (attempt {attempt+1}): {e}")
            time.sleep(delay)
    return "", artist


def process_and_save_lyrics(db: Session, track: str, artist: str, lyrics: str, request_info: dict) -> dict:
    lyrics_hash = hashlib.md5(lyrics.encode()).hexdigest()

    # Уточняем артиста и выбираем самую популярную версию
    _, genius_artist = fetch_lyrics_from_genius(track, artist)
    actual_artist = choose_most_popular_version(track, genius_artist)

    # Признаки
    tags_list = fetch_tags_lastfm(track, actual_artist)
    themes_list = extract_themes(lyrics)

    # E5-эмбеддинг
    e5_bytes = get_text_embedding(lyrics)
    sb_emb = sbert_model.encode([" ".join(lyrics.split()[:400])], batch_size=32)[0]
    sb_bytes = np.array(sb_emb, dtype=np.float32).tobytes()
    emo_bytes = get_emotion_vector(lyrics)
    emovec = np.frombuffer(emo_bytes, dtype=np.float32)

    # scalar_emotion
    joy_idx = emotion_model.label2id.get("joy")
    sad_idx = emotion_model.label2id.get("sadness")
    scalar_emotion = float(emovec[joy_idx] - emovec[sad_idx]) if joy_idx is not None and sad_idx is not None else 0.0

    data = {
        "track_name": track,
        "artist": artist,
        "lyrics": lyrics,
        "embedding": e5_bytes,
        "sbert_embedding": sb_bytes,
        "deep_emotion": scalar_emotion,
        "deep_emotion_vec": emo_bytes,
        # Сохраняем Python-списки для JSON-колонок
        "themes": themes_list,
        "genre": tags_list,
        "lyrics_hash": lyrics_hash
    }

    entry = db.query(Lyrics).filter_by(track_name=track, artist=artist).first()
    needs_index = False
    if not entry:
        entry = Lyrics(**data)
        db.add(entry)
        needs_index = True
    else:
        if entry.lyrics_hash != lyrics_hash:
            for k, v in data.items(): setattr(entry, k, v)
            needs_index = True

    db.commit()

    if needs_index:
        faiss_service.add(entry)

    # Логируем запрос
    db.add(Log(
        ip_address=request_info.get("ip"),
        operation="get_lyrics",
        status="success",
        device_info=request_info.get("agent", "-")
    ))
    db.commit()

    return {
        "track": track,
        "artist": artist,
        "lyrics": lyrics,
        "genre": tags_list,
        "emotion": scalar_emotion
    }