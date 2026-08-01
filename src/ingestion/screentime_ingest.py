import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
import requests
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

AW_BUCKET_ID = "aw-watcher-window_MacBook-Air-Ostap.local"
AW_URL = f"http://localhost:5600/api/0/buckets/{AW_BUCKET_ID}/events"

LOCK_FILE = Path(".last_run_date")


def check_already_ran_today() -> bool:
    """Перевіряє, чи скрипт вже запускався сьогодні."""
    if LOCK_FILE.exists():
        last_run = LOCK_FILE.read_text().strip()
        today_str = (datetime.now() - timedelta(hours=4)).date().isoformat()
        if last_run == today_str:
            return True
    return False


def save_run_date():
    """Зберігає поточну дату у файл блокування."""
    LOCK_FILE.write_text((datetime.now() - timedelta(hours=4)).date().isoformat())


def get_watermark(supabase: Client) -> str:
    """Отримує найсвіжіший timestamp з бази Supabase для інкрементального завантаження."""
    try:
        response = (
            supabase.table("bronze_screentime")
            .select("raw_payload")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        if response.data and len(response.data) > 0:
            payload = response.data[0].get("raw_payload", {})
            events = payload.get("events", [])
            if events:
                timestamps = [e.get("timestamp") for e in events if e.get("timestamp")]
                if timestamps:
                    return max(timestamps)
    except Exception as e:
        print(f"⚠️ Не вдалося отримати вотермарк з бази: {e}")

    default_start = datetime.now(timezone.utc) - timedelta(days=7)
    return default_start.isoformat()


def fetch_screentime_events(start_time: str) -> list[dict]:
    """Отримує події з ActivityWatch починаючи з вотермарка."""
    params = {"start": start_time}
    try:
        response = requests.get(AW_URL, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Помилка з'єднання з ActivityWatch (перевір, чи запущений додаток): {e}")
        return []


def group_events_by_logical_day(events: list[dict]) -> dict[str, list[dict]]:
    """Групує події за логічними днями з урахуванням зсуву доби на 04:00 ранку."""
    chunks = {}
    for event in events:
        timestamp_str = event.get("timestamp")
        if not timestamp_str:
            continue

        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Зсув доби на 4 години назад
        logical_dt = dt - timedelta(hours=4)
        logical_date_str = logical_dt.date().isoformat()

        if logical_date_str not in chunks:
            chunks[logical_date_str] = []
        chunks[logical_date_str].append(event)

    return chunks


def insert_chunks_to_bronze(supabase: Client, chunks: dict[str, list[dict]]):
    """Зберігає кожен логічний день як окремий батч у бронзовий шар."""
    if not chunks:
        print("⚠️ Немає нових подій для запису.")
        return

    for logical_date, day_events in sorted(chunks.items()):
        payload = {
            "device": "MacBook Air",
            "bucket_id": AW_BUCKET_ID,
            "logical_date": logical_date,
            "events_count": len(day_events),
            "events": day_events
        }

        supabase.table("bronze_screentime").insert({"raw_payload": payload}).execute()
        print(
            f"✅ Успішно завантажено чанк за логічну дату {logical_date} ({len(day_events)} подій) у bronze_screentime.")


if __name__ == "__main__":
    if check_already_ran_today():
        print("⏸️ Скрипт вже виконувався сьогодні. Пропускаємо.")
        exit(0)

    print("⏳ Отримуємо дані про екранний час з ActivityWatch...")
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    watermark = get_watermark(supabase_client)
    print(f"📌 Останній відомий час у базі (watermark): {watermark}")

    events = fetch_screentime_events(watermark)

    if events:
        chunks = group_events_by_logical_day(events)
        insert_chunks_to_bronze(supabase_client, chunks)
        save_run_date()
        print("🎉 Локальну інгестію екранного часу успішно завершено!")
    else:
        print("ℹ️ Нових подій у ActivityWatch не знайдено.")
        save_run_date()