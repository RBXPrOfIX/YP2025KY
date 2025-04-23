# populate_ultimate.py
import requests
import random
import time
import logging
from urllib.parse import quote
import sys
from langdetect import detect, LangDetectException
from concurrent.futures import ThreadPoolExecutor, as_completed
import backoff
from tqdm import tqdm

# Конфигурация
GENIUS_TOKEN = "OheKD5f6K0vm_3aKWGfb5wE8Et4bkt_TTzXRVWcRr1Ywlb8VU1yMxVC6dATKMiw7"
SERVER_URL = "http://localhost:8000/get_lyrics"
MAX_REQUESTS = 300
WORKERS = 8  # Оптимизировано для локального сервера
MAX_RETRIES = 7
REQUEST_TIMEOUT = 90
GENIUS_TIMEOUT = 30

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('populate_ultimate.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class GeniusAPI:
    def __init__(self, token):
        self.base_url = "https://api.genius.com"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.validate_token()

    def validate_token(self):
        try:
            response = requests.get(
                f"{self.base_url}/search?q=test",
                headers=self.headers,
                timeout=15
            )
            response.raise_for_status()
        except Exception as e:
            logging.error(f"Ошибка подключения к Genius API: {str(e)}")
            sys.exit(1)

    @backoff.on_exception(backoff.expo, Exception, max_tries=3, max_time=60)
    def search_tracks(self, term: str, pages: int = 3):
        tracks = []
        for page in range(1, pages + 1):
            try:
                response = requests.get(
                    f"{self.base_url}/search",
                    params={
                        "q": term,
                        "page": page,
                        "per_page": 20,
                        "sort": "popularity"
                    },
                    headers=self.headers,
                    timeout=GENIUS_TIMEOUT
                )
                data = response.json()

                for hit in data.get("response", {}).get("hits", []):
                    song = hit.get("result", {})
                    title = song.get("title", "").strip()
                    artist = song.get("primary_artist", {}).get("name", "").strip()
                    if title and artist:
                        tracks.append((title, artist))
                
                time.sleep(1.5)  # Защита от rate limits
            except Exception as e:
                logging.warning(f"Ошибка поиска: {str(e)}")
        
        return tracks

    def get_tracks(self):
        ru_terms = ["русский рэп", "поп-музыка", "шансон", "хип-хоп"]
        en_terms = ["pop", "rap"]
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self.search_tracks, term, 3): term for term in ru_terms + en_terms}
            results = []
            
            for future in tqdm(as_completed(futures), total=len(futures), desc="Сбор треков"):
                try:
                    results.extend(future.result())
                except Exception as e:
                    logging.error(f"Ошибка: {str(e)}")

        tracks = list({(t[0].lower(), t[1].lower()): t for t in results}.values())
        random.shuffle(tracks)
        return tracks[:MAX_REQUESTS]

class TrackProcessor:
    @staticmethod
    @backoff.on_exception(
        backoff.expo, 
        requests.exceptions.RequestException, 
        max_tries=MAX_RETRIES, 
        max_time=300,
        giveup=lambda e: not isinstance(e, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)))
    def process_track(track: tuple, session: requests.Session, pbar: tqdm):
        title, artist = track
        
        try:
            # Пропуск невалидных треков
            if any(x in title.lower() for x in ["remix", "live", "version"]):
                return False

            # Отправка запроса с увеличенным таймаутом
            response = session.get(
                SERVER_URL,
                params={"track_name": title, "artist": artist},
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                logging.info(f"Успешно: {artist} - {title}")
                return True
                
            pbar.write(f"Пропущен: {artist} - {title} ({response.status_code})")
            return False
            
        except LangDetectException:
            return False
        except Exception as e:
            pbar.write(f"Ошибка: {artist} - {title} ({str(e)})")
            raise

def check_server():
    try:
        test = requests.get("http://localhost:8000", timeout=10)
        return test.status_code in [200, 404, 405]
    except:
        return False

def main():
    if not check_server():
        logging.error("Сервер недоступен! Проверьте:")
        logging.error("1. Запущен ли server.py")
        logging.error("2. Открыт ли порт 8000")
        logging.error("3. Нет ли ошибок в server.log")
        return

    genius = GeniusAPI(GENIUS_TOKEN)
    
    logging.info("Инициализация сбора треков...")
    tracks = genius.get_tracks()
    
    added = 0
    with requests.Session() as session:
        session.mount('http://', requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=100,
            max_retries=3
        ))
        
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            with tqdm(total=len(tracks), desc="Обработка", dynamic_ncols=True) as pbar:
                futures = []
                
                for track in tracks:
                    future = executor.submit(
                        TrackProcessor.process_track,
                        track,
                        session,
                        pbar
                    )
                    futures.append(future)
                    time.sleep(0.3)  # Контроль скорости запросов
                
                for future in as_completed(futures):
                    try:
                        if future.result():
                            added += 1
                    except:
                        pass
                    finally:
                        pbar.update(1)

    logging.info(f"Успешно добавлено: {added}/{len(tracks)}")

if __name__ == "__main__":
    start_time = time.time()
    try:
        main()
    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}")
    finally:
        logging.info(f"Общее время: {(time.time()-start_time)/60:.1f} минут")