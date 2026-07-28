import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

ORIGINAL_DB_PATH = os.path.expanduser(
    "~/Library/Application Support/Knowledge/knowledgeC.db"
)
TEMP_DB_PATH = "/tmp/knowledgeC_copy.db"
CORE_DATA_EPOCH_OFFSET = 978307200

# Чорний список десктопних додатків macOS
MACOS_EXCLUDED_KEYWORDS = [
    "pycharm", "finder", "iterm", "terminal", "docker",
    "postman", "vscode", "sublime", "activitywatch", "arc",
    "systempreferences", "system settings", "ical"
]


def get_last_processed_timestamp(supabase: Client) -> datetime:
    """Отримує найсвіжіший timestamp подій для iPhone 13 із бронзового шару."""
    try:
        res = (
            supabase.table("bronze_screentime")
            .select("raw_payload")
            .filter("raw_payload->>device", "eq", "iPhone 13")
            .order("inserted_at", desc=True)
            .limit(1)
            .execute()
        )

        if res.data and len(res.data) > 0:
            payload = res.data[0].get("raw_payload", {})
            events = payload.get("events", [])
            if events:
                # Знаходимо максимальний timestamp серед подій останнього батчу
                max_ts_str = max(e["timestamp"] for e in events if "timestamp" in e)
                return datetime.fromisoformat(max_ts_str)
    except Exception as e:
        print(f"⚠️ Не вдалося отримати останній timestamp із Supabase: {e}")

    # За замовчуванням (якщо база порожня) — забираємо за останні 24 години
    return datetime.now(timezone.utc) - timedelta(days=1)


def fetch_iphone_events_from_db(since_dt: datetime) -> list[dict]:
    """Витягує з knowledgeC.db тільки події, новіші за since_dt."""
    if not os.path.exists(ORIGINAL_DB_PATH):
        print(f"❌ Базу даних за шляхом {ORIGINAL_DB_PATH} не знайдено.")
        return []

    shutil.copy2(ORIGINAL_DB_PATH, TEMP_DB_PATH)

    events = []
    try:
        conn = sqlite3.connect(TEMP_DB_PATH)
        cursor = conn.cursor()

        now_utc = datetime.now(timezone.utc)

        # Переводимо datetime у Core Data timestamp
        core_data_start = since_dt.timestamp() - CORE_DATA_EPOCH_OFFSET
        core_data_end = now_utc.timestamp() - CORE_DATA_EPOCH_OFFSET

        # Отримуємо тільки НОВІ сесії використання
        query = """
            SELECT 
                ZVALUESTRING,
                ZSTARTDATE,
                ZENDDATE
            FROM ZOBJECT
            WHERE ZSTREAMNAME = '/app/usage'
              AND ZSTARTDATE > ?
              AND ZSTARTDATE <= ?
            ORDER BY ZSTARTDATE ASC
        """

        cursor.execute(query, (core_data_start, core_data_end))
        rows = cursor.fetchall()

        for row in rows:
            bundle_id, start_cd, end_cd = row
            if not bundle_id or not start_cd or not end_cd:
                continue

            app_raw = bundle_id.lower()

            # Пропускаємо маківські програми
            if any(keyword in app_raw for keyword in MACOS_EXCLUDED_KEYWORDS):
                continue

            start_dt = datetime.fromtimestamp(start_cd + CORE_DATA_EPOCH_OFFSET, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(end_cd + CORE_DATA_EPOCH_OFFSET, tz=timezone.utc)
            duration_seconds = max(0, (end_dt - start_dt).total_seconds())

            if duration_seconds > 0:
                app_name = bundle_id.split(".")[-1].capitalize()

                events.append({
                    "timestamp": start_dt.isoformat(),
                    "duration": duration_seconds,
                    "data": {
                        "app": app_name,
                        "bundle_id": bundle_id
                    }
                })

        conn.close()
    except Exception as e:
        print(f"⚠️ Помилка зчитування knowledgeC.db: {e}")
    finally:
        if os.path.exists(TEMP_DB_PATH):
            os.remove(TEMP_DB_PATH)

    return events


def insert_iphone_to_bronze(supabase: Client, raw_events: list[dict]):
    if not raw_events:
        print("ℹ️ Нових подій з iPhone 13 з моменту останньої синхронізації немає.")
        return

    payload = {
        "device": "iPhone 13",
        "bucket_id": "knowledgeC_iphone_usage",
        "events_count": len(raw_events),
        "events": raw_events,
    }

    try:
        supabase.table("bronze_screentime").insert(
            {"raw_payload": payload}
        ).execute()
        print(
            f"✅ Успішно збережено {len(raw_events)} НОВИХ подій для iPhone 13 у bronze_screentime!"
        )
    except Exception as e:
        print(f"❌ Помилка відправки в Supabase: {e}")


if __name__ == "__main__":
    print("⏳ Інкрементальний запуск зчитування для iPhone 13...")
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Визначаємо, від якого моменту шукати події
    last_processed_dt = get_last_processed_timestamp(supabase_client)
    print(f"🔎 Шукаємо події новіші за: {last_processed_dt.isoformat()}")

    # 2. Зчитуємо тільки дельта-дані з бази
    iphone_events = fetch_iphone_events_from_db(last_processed_dt)

    # 3. Записуємо в Bronze тільки якщо є нові події
    insert_iphone_to_bronze(supabase_client, iphone_events)