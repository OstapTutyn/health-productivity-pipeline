import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_USERNAME = os.getenv("LASTFM_USERNAME")

LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/"


def get_lastfm_watermark(supabase: Client) -> int:
    """Отримує unix timestamp останнього збереженого треку з etl_watermarks."""
    try:
        res = supabase.table("etl_watermarks").select("last_extracted_timestamp").eq("source_name", "lastfm").execute()
        if res.data:
            iso_str = res.data[0]["last_extracted_timestamp"]
            # Заміна Z на +00:00 для коректного парсингу в Python
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return int(dt.timestamp())
    except Exception as e:
        print(f"Не вдалося отримати watermark з Supabase: {e}")

    # За замовчуванням — за останні 7 днів
    return int((datetime.now(timezone.utc).timestamp()) - (7 * 86400))


def update_lastfm_watermark(supabase: Client, tracks: list[dict]):
    """Оновлює watermark новим максимальним часом після успішного збереження."""
    timestamps = [
        int(t["date"]["uts"]) for t in tracks if "date" in t and "uts" in t["date"]
    ]
    if not timestamps:
        return

    max_ts = max(timestamps)
    max_dt = datetime.fromtimestamp(max_ts, tz=timezone.utc)

    try:
        supabase.table("etl_watermarks").update({
            "last_extracted_timestamp": max_dt.isoformat()
        }).eq("source_name", "lastfm").execute()
        print(f"💧 Watermark для 'lastfm' успішно оновлено до {max_dt.isoformat()}")
    except Exception as e:
        print(f"Помилка оновлення watermark: {e}")


def fetch_recent_tracks_from_lastfm(from_uts: int) -> list[dict]:
    """Витягує нові треки з Last.fm API, які прослухані після from_uts."""
    params = {
        "method": "user.getrecenttracks",
        "user": LASTFM_USERNAME,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": 200,
        "from": from_uts + 1,  # тільки новіші за останній timestamp
    }

    try:
        response = requests.get(LASTFM_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        recent_tracks = data.get("recenttracks", {}).get("track", [])
        if isinstance(recent_tracks, dict):  # якщо повернувся 1 трек
            recent_tracks = [recent_tracks]

        # Фільтруємо трек, який зараз грає в реальному часі ("@attr": {"nowplaying": "true"})
        completed_tracks = [
            t for t in recent_tracks if not (t.get("@attr", {}).get("nowplaying") == "true")
        ]

        return completed_tracks
    except Exception as e:
        print(f"Помилка запиту до Last.fm API: {e}")
        return []


def insert_music_to_bronze(supabase: Client, tracks: list[dict]) -> bool:
    """Зберігає треки у bronze_music. Повертає True, якщо успішно."""
    if not tracks:
        return False

    payload = {
        "source": "lastfm",
        "username": LASTFM_USERNAME,
        "tracks_count": len(tracks),
        "tracks": tracks,
    }

    try:
        supabase.table("bronze_music").insert({"raw_payload": payload}).execute()
        print(f"Успішно збережено {len(tracks)} НОВИХ треків у bronze_music!")
        return True
    except Exception as e:
        print(f"Помилка запиту до Supabase (bronze_music): {e}")
        return False


if __name__ == "__main__":
    print("Перевірка нових треків на Last.fm...")
    if not LASTFM_API_KEY or not LASTFM_USERNAME:
        print("Помилка: LASTFM_API_KEY або LASTFM_USERNAME не вказані в .env")
        exit(1)

    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Читаємо стан (watermark)
    last_uts = get_lastfm_watermark(supabase_client)
    print(f"Шукаємо треки, прослухані після Unix TS: {last_uts} ({datetime.fromtimestamp(last_uts, tz=timezone.utc).isoformat()})")

    # 2. Отримуємо дані
    new_tracks = fetch_recent_tracks_from_lastfm(last_uts)

    # 3. Зберігаємо і, якщо успішно, оновлюємо watermark
    if new_tracks:
        is_success = insert_music_to_bronze(supabase_client, new_tracks)
        if is_success:
            update_lastfm_watermark(supabase_client, new_tracks)
    else:
        print("Нових треків поки немає.")