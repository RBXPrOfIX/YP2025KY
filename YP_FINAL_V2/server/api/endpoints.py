from fastapi import APIRouter, Request, HTTPException, Depends, Body
from sqlalchemy.orm import Session
import json
import numpy as np

from database import get_db
from models import Lyrics, Log
from services.lyrics import fetch_lyrics_from_genius, process_and_save_lyrics
from services.crypto import decrypt_payload, encrypt_payload
from services.faiss_index import faiss_service
from services.idf_cache import idf_service
from config import (
    logger,
    SBERT_WEIGHT, E5_WEIGHT, EMO_WEIGHT,
    THEME_BONUS, GENRE_BONUS, OVERLAP_RATIO_BONUS,
    LENGTH_NORMALIZATION, DUPLICATE_PENALTY
)

router = APIRouter()


@router.post("/get_lyrics")
def get_lyrics_encrypted(
    request: Request,
    db: Session = Depends(get_db),
    body: dict = Body(...)
):
    token = body.get("data")
    if not token:
        raise HTTPException(status_code=400, detail="Missing encrypted payload")
    try:
        raw = decrypt_payload(token)
        params = json.loads(raw.decode("utf-8"))
        track_name = params.get("track_name")
        artist     = params.get("artist")
        if not track_name or not artist:
            raise HTTPException(status_code=400, detail="Invalid parameters")

        text, _ = fetch_lyrics_from_genius(track_name, artist)
        if len(text.split()) < 10:
            raise HTTPException(status_code=404, detail="Текст слишком короткий или не найден")

        result = process_and_save_lyrics(db, track_name, artist, text, {
            "ip":    request.client.host,
            "agent": request.headers.get("User-Agent", "-")
        })

        payload   = json.dumps(result, ensure_ascii=False).encode("utf-8")
        encrypted = encrypt_payload(payload)
        return {"data": encrypted}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Ошибка в /get_lyrics")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/find_similar")
async def find_similar_encrypted(
    request: Request,
    db: Session = Depends(get_db),
    body: dict = Body(...)
):
    token = body.get("data")
    if not token:
        raise HTTPException(status_code=400, detail="Missing encrypted payload")
    try:
        raw = decrypt_payload(token)
        params = json.loads(raw.decode("utf-8"))
        track_name = params.get("track_name")
        artist     = params.get("artist")
        if not track_name or not artist:
            raise HTTPException(status_code=400, detail="Invalid parameters")

        source = db.query(Lyrics).filter_by(track_name=track_name, artist=artist).first()
        if not source or not source.embedding or not source.sbert_embedding or not source.deep_emotion_vec:
            raise HTTPException(status_code=404, detail="Сначала вызовите /get_lyrics")

        # Normalize source vectors
        src_e5 = np.frombuffer(source.embedding, dtype=np.float32).copy()
        src_sb = np.frombuffer(source.sbert_embedding, dtype=np.float32).copy()
        src_em = np.frombuffer(source.deep_emotion_vec, dtype=np.float32).copy()
        src_e5 /= (np.linalg.norm(src_e5) + 1e-10)
        src_sb /= (np.linalg.norm(src_sb) + 1e-10)
        src_em /= (np.linalg.norm(src_em) + 1e-10)

        src_genres = set(source.genre or [])
        src_themes = set(source.themes or [])

        # Hybrid FAISS search
        candidate_ids = faiss_service.search(src_e5, src_sb, src_em, top_k=50)

        # Bulk fetch and filter
        objs       = db.query(Lyrics).filter(Lyrics.id.in_(candidate_ids)).all()
        id_to_obj  = {o.id: o for o in objs}
        neighbors  = []
        seen_ids   = set()
        for cid in candidate_ids:
            if cid == source.id or cid in seen_ids:
                continue
            o = id_to_obj.get(cid)
            if not o or not o.embedding:
                continue
            # require common genre and theme
            if not (src_genres & set(o.genre or [])):
                continue
            if not (src_themes & set(o.themes or [])):
                continue
            neighbors.append(o)
            seen_ids.add(cid)
            if len(neighbors) >= 30:
                break

        if not neighbors:
            raise HTTPException(status_code=404, detail="Нет доступных кандидатов")

        theme_idf = idf_service.theme_idf
        genre_idf = idf_service.genre_idf

        results = []
        for cand in neighbors:
            e5v = np.frombuffer(cand.embedding, dtype=np.float32).copy()
            sbv = np.frombuffer(cand.sbert_embedding, dtype=np.float32).copy()
            emv = np.frombuffer(cand.deep_emotion_vec, dtype=np.float32).copy()
            e5v /= (np.linalg.norm(e5v) + 1e-10)
            sbv /= (np.linalg.norm(sbv) + 1e-10)
            emv /= (np.linalg.norm(emv) + 1e-10)

            cos_sim = float(np.dot(src_e5, e5v))
            sb_sim  = float(np.dot(src_sb, sbv))
            emo_sim = float(np.dot(src_em, emv))

            common_t    = src_themes & set(cand.themes or [])
            union_t     = src_themes | set(cand.themes or [])
            theme_tfidf = (
                sum(theme_idf.get(t, 0) for t in common_t) /
                sum(theme_idf.get(t, 0) for t in union_t)
                if union_t else 0.0
            )

            common_g    = src_genres & set(cand.genre or [])
            union_g     = src_genres | set(cand.genre or [])
            genre_tfidf = (
                sum(genre_idf.get(g, 0) for g in common_g) /
                sum(genre_idf.get(g, 0) for g in union_g)
                if union_g else 0.0
            )
            overlap_ratio = (len(common_g) / len(union_g)) if union_g else 0.0

            raw_score    = SBERT_WEIGHT * sb_sim + E5_WEIGHT * cos_sim + EMO_WEIGHT * emo_sim
            bonus        = (1 + THEME_BONUS * theme_tfidf + GENRE_BONUS * genre_tfidf + OVERLAP_RATIO_BONUS * overlap_ratio)
            length_bonus = min(len(cand.lyrics.split()), LENGTH_NORMALIZATION) / LENGTH_NORMALIZATION
            score        = raw_score * bonus * length_bonus
            score        = min(score, 0.9999)

            results.append({
                "track":            cand.track_name,
                "artist":           cand.artist,
                "similarity":       round(score * 100, 2),
                "sbert_similarity": round(max(sb_sim,  0) * 100, 2),
                "cosine_semantic":  round(max(cos_sim, 0) * 100, 2),
                "emotion_sim":      round(emo_sim * 100,   2),
                "theme_tfidf":      round(theme_tfidf * 100,2),
                "genre_tfidf":      round(genre_tfidf * 100,2),
                "overlap_ratio":    round(overlap_ratio * 100,2),
            })

        # final unique top-5
        seen_pairs = set()
        final = []
        for item in sorted(results, key=lambda x: -x["similarity"]):
            pair = (item["track"], item["artist"])
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            final.append(item)
            if len(final) == 5:
                break

        db.add(Log(
            ip_address=request.client.host,
            operation="find_similar",
            status="success",
            device_info=request.headers.get("User-Agent", "-")
        ))
        db.commit()

        payload   = json.dumps({"similar_tracks": final}, ensure_ascii=False).encode("utf-8")
        encrypted = encrypt_payload(payload)
        return {"data": encrypted}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Ошибка в /find_similar")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
