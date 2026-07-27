import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def fetch_latest_bronze_record(supabase: Client):
    response = (
        supabase.table("bronze_screentime")
        .select("raw_payload")
        .order("inserted_at", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        return {}

    return response.data[0]["raw_payload"]

def transform_to_events(payload: dict) -> list[dict]:
    """Розпаковує сирий payload у список очищених, дедуплікованих подій."""
    events = payload.get("events", [])
    device = payload.get("device", "Unknown device")

    unique_events = {}
    for event in events:
        data = event.get("data", {})
        started_at = event.get("timestamp")
        app_name = data.get("app", "Unknown")

        # Ключ для унікальності
        key = (device, started_at, app_name)

        # Беремо останній або записуємо унікальний
        unique_events[key] = {
            "device": device,
            "app_name": app_name,
            "window_title": data.get("title", ""),
            "started_at": started_at,
            "duration_seconds": event.get("duration", 0),
        }

    # Повертаємо список лише унікальних об'єктів
    return list(unique_events.values())

def upsert_to_silver(supabase: Client, events: list[dict]):
    """Завантажує масив подій у stg_screentime_events (Silver Layer)."""
    if not events:
        print("⚠️ Немає подій для вставки.")
        return

    # Зверни увагу на .select() в кінці - він змушує Supabase повернути реальні вставлені рядки!
    response = (
        supabase.table("stg_screentime_events")
        .upsert(events, on_conflict="device,started_at,app_name")
        .execute()
    )

    # ДРУКУЄМО РЕАЛЬНУ ВІДПОВІДЬ БАЗИ
    print("DEBUG Supabase response data:", response.data)
    print(
        f"✅ Успішно збережено {len(response.data if response.data else [])} деталей у stg_screentime_events!"
    )


if __name__ == "__main__":
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("⏳ Зчитуємо сирі дані з Bronze...")
    raw_payload = fetch_latest_bronze_record(supabase_client)

    if raw_payload:
        print("⚙️ Трансформуємо івенти...")
        clean_events = transform_to_events(raw_payload)

        print("🚀 Вставляємо в stg_screentime_events...")
        upsert_to_silver(supabase_client, clean_events)
    else:
        print("❌ Не вдалося знайти записи в bronze_screentime.")