import numpy as np
import faiss
from typing import List
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Lyrics
from config import SBERT_WEIGHT, E5_WEIGHT, EMO_WEIGHT

class FaissIndexService:
    def __init__(self):
        self.index = None
        self.id_map: List[int] = []
        self.dim = None

    def build_index(self):
        db: Session = SessionLocal()
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.bind)
            if 'lyrics' not in inspector.get_table_names():
                return

            objs = db.query(Lyrics).filter(
                Lyrics.embedding != None,
                Lyrics.sbert_embedding != None,
                Lyrics.deep_emotion_vec != None
            ).all()
            if not objs:
                return

            vectors = []
            self.id_map = []
            for o in objs:
                e5  = np.frombuffer(o.embedding, dtype=np.float32).copy()
                sb  = np.frombuffer(o.sbert_embedding, dtype=np.float32).copy()
                emo = np.frombuffer(o.deep_emotion_vec, dtype=np.float32).copy()

                # normalize each segment
                e5  /= (np.linalg.norm(e5)  + 1e-10)
                sb  /= (np.linalg.norm(sb)  + 1e-10)
                emo /= (np.linalg.norm(emo) + 1e-10)

                # weighted concatenation
                part = np.concatenate([
                    E5_WEIGHT  * e5,
                    SBERT_WEIGHT * sb,
                    EMO_WEIGHT   * emo
                ])
                vec = part / (np.linalg.norm(part) + 1e-10)

                vectors.append(vec)
                self.id_map.append(o.id)

            emb_matrix = np.vstack(vectors)
            self.dim = emb_matrix.shape[1]

            # HNSW parameters tuned for recall
            self.index = faiss.IndexHNSWFlat(self.dim, 64)
            self.index.hnsw.efConstruction = 128
            self.index.hnsw.efSearch = 64
            self.index.add(emb_matrix)
        finally:
            db.close()

    def add(self, obj: Lyrics):
        e5  = np.frombuffer(obj.embedding, dtype=np.float32).copy()
        sb  = np.frombuffer(obj.sbert_embedding, dtype=np.float32).copy()
        emo = np.frombuffer(obj.deep_emotion_vec, dtype=np.float32).copy()

        e5  /= (np.linalg.norm(e5)  + 1e-10)
        sb  /= (np.linalg.norm(sb)  + 1e-10)
        emo /= (np.linalg.norm(emo) + 1e-10)

        part = np.concatenate([
            E5_WEIGHT   * e5,
            SBERT_WEIGHT* sb,
            EMO_WEIGHT  * emo
        ])
        vec = part / (np.linalg.norm(part) + 1e-10)

        if self.index is None:
            self.dim = vec.shape[0]
            self.index = faiss.IndexHNSWFlat(self.dim, 64)
            self.index.hnsw.efConstruction = 128
            self.index.hnsw.efSearch = 64

        self.index.add(vec.reshape(1, -1))
        self.id_map.append(obj.id)

    def search(self, query_e5: np.ndarray, query_sbert: np.ndarray, query_emo: np.ndarray, top_k: int) -> List[int]:
        q_e5  = query_e5   / (np.linalg.norm(query_e5)  + 1e-10)
        q_sb  = query_sbert/ (np.linalg.norm(query_sbert)+ 1e-10)
        q_emo = query_emo  / (np.linalg.norm(query_emo)  + 1e-10)

        part = np.concatenate([
            E5_WEIGHT   * q_e5,
            SBERT_WEIGHT* q_sb,
            EMO_WEIGHT  * q_emo
        ])
        q_vec = part / (np.linalg.norm(part) + 1e-10)

        if self.index is None or not self.id_map:
            return []
        _, idxs = self.index.search(q_vec.reshape(1, -1), min(top_k, len(self.id_map)))
        return [self.id_map[i] for i in idxs[0] if i < len(self.id_map)]

# Singleton instance
faiss_service = FaissIndexService()
