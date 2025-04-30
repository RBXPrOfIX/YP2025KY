import os
import sys
import time
import logging
import random
import json
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import requests
from requests.exceptions import RequestException
from tqdm import tqdm
from dotenv import load_dotenv
import backoff
from langdetect import detect, LangDetectException
import lyricsgenius

# Load environment variables
load_dotenv()

# Configuration
GENIUS_TOKEN    = os.getenv("GENIUS_TOKEN", "")
LASTFM_API_KEY  = os.getenv("LASTFM_API_KEY", "")
SERVER_URL      = os.getenv("SERVER_URL", "http://localhost:8000/get_lyrics")
MAX_REQUESTS    = int(os.getenv("MAX_REQUESTS", "3000"))
WORKERS         = int(os.getenv("WORKERS", "8"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "90"))
GENIUS_TIMEOUT  = float(os.getenv("GENIUS_TIMEOUT", "30"))
LASTFM_API_URL  = os.getenv("LASTFM_API_URL", "http://ws.audioscrobbler.com/2.0/")

# Encryption key
_key_b64 = os.getenv("ENC_KEY_B64")
if not _key_b64:
    raise RuntimeError("Не задана переменная окружения ENC_KEY_B64")
KEY = base64.urlsafe_b64decode(_key_b64)
aesgcm = AESGCM(KEY)

