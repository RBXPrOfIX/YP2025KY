import requests
import re
from urllib.parse import quote
import backoff
from config import LASTFM_API_URL, LASTFM_API_KEY, logger

@backoff.on_exception(backoff.expo, requests.RequestException, max_tries=3, jitter=backoff.full_jitter)
def search_track_versions(title: str, artist: str, limit: int = 10) -> list[dict]:
    resp = requests.get(LASTFM_API_URL, params={
        "method": "track.search",
        "track": title,
        "artist": artist,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": limit,
        "autocorrect": 1
    }, timeout=5)
    resp.raise_for_status()
    matches = resp.json().get("results", {}).get("trackmatches", {}).get("track", [])
    result = []
    for item in matches:
        try:
            listeners = int(item.get("listeners", 0))
        except ValueError:
            listeners = 0
        result.append({
            "artist": item.get("artist"),
            "listeners": listeners
        })
    return result

@backoff.on_exception(backoff.expo, requests.RequestException, max_tries=3, jitter=backoff.full_jitter)
def choose_most_popular_version(title: str, artist: str) -> str:
    candidates = search_track_versions(title, artist)
    best_score = -1
    best_artist = artist
    for cand in candidates:
        try:
            resp = requests.get(LASTFM_API_URL, params={
                "method": "track.getInfo",
                "artist": cand["artist"],
                "track": title,
                "api_key": LASTFM_API_KEY,
                "format": "json",
                "autocorrect": 1
            }, timeout=5)
            resp.raise_for_status()
            info = resp.json().get("track", {}) or {}
            playcount = int(info.get("playcount", 0))
        except Exception:
            playcount = 0
        score = cand["listeners"] + playcount
        if score > best_score:
            best_score = score
            best_artist = cand["artist"]
    return best_artist

