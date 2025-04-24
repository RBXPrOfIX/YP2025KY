# server/services/lastfm.py
import requests
import re
from urllib.parse import quote
import backoff
from config import LASTFM_API_URL, LASTFM_API_KEY, logger

@backoff.on_exception(backoff.expo, requests.RequestException, max_tries=3, jitter=backoff.full_jitter)
def search_track_versions(title: str, artist: str, limit: int = 10) -> list[dict]:
    resp = requests.get(LASTFM_API_URL, params={
        "method":      "track.search",
        "track":       title,
        "artist":      artist,
        "api_key":     LASTFM_API_KEY,
        "format":      "json",
        "limit":       limit,
        "autocorrect": 1
    }, timeout=5)
    resp.raise_for_status()
    results = resp.json().get("results", {}).get("trackmatches", {}).get("track", [])
    return [
        {
            "artist": item.get("artist"),
            "listeners": int(item.get("listeners", 0))
        }
        for item in results
    ]

@backoff.on_exception(backoff.expo, requests.RequestException, max_tries=3, jitter=backoff.full_jitter)
def choose_most_popular_version(title: str, artist: str) -> str:
    candidates = search_track_versions(title, artist)
    best_score = -1
    best_artist = None

    for candidate in candidates:
        try:
            resp = requests.get(LASTFM_API_URL, params={
                "method":      "track.getInfo",
                "artist":      candidate["artist"],
                "track":       title,
                "api_key":     LASTFM_API_KEY,
                "format":      "json",
                "autocorrect": 1
            }, timeout=5)
            resp.raise_for_status()
            track_info = resp.json().get("track", {}) or {}
            playcount = int(track_info.get("playcount", 0))
        except Exception:
            playcount = 0

        score = candidate["listeners"] + playcount
        if score > best_score:
            best_score = score
            best_artist = candidate["artist"]

    return best_artist or artist

@backoff.on_exception(backoff.expo, requests.RequestException, max_tries=3, jitter=backoff.full_jitter)
def fetch_tags_lastfm(title: str, artist: str) -> list[str]:
    logger.debug(f"[LastFM] getTopTags for: artist={artist}, title={title}")
    try:
        resp = requests.get(LASTFM_API_URL, params={
            "method":      "track.getTopTags",
            "artist":      artist,
            "track":       title,
            "api_key":     LASTFM_API_KEY,
            "format":      "json",
            "autocorrect": 1
        }, timeout=5)
        resp.raise_for_status()
        tag_data = resp.json().get("toptags", {}).get("tag", [])
        if isinstance(tag_data, dict):
            tag_data = [tag_data]
        return [tag["name"] for tag in tag_data if "name" in tag]
    except Exception as e:
        logger.warning(f"[LastFM] API failed, fallback to HTML: {e!r}")

    try:
        url = f"https://www.last.fm/music/{quote(artist)}/_/{quote(title)}"
        html = requests.get(url, timeout=5).text
        scraped = re.findall(r'<a[^>]+href="/tag/[^>]*>([^<]+)</a>', html)
        return list(dict.fromkeys(tag.strip() for tag in scraped if tag.strip()))
    except Exception as e:
        logger.warning(f"[LastFM] HTML scrape failed: {e!r}")
        return []