def encrypt_payload(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    iv = os.urandom(12)
    ct = aesgcm.encrypt(iv, raw, associated_data=None)
    return base64.urlsafe_b64encode(iv + ct).decode()

def decrypt_payload(token: str) -> dict:
    data = base64.urlsafe_b64decode(token)
    iv, ct = data[:12], data[12:]
    raw = aesgcm.decrypt(iv, ct, associated_data=None)
    return json.loads(raw.decode("utf-8"))

# Validate env
if not GENIUS_TOKEN or not LASTFM_API_KEY:
    logging.error("GENIUS_TOKEN и/или LASTFM_API_KEY не заданы")
    sys.exit(1)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("populate_random.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Last.fm MBID cache
artist_mbid_cache = {}

@backoff.on_exception(backoff.expo, RequestException, max_tries=3, jitter=backoff.full_jitter)
def fetch_tags_lastfm(title: str, artist: str) -> List[str]:
    mbid = artist_mbid_cache.get(artist)
    if mbid is None:
        try:
            resp = requests.get(
                LASTFM_API_URL,
                params={"method": "artist.getInfo", "artist": artist, "api_key": LASTFM_API_KEY, "format": "json"},
                timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            mbid = resp.json().get("artist", {}).get("mbid")
        except RequestException:
            mbid = None
        artist_mbid_cache[artist] = mbid

    resp = requests.get(
        LASTFM_API_URL,
        params={"method": "track.getInfo", "artist": artist, "track": title, "api_key": LASTFM_API_KEY, "format": "json"},
        timeout=REQUEST_TIMEOUT
    )
    resp.raise_for_status()
    info = resp.json().get("track", {})

    if mbid and info.get("artist", {}).get("mbid") != mbid:
        return []

    tags = info.get("toptags", {}).get("tag", [])
    return [t.get("name") for t in tags if t.get("name")]

class GeniusAPI:
    BASE = "https://api.genius.com"
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "User-Agent": "populate-script/1.0"
        })
        try:
            r = self.session.get(f"{self.BASE}/search", params={"q": "test"}, timeout=GENIUS_TIMEOUT)
            r.raise_for_status()
        except RequestException as e:
            logger.error(f"Genius API unavailable: {e}")
            sys.exit(1)

    @backoff.on_exception(backoff.expo, RequestException, max_tries=5, jitter=backoff.full_jitter)
    def search_tracks(self, term: str, page: int) -> List[Tuple[str, str]]:
        resp = self.session.get(
            f"{self.BASE}/search",
            params={"q": term, "page": page, "per_page": 20},
            timeout=GENIUS_TIMEOUT
        )
        resp.raise_for_status()
        hits = resp.json().get("response", {}).get("hits", [])
        out = []
        for h in hits:
            r = h.get("result", {})
            title  = r.get("title", "").strip()
            artist = r.get("primary_artist", {}).get("name", "").strip()
            if title and artist and not any(x in title.lower() for x in ("remix","live","version")):
                out.append((title, artist))
        return out

    def get_random_tracks(self, terms: List[str], pages: int = 10) -> List[Tuple[str, str]]:
        tasks = []
        with ThreadPoolExecutor(max_workers=5) as exec:
            for term in terms:
                for p in range(1, pages+1):
                    tasks.append(exec.submit(self.search_tracks, term, p))
            all_tracks = []
            for f in tqdm(as_completed(tasks), total=len(tasks), desc="Collecting from Genius"):
                try:
                    all_tracks.extend(f.result())
                except Exception as e:
                    logger.warning(f"Error fetching Genius tracks: {e}")
        unique = {(t.lower(), a.lower()): (t,a) for t,a in all_tracks}
        lst = list(unique.values())
        random.shuffle(lst)
        return lst[:MAX_REQUESTS]

@backoff.on_exception(backoff.expo, RequestException, max_tries=7, jitter=backoff.full_jitter)
def send_to_server(session: requests.Session, title: str, artist: str) -> bool:
    payload = {"track_name": title, "artist": artist}
    token = encrypt_payload(payload)
    resp = session.post(SERVER_URL, json={"data": token}, timeout=REQUEST_TIMEOUT)
    if resp.status_code == 404:
        return False
    resp.raise_for_status()
    body = resp.json()
    encrypted = body.get("data")
    if not encrypted:
        return False
    data = decrypt_payload(encrypted)
    tags = data.get("genre") or []
    return bool(tags)

def main():
    # Check server availability
    try:
        r = requests.get(SERVER_URL, timeout=5)
        if r.status_code >= 500:
            raise RequestException("Server error")
    except Exception as e:
        logger.error(f"Cannot connect to server: {e}")
        sys.exit(1)

    # Initialize APIs
    genius_api = GeniusAPI(GENIUS_TOKEN)
    genius_lyrics = lyricsgenius.Genius(GENIUS_TOKEN)
    genius_lyrics.verbose = False
    genius_lyrics.remove_section_headers = True
    genius_lyrics.timeout = GENIUS_TIMEOUT

    terms = [
        "русский рэп","поп-музыка","шансон","хип-хоп",
        "pop","rap","rock","electronic","jazz","blues",
        "metal","indie","alternative","reggae","edm","r&b",
        "latin","folk"
    ]
    candidates = genius_api.get_random_tracks(terms)
    logger.info(f"Collected {len(candidates)} candidates")

    # Filter by Last.fm tags
    valid = []
    for title, artist in tqdm(candidates, desc="Filtering Last.fm"):
        try:
            tags = fetch_tags_lastfm(title, artist)
            if tags:
                valid.append((title, artist))
        except Exception as e:
            logger.warning(f"Last.fm error {artist}-{title}: {e}")
    logger.info(f"{len(valid)} after Last.fm")

    # Push to server with language check
    session = requests.Session()
    session.mount('http://', requests.adapters.HTTPAdapter(pool_connections=WORKERS, pool_maxsize=WORKERS))
    added = 0

    def process_and_send(title: str, artist: str) -> bool:
        # Fetch lyrics locally
        try:
            song = genius_lyrics.search_song(title, artist)
            lyrics = (song.lyrics or "").strip() if song else ""
            if not lyrics:
                logger.info(f"Skipping {artist}-{title}: no lyrics")
                return False
        except Exception as e:
            logger.warning(f"Error fetching lyrics {artist}-{title}: {e}")
            return False

        # Detect language
        try:
            lang = detect(lyrics)
        except LangDetectException:
            logger.warning(f"Language detection failed {artist}-{title}")
            return False
        if lang not in ("ru","en"):
            logger.info(f"Skipping {artist}-{title}: unsupported language '{lang}'")
            return False

        # Send to server
        return send_to_server(session, title, artist)

    with ThreadPoolExecutor(max_workers=WORKERS) as exec:
        futures = {exec.submit(process_and_send, t, a): (t,a) for t,a in valid}
        for f in tqdm(as_completed(futures), total=len(futures), desc="Pushing to server"):
            title, artist = futures[f]
            try:
                if f.result():
                    added += 1
            except Exception as e:
                logger.warning(f"Error processing {artist}-{title}: {e}")

    logger.info(f"Successfully added {added}/{len(valid)} tracks")

if __name__ == "__main__":
    start = time.time()
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        logger.info(f"Total time: {(time.time() - start)/60:.2f} min")
