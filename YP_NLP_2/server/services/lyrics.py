# server/services/lyrics.py
import json
import hashlib
from typing import Tuple
from sqlalchemy.orm import Session
from config import logger
from models import Lyrics, Log
from .semantic import get_text_embedding
from .emotion import get_deep_emotion
from .themes import extract_themes
from .lastfm import fetch_tags_lastfm, choose_most_popular_version
import lyricsgenius

from config import GENIUS_TOKEN

genius = lyricsgenius.Genius(GENIUS_TOKEN)
genius.verbose = False
genius.remove_section_headers = True


def fetch_lyrics_from_genius(track: str, artist: str) -> Tuple[str, str]:
    """Получить текст и имя исполнителя из Genius"""
    song = genius.search_song(track, artist)
    if not song:
        return "", artist
    return song.lyrics or "", song.primary_artist.name if hasattr(song, "primary_artist") else artist


def process_and_save_lyrics(db: Session, track: str, artist: str, lyrics: str, request_info: dict) -> dict:
    """Обработка и сохранение текста в БД"""
    lyrics_hash = hashlib.md5(lyrics.encode()).hexdigest()
    tags = fetch_tags_lastfm(track, choose_most_popular_version(track, artist))
    emotion_score = get_deep_emotion(lyrics)
    themes = extract_themes(lyrics)
    embedding = get_text_embedding(lyrics)

    data = {
        "track_name": track,
        "artist": artist,
        "lyrics": lyrics,
        "embedding": embedding,
        "deep_emotion": emotion_score,
        "themes": json.dumps(themes, ensure_ascii=False),
        "genre": json.dumps(tags, ensure_ascii=False),
        "lyrics_hash": lyrics_hash
    }

    entry = db.query(Lyrics).filter_by(track_name=track, artist=artist).first()
    if entry is None:
        db.add(Lyrics(**data))
    else:
        if entry.lyrics_hash != lyrics_hash:
            for k, v in data.items():
                setattr(entry, k, v)
    db.commit()

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
        "genre": tags,
        "emotion": emotion_score
    }
