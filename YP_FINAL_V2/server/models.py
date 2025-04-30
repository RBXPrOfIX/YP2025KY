from sqlalchemy import Column, Integer, String, Text, DateTime, Float, BLOB, JSON
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Lyrics(Base):
    __tablename__ = "lyrics"

    id              = Column(Integer, primary_key=True)
    track_name      = Column(String(200), index=True)
    artist          = Column(String(200), index=True)
    lyrics          = Column(Text)
    embedding       = Column(BLOB)
    sbert_embedding = Column(BLOB)
    deep_emotion    = Column(Float)
    deep_emotion_vec= Column(BLOB)
    themes          = Column(JSON, default=list)
    genre           = Column(JSON, default=list)
    created_at      = Column(DateTime, default=datetime.utcnow)
    lyrics_hash     = Column(String(32), index=True)

class Log(Base):
    __tablename__ = "logs"

    id          = Column(Integer, primary_key=True)
    timestamp   = Column(DateTime, default=datetime.utcnow)
    ip_address  = Column(String(15))
    operation   = Column(String(50))
    status      = Column(String(20))
    device_info = Column(Text)