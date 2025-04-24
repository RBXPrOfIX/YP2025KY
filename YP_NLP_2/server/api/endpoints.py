from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Lyrics, Log
from services.lyrics import fetch_lyrics_from_genius, process_and_save_lyrics
from services.semantic import sbert_model
import numpy as np
import json
from config import logger

router = APIRouter()

@router.get("/get_lyrics")
async def get_lyrics(request: Request, track_name: str, artist: str, db: Session = Depends(get_db)):
    logger.info(f"get_lyrics: track={track_name!r}, artist={artist!r}")
    try:
        text, actual_artist = fetch_lyrics_from_genius(track_name, artist)
        if len(text.split()) < 10:
            raise HTTPException(status_code=404, detail="Текст слишком короткий или не найден")

        result = process_and_save_lyrics(db, track_name, actual_artist, text, {
            "ip": request.client.host,
            "agent": request.headers.get("User-Agent", "-")
        })
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка в /get_lyrics")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/find_similar")
async def find_similar(request: Request, track_name: str, artist: str, db: Session = Depends(get_db)):
    logger.info(f"find_similar: track={track_name!r}, artist={artist!r}")
    try:
        source = db.query(Lyrics).filter_by(track_name=track_name, artist=artist).first()
        if not source or not source.embedding:
            raise HTTPException(status_code=404, detail="Сначала вызовите /get_lyrics")

        src_vec = np.frombuffer(source.embedding, dtype=np.float32).copy()
        src_vec /= (np.linalg.norm(src_vec) + 1e-10)
        src_text = " ".join(source.lyrics.split()[:400])
        src_emotion = float(source.deep_emotion)
        src_themes = set(json.loads(source.themes))
        src_genres = set(json.loads(source.genre)) if source.genre else set()

        all_tracks = db.query(Lyrics).filter(Lyrics.id != source.id).all()
        candidates = []
        for s in all_tracks:
            if not s.embedding or len(s.lyrics.split()) < 10:
                continue
            vec = np.frombuffer(s.embedding, dtype=np.float32).copy()
            vec /= (np.linalg.norm(vec) + 1e-10)
            candidates.append({
                "vec": vec,
                "text": " ".join(s.lyrics.split()[:400]),
                "emotion": float(s.deep_emotion),
                "themes": set(json.loads(s.themes)),
                "genres": set(json.loads(s.genre) if s.genre else []),
                "title": s.track_name,
                "artist": s.artist,
                "length": len(s.lyrics.split())
            })

        top_candidates = sorted(candidates, key=lambda c: -np.dot(src_vec, c["vec"]))[:30]
        embs = sbert_model.encode([src_text] + [c["text"] for c in top_candidates], batch_size=32)
        src_sbert = embs[0]
        results = []

        for cand, emb in zip(top_candidates, embs[1:]):
            cos_sim = float(np.dot(src_vec, cand["vec"]))
            sb_sim = float(np.dot(src_sbert, emb) / (np.linalg.norm(src_sbert) * np.linalg.norm(emb) + 1e-10))
            emo_diff = abs(src_emotion - cand["emotion"])
            common_themes = src_themes & cand["themes"]
            common_genres = src_genres & cand["genres"]

            bonus = 1 + 0.1 * len(common_themes) + 0.05 * len(common_genres)
            bonus += 0.01 * (len(common_themes) / len(src_themes | cand["themes"]) if src_themes | cand["themes"] else 0)
            text_bonus = min(cand["length"], 400) / 400

            score = (0.5 * sb_sim + 0.4 * cos_sim + 0.1 * (1 - emo_diff)) * bonus * text_bonus

            results.append({
                "track": cand["title"],
                "artist": cand["artist"],
                "similarity": round(min(max(score, 0), 1) * 100, 2),
                "sbert_similarity": round(max(sb_sim, 0) * 100, 2),
                "cosine_semantic": round(max(cos_sim, 0) * 100, 2),
                "tone_diff": round(emo_diff, 3),
                "shared_themes": list(common_themes),
                "shared_genres": list(common_genres)
            })

        db.add(Log(
            ip_address=request.client.host,
            operation="find_similar",
            status="success",
            device_info=request.headers.get("User-Agent", "-")
        ))
        db.commit()

        return {"similar_tracks": sorted(results, key=lambda r: -r["similarity"])[:5]}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка в /find_similar")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