@backoff.on_exception(backoff.expo, requests.RequestException, max_tries=3, jitter=backoff.full_jitter)
def fetch_tags_lastfm(title: str, artist: str) -> list[str]:
    allowed_genres = {
    # Основные
    "pop", "rock", "hip-hop", "rap", "jazz", "blues", "electronic", "metal", "punk", "funk", "soul",
    "rnb", "r&b", "classical", "reggae", "disco", "folk", "indie", "alternative", "house", "techno",
    "trance", "dubstep", "edm", "instrumental", "ambient", "lo-fi", "lofi", "grunge", "hard rock",
    "soft rock", "psychedelic", "experimental", "emo", "ska", "drum and bass", "dnb", "new wave",
    "industrial", "chillout", "synthpop", "trip-hop", "garage", "dance", "dance-pop", "electropop",
    "minimal", "post-rock", "metalcore", "death metal", "black metal", "heavy metal", "progressive",
    "neo soul", "dream pop", "dreamy", "gospel", "opera", "world", "ethnic", "latin", "reggaeton",
    "afrobeat", "trap", "phonk", "boom bap", "chanson", "k-pop", "j-pop", "c-pop", "soundtrack",
    "score", "musical", "hardcore", "acoustic", "melodic", "epic", "ballad", "romantic", "melancholy",
    "symphonic", "jazz rap", "pop rap", "alternative rock", "classic rock", "progressive rock", 
    "nu metal", "grime", "noise", "emo rap", "indietronica", "future bass", "hyperpop", "chiptune",
    "vaporwave", "glitch", "breakcore", "downtempo", "tech house", "deep house", "bassline", "uk garage",
    "jungle", "gabber", "hardstyle", "shoegaze", "post-punk", "coldwave", "math rock", "sludge", 
    "slowcore", "americana", "bluegrass", "swamp rock", "trap metal", "cloud rap",

    # Региональные и народные
    "flamenco", "tango", "samba", "bossa nova", "mariachi", "cumbia", "nordic folk", "celtic", "balkan",
    "greek folk", "turkish folk", "arabic", "klezmer", "african", "asian", "indian", "bollywood",
    "arabesque", "fado", "rebetiko", "persian", "mongolian throat singing", "jewish", "chinese traditional",
    "soca", "salsa", "merengue", "bachata", "dancehall", "highlife", "zouk", "polka", "Cajun", "zydeco",

    # Электронные и танцевальные
    "psytrance", "goa trance", "idm", "breakbeat", "electro swing", "future house", "big room",
    "progressive house", "trancecore", "industrial techno", "tech trance", "eurodance", "eurobeat",
    "hands up", "happy hardcore", "nightcore", "synthwave", "outrun", "retrowave", "witch house",
    "acid house", "tropical house", "future garage", "moombahton", "big beat", "drumstep",

    # Металл и тяжёлая сцена
    "thrash metal", "doom metal", "sludge metal", "post-metal", "speed metal", "power metal",
    "viking metal", "folk metal", "symphonic metal", "melodic death metal", "blackgaze",
    "metalstep", "groove metal", "deathcore", "mathcore", "technical death metal",
    "progressive metal", "industrial metal", "gothic metal",

    # Хип-хоп/рэп и смежное
    "g-funk", "west coast", "east coast", "southern rap", "drill", "latin trap", "underground rap",
    "conscious rap", "meme rap", "battle rap", "crunk", "hyphy", "bounce", "miami bass", "trap soul",
    "cloud rap",

    # Поп и инди
    "bubblegum pop", "teen pop", "pop punk", "synthpop", "baroque pop", "indie pop",
    "electro pop", "dream pop", "power pop", "art pop", "glam rock", "britpop", "pop rock", "indie rock",

    # Рок и альтернативная сцена
    "arena rock", "garage rock", "space rock", "stoner rock", "folk rock", "blues rock", "punk rock",
    "emo rock", "post-hardcore", "screamo", "noise rock", "psych rock", "sludge rock", "southern rock",
    "rap rock", "crossover thrash", "krautrock", "post-grunge", "gothic rock",

    # Саундтреки и инструментал
    "anime", "anime soundtrack", "video game music", "vgm", "game soundtrack", "cinematic",
    "film score", "instrumental hip-hop", "orchestral", "trailer music", "epic music", "background music",

    # Джаз и джазовые поджанры
    "bebop", "hard bop", "smooth jazz", "jazz fusion", "modal jazz", "free jazz",

    # Классическая музыка
    "baroque", "romantic classical", "contemporary classical",

    # Прочие и гибридные
    "spoken word", "a cappella", "field recordings", "avant-garde", "experimental hip-hop",
    "meditative", "healing", "new age", "relaxation", "sound healing", "nature sounds", "asmr",
    "tiktok music", "meme music", "satanic metal", "occult rock"
}

    logger.debug(f"[LastFM] track.getTopTags request for: artist={artist}, title={title}")
    try:
        resp = requests.get(LASTFM_API_URL, params={
            "method": "track.getTopTags",
            "artist": artist,
            "track": title,
            "api_key": LASTFM_API_KEY,
            "format": "json",
            "autocorrect": 1
        }, timeout=5)
        resp.raise_for_status()
        result = resp.json()
        tags = result.get("toptags", {}).get("tag", [])
        if isinstance(tags, dict):
            tags = [tags]
        names = [t["name"].lower() for t in tags if "name" in t]
        filtered = [t for t in names if t in allowed_genres]
        if filtered:
            logger.debug(f"[LastFM] filtered tags: {filtered!r}")
            return filtered
    except Exception as e:
        logger.debug(f"[LastFM] API call failed: {e!r}")

    logger.debug(f"[LastFM] fallback: HTML scrape for: artist={artist}, title={title}")
    try:
        # Убираем служебные скобки из имени артиста и названия для корректного URL
        safe_artist = re.sub(r"\s*\(.*\)$", "", artist)
        safe_title = re.sub(r"\s*\(.*\)$", "", title)
        url = f"https://www.last.fm/music/{quote(safe_artist)}/_/{quote(safe_title)}"
        page = requests.get(url, timeout=5)
        page.raise_for_status()
        html = page.text
        scraped = re.findall(r'<a[^>]+href="/tag/[^>]*>([^<]+)</a>', html)
        tags = list(dict.fromkeys(t.strip().lower() for t in scraped if t.strip()))
        filtered = [t for t in tags if t in allowed_genres]
        logger.debug(f"[LastFM] scraped and filtered tags: {filtered!r}")
        return filtered
    except Exception as e:
        logger.debug(f"[LastFM] HTML scrape failed: {e!r}")
        return []