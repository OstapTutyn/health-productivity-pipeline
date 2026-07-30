import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def fetch_unprocessed_records(supabase: Client) -> list[dict]:
    """Витягує всі батчі з Bronze, які ще не були оброблені."""
    response = (
        supabase.table("bronze_screentime")
        .select("id, raw_payload")
        .eq("is_processed", False)
        .execute()
    )
    return response.data if response.data else []


def transform_to_events(payload: dict) -> list[dict]:
    """Розпаковує сирий payload у список очищених, дедуплікованих подій."""
    events = payload.get("events", [])
    device = payload.get("device", "Unknown device")

    unique_events = {}
    for event in events:
        data = event.get("data", {})
        started_at = event.get("timestamp")
        app_name = data.get("app", "Unknown")
        duration = event.get("duration", 0)

        # --- DATA QUALITY CHECKS ---
        # Відкидаємо нульову/від'ємну тривалість та баги Apple (> 24 год)
        if duration <= 0 or duration > 86400:
            continue

        # Ключ для унікальності
        key = (device, started_at, app_name)

        # Беремо останній або записуємо унікальний
        unique_events[key] = {
            "device": device,
            "app_name": app_name,
            "window_title": data.get("title", ""),
            "started_at": started_at,
            "duration_seconds": duration,
        }

    return list(unique_events.values())


def upsert_to_silver(supabase: Client, events: list[dict]):
    """Завантажує масив подій у stg_screentime_events (Silver Layer)."""
    if not events:
        return

    response = (
        supabase.table("stg_screentime_events")
        .upsert(events, on_conflict="device,started_at,app_name")
        .execute()
    )
    print(f"Успішно збережено {len(events)} деталей у stg_screentime_events!")


def mark_as_processed(supabase: Client, record_ids: list[int]):
    """Позначає оброблені батчі у Bronze."""
    if not record_ids:
        return

    supabase.table("bronze_screentime").update(
        {"is_processed": True}
    ).in_("id", record_ids).execute()
    print(f"Позначено {len(record_ids)} батчів у Bronze як is_processed = True.")


if __name__ == "__main__":
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Шукаємо необроблені дані в Bronze...")

    unprocessed_records = fetch_unprocessed_records(supabase_client)

    if unprocessed_records:
        all_clean_events = []
        processed_ids = []

        for record in unprocessed_records:
            print(f"Трансформуємо батч ID {record['id']}...")
            clean_events = transform_to_events(record["raw_payload"])
            all_clean_events.extend(clean_events)
            processed_ids.append(record["id"])

        if all_clean_events:
            print("Вставляємо в stg_screentime_events...")
            upsert_to_silver(supabase_client, all_clean_events)
        else:
            print("Після очистки аномалій не залишилося валідних подій для збереження.")

        # Позначаємо як оброблені навіть якщо батч складався лише з аномалій,
        # щоб скрипт не зациклювався на битих даних.
        mark_as_processed(supabase_client, processed_ids)
    else:
        print("Усі записи в bronze_screentime вже оброблені. Нових даних немає.")