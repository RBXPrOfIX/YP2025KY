import os
import sys
import time
import logging
import random
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.exceptions import RequestException
from tqdm import tqdm
from dotenv import load_dotenv
import backoff

# Load environment variables
load_dotenv()

# Configuration
GENIUS_TOKEN = os.getenv("GENIUS_TOKEN", "OheKD5f6K0vm_3aKWGfb5wE8Et4bkt_TTzXRVWcRr1Ywlb8VU1yMxVC6dATKMiw7")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY", "3bfa7b7aa77348f7de800e8f90af0a51")
SERVER_URL      = os.getenv("SERVER_URL", "http://localhost:8000/get_lyrics")
MAX_REQUESTS    = int(os.getenv("MAX_REQUESTS", "1000"))
WORKERS         = int(os.getenv("WORKERS", "8"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "90"))
GENIUS_TIMEOUT  = float(os.getenv("GENIUS_TIMEOUT", "30"))
LASTFM_API_URL  = os.getenv("LASTFM_API_URL", "http://ws.audioscrobbler.com/2.0/")

# Validate required variables
if not GENIUS_TOKEN or not LASTFM_API_KEY:
    logging.error("Environment variables GENIUS_TOKEN and/or LASTFM_API_KEY are not set.")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("populate_random.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Cache for artist MBIDs to filter out covers/duplicates
artist_mbid_cache = {}

@backoff.on_exception(backoff.expo, RequestException, max_tries=3, jitter=backoff.full_jitter)
def fetch_tags_lastfm(title: str, artist: str) -> List[str]:
    """
    Fetch tags for a given track from Last.fm, filtering out covers using artist MBID.
    """
    # Get artist MBID if not cached
    mbid = artist_mbid_cache.get(artist)
    if mbid is None:
        try:
            resp = requests.get(LASTFM_API_URL, params={
                "method": "artist.getInfo",
                "artist": artist,
                "api_key": LASTFM_API_KEY,
                "format": "json"
            }, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            mbid = resp.json().get("artist", {}).get("mbid")
        except RequestException:
            mbid = None
        artist_mbid_cache[artist] = mbid

    # Fetch track info
    resp = requests.get(LASTFM_API_URL, params={
        "method": "track.getInfo",
        "artist": artist,
        "track": title,
        "api_key": LASTFM_API_KEY,
        "format": "json"
    }, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    info = resp.json().get("track", {})

    # If MBID present and does not match, skip (likely a cover)
    if mbid and info.get("artist", {}).get("mbid") != mbid:
        return []

    # Extract tag names
    tags = info.get("toptags", {}).get("tag", [])
    return [t.get("name") for t in tags if t.get("name")]

class GeniusAPI:
    """Wrapper for the Genius API to fetch track candidates."""
    BASE = "https://api.genius.com"

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "User-Agent": "populate-script/1.0"
        })
        # Test connectivity
        try:
            r = self.session.get(f"{self.BASE}/search", params={"q": "test"}, timeout=GENIUS_TIMEOUT)
            r.raise_for_status()
        except RequestException as e:
            logger.error(f"Genius API unavailable: {e}")
            sys.exit(1)

    @backoff.on_exception(backoff.expo, RequestException, max_tries=5, jitter=backoff.full_jitter)
    def search_tracks(self, term: str, page: int) -> List[Tuple[str, str]]:
        """Search tracks by term and page."""
        resp = self.session.get(
            f"{self.BASE}/search",
            params={"q": term, "page": page, "per_page": 20},
            timeout=GENIUS_TIMEOUT
        )
        resp.raise_for_status()
        hits = resp.json().get("response", {}).get("hits", [])
        out = []
        for h in hits:
            res = h.get("result", {})
            title  = res.get("title", "").strip()
            artist = res.get("primary_artist", {}).get("name", "").strip()
            if title and artist and not any(x in title.lower() for x in ("remix", "live", "version")):
                out.append((title, artist))
        return out

    def get_random_tracks(self, terms: List[str], pages: int = 10) -> List[Tuple[str, str]]:
        """Collect and return a shuffled list of unique track candidates."""
        tasks = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            for term in terms:
                for p in range(1, pages + 1):
                    tasks.append(executor.submit(self.search_tracks, term, p))
            all_tracks = []
            for future in tqdm(as_completed(tasks), total=len(tasks), desc="Collecting from Genius"):
                try:
                    all_tracks.extend(future.result())
                except Exception as e:
                    logger.warning(f"Error fetching Genius tracks: {e}")
        # Deduplicate and shuffle
        unique = {(t.lower(), a.lower()): (t, a) for t, a in all_tracks}
        lst = list(unique.values())
        random.shuffle(lst)
        return lst[:MAX_REQUESTS]

@backoff.on_exception(backoff.expo, RequestException, max_tries=7, jitter=backoff.full_jitter)
def send_to_server(session: requests.Session, title: str, artist: str) -> bool:
    """
    Отправляет запрос /get_lyrics.
    - Если трек не найден или слишком короткий (404) — сразу возвращаем False.
    - При других ошибках (5xx, таймаутах) бросаем исключение, чтобы backoff сделал ретрай.
    """
    resp = session.get(
        SERVER_URL,
        params={"track_name": title, "artist": artist},
        timeout=REQUEST_TIMEOUT
    )
    if resp.status_code == 404:
        # трек не подходит — не ретраить
        return False
    resp.raise_for_status()
    data = resp.json()
    tags = data.get("genre") or []
    return bool(tags)

def check_server() -> bool:
    try:
        r = requests.get(SERVER_URL, timeout=5)
        return r.status_code < 500
    except RequestException as e:
        logger.error(f"Cannot connect to server: {e}")
        return False

def main():
    if not check_server():
        logger.error("Server /get_lyrics unavailable")
        sys.exit(1)

    genius = GeniusAPI(GENIUS_TOKEN)
    terms = ["русский рэп", "поп-музыка", "шансон", "хип-хоп", "pop", "rap"]
    candidates = genius.get_random_tracks(terms)
    logger.info(f"Collected {len(candidates)} candidates")

    # Filter by Last.fm tags
    valid = []
    for title, artist in tqdm(candidates, desc="Filtering by Last.fm tags"):
        try:
            tags = fetch_tags_lastfm(title, artist)
            if tags:
                valid.append((title, artist))
        except Exception as e:
            logger.warning(f"Last.fm fetch error for {artist} - {title}: {e}")
    logger.info(f"{len(valid)} tracks remain after Last.fm filter")

    # Send to server
    session = requests.Session()
    session.mount('http://', requests.adapters.HTTPAdapter(pool_connections=WORKERS, pool_maxsize=WORKERS))
    added = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(send_to_server, session, t, a): (t, a) for t, a in valid}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Pushing to server"):
            title, artist = futures[future]
            try:
                if future.result():
                    added += 1
            except Exception as e:
                logger.warning(f"Error sending {artist} - {title}: {e}")
    logger.info(f"Successfully added {added}/{len(valid)} tracks")

if __name__ == "__main__":
    start = time.time()
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        logger.info(f"Total time: {(time.time() - start)/60:.2f} min")

