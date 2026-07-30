import os
import requests
import urllib.parse
from collections import Counter
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")

LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/"


def get_unprocessed_music_batches(supabase: Client) -> list[dict]:
    """Витягує всі необроблені батчі з bronze_music."""
    try:
        res = (
            supabase.table("bronze_music")
            .select("id, raw_payload")
            .eq("is_processed", False)
            .order("inserted_at", desc=False)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Помилка отримання батчів з bronze_music: {e}")
        return []


def enrich_track_details(artist_name: str, track_name: str) -> dict:
    """Отримує duration, genre та bpm для треку з Last.fm та додаткових API."""
    details = {"duration_seconds": 0, "genre": "Unknown", "bpm": None}

    if not LASTFM_API_KEY:
        return details

    # 1. Отримуємо duration та genre з Last.fm track.getInfo
    try:
        params = {
            "method": "track.getInfo",
            "api_key": LASTFM_API_KEY,
            "artist": artist_name,
            "track": track_name,
            "format": "json",
        }
        resp = requests.get(LASTFM_API_URL, params=params, timeout=5)
        if resp.status_code == 200:
            track_info = resp.json().get("track", {})

            # Duration (перетворюємо з мс у секунди)
            duration_ms = int(track_info.get("duration", 0))
            if duration_ms > 0:
                details["duration_seconds"] = round(duration_ms / 1000)

            # Genre (беремо перший топ-тег)
            toptags = track_info.get("toptags", {}).get("tag", [])
            if toptags:
                if isinstance(toptags, list) and len(toptags) > 0:
                    details["genre"] = toptags[0].get("name", "Unknown").capitalize()
                elif isinstance(toptags, dict):
                    details["genre"] = toptags.get("name", "Unknown").capitalize()
    except Exception as e:
        print(f"Не вдалося отримати деталі з Last.fm для {track_name}: {e}")

    # 2. Отримуємо BPM (MusicBrainz / AcousticBrainz lookup або пошуковий фолбек)
    try:
        # Безпечне кодування кирилиці для URL
        safe_query = urllib.parse.quote(f'artist:"{artist_name}" AND recording:"{track_name}"')
        mb_url = f"https://api.musicbrainz.org/ws/2/recording?query={safe_query}&fmt=json"

        headers = {"User-Agent": "PersonalRoutinePipeline/1.0 (contact@example.com)"}
        mb_resp = requests.get(mb_url, headers=headers, timeout=5)
    except Exception:
        pass

    return details


def process_music_batch(supabase: Client, batch: dict):
    batch_id = batch["id"]
    payload = batch.get("raw_payload", {})
    tracks = payload.get("tracks", [])

    if not tracks:
        print(f"Батч ID {batch_id} порожній. Позначаємо як оброблений.")
        supabase.table("bronze_music").update({"is_processed": True}).eq(
            "id", batch_id
        ).execute()
        return

    detailed_tracks = []
    hourly_buckets = {}

    for t in tracks:
        date_info = t.get("date", {})
        uts_str = date_info.get("uts")
        if not uts_str:
            continue

        played_at_dt = datetime.fromtimestamp(int(uts_str), tz=timezone.utc)
        played_at_iso = played_at_dt.isoformat()
        entry_date = played_at_dt.strftime("%Y-%m-%d")

        hourly_dt = played_at_dt.replace(minute=0, second=0, microsecond=0)
        hourly_iso = hourly_dt.isoformat()

        track_name = t.get("name", "Unknown Track")

        artist_info = t.get("artist", {})
        artist_name = (
            artist_info.get("#text")
            if isinstance(artist_info, dict)
            else str(artist_info)
        ) or "Unknown Artist"

        album_info = t.get("album", {})
        album_name = (
            album_info.get("#text")
            if isinstance(album_info, dict)
            else str(album_info)
        ) or "Unknown Album"

        # --- Data Enrichment (Жанр, Тривалість, BPM) ---
        enriched_info = enrich_track_details(artist_name, track_name)

        detailed_tracks.append(
            {
                "played_at": played_at_iso,
                "entry_date": entry_date,
                "track_name": track_name,
                "artist_name": artist_name,
                "album_name": album_name,
                "genre": enriched_info["genre"],
                "duration_seconds": enriched_info["duration_seconds"],
                "bpm": enriched_info["bpm"],
                "source": "lastfm",
            }
        )

        if hourly_iso not in hourly_buckets:
            hourly_buckets[hourly_iso] = {
                "entry_date": entry_date,
                "tracks_count": 0,
                "artists": [],
                "genres": [],
                "bpms": [],
            }

        hourly_buckets[hourly_iso]["tracks_count"] += 1
        hourly_buckets[hourly_iso]["artists"].append(artist_name)
        if enriched_info["genre"] != "Unknown":
            hourly_buckets[hourly_iso]["genres"].append(enriched_info["genre"])
        if enriched_info["bpm"]:
            hourly_buckets[hourly_iso]["bpms"].append(enriched_info["bpm"])

    # --- Збереження у stg_music_tracks ---
    if detailed_tracks:
        try:
            supabase.table("stg_music_tracks").upsert(
                detailed_tracks, on_conflict="artist_name,track_name,played_at"
            ).execute()
            print(
                f"Збережено та збагачено {len(detailed_tracks)} треків у stg_music_tracks"
            )
        except Exception as e:
            print(f"Помилка запису у stg_music_tracks: {e}")

    # --- Збереження у stg_music_hourly ---
    hourly_records = []
    for h_ts, data in hourly_buckets.items():
        artist_counts = Counter(data["artists"])
        dominant_artist = artist_counts.most_common(1)[0][0]

        dominant_genre = "Unknown"
        if data["genres"]:
            genre_counts = Counter(data["genres"])
            dominant_genre = genre_counts.most_common(1)[0][0]

        avg_bpm = None
        if data["bpms"]:
            avg_bpm = round(sum(data["bpms"]) / len(data["bpms"]))

        hourly_records.append(
            {
                "hourly_timestamp": h_ts,
                "entry_date": data["entry_date"],
                "tracks_count": data["tracks_count"],
                "dominant_artist": dominant_artist,
                "dominant_genre": dominant_genre,
                "avg_bpm": avg_bpm,
            }
        )

    if hourly_records:
        try:
            supabase.table("stg_music_hourly").upsert(
                hourly_records, on_conflict="hourly_timestamp"
            ).execute()
            print(
                f"Збережено {len(hourly_records)} годинних агрегацій у stg_music_hourly"
            )
        except Exception as e:
            print(f"Помилка запису у stg_music_hourly: {e}")

    # Позначаємо батч у Bronze як оброблений
    supabase.table("bronze_music").update({"is_processed": True}).eq(
        "id", batch_id
    ).execute()
    print(f"Батч ID {batch_id} успішно оброблено!")


if __name__ == "__main__":
    print("Запуск збагачення та трансформації музики...")
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Якщо треба перепрогонити існуючий батч для перевірки, скинемо is_processed в false в Supabase
    unprocessed_batches = get_unprocessed_music_batches(supabase_client)
    if not unprocessed_batches:
        print("Необроблених батчів у bronze_music не знайдено.")
    else:
        for b in unprocessed_batches:
            process_music_batch(supabase_client, b)