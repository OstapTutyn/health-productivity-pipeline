import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def process_music_transform(supabase: Client):
    response = (
        supabase.table("bronze_music")
        .select("id, raw_payload")
        .eq("is_processed", False)
        .execute()
    )
    records = response.data if response.data else []
    if not records:
        print("Необроблених даних у bronze_music немає.")
        return

    processed_ids = []
    all_tracks = []

    for record in records:
        processed_ids.append(record["id"])
        payload = record.get("raw_payload", {})
        tracks = payload.get("tracks", [])

        for track in tracks:
            track_name = track.get("name")
            artist = track.get("artist", {}).get("#text") or track.get("artist", {}).get("name")
            album = track.get("album", {}).get("#text") or track.get("album", {}).get("name")
            date_info = track.get("date", {})
            uts = date_info.get("uts")

    chunk_size = 500
    if all_tracks:
        for i in range(0, len(all_tracks), chunk_size):
            chunk = all_tracks[i:i + chunk_size]
            supabase.table("stg_music_tracks").upsert(
                chunk, on_conflict="artist_name,track_name,played_at"
            ).execute()
        print(f"Успішно збережено {len(all_tracks)} треків у stg_music_tracks!")

    supabase.table("bronze_music").update({"is_processed": True}).in_("id", processed_ids).execute()
    print("Батчі в bronze_music успішно позначено як оброблені.")

if __name__ == "__main__":
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    process_music_transform(supabase_client)
