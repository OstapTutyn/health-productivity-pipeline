import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

AW_BUCKET_ID = "aw-watcher-window_MacBook-Air-Ostap.local"
AW_URL = f"http://localhost:5600/api/0/buckets/{AW_BUCKET_ID}/events"

def fetch_screentime_events(limit: int = 100) -> list[dict]:
    params = {"limit": limit}
    response = requests.get(AW_URL, params=params)
    response.raise_for_status()

    return response.json()

def insert_to_bronze(supabase: Client, raw_events: list[dict]):
    if not raw_events:
        print("⚠️ Немає нових подій для запису.")
        return

    payload = {
        "device": "MacBook Air",
        "bucket_id": AW_BUCKET_ID,
        "events_count": len(raw_events),
        "events": raw_events
    }

    supabase.table("bronze_screentime").insert({"raw_payload": payload}).execute()
    print(f"✅ Успішно збережено {len(raw_events)} подій у bronze_screentime!")


if __name__ == "__main__":
    print("⏳ Отримуємо дані про екранний час з ActivityWatch...")

    # Створюємо клієнт Supabase
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Витягуємо події та зберігаємо
    events = fetch_screentime_events(limit=100)
    insert_to_bronze(supabase_client, events)

