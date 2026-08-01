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


def get_iphone_watermark(supabase: Client) -> datetime:
    """Отримує останній timestamp подій для iPhone 13 із etl_watermarks."""
    try:
        res = supabase.table("etl_watermarks").select("last_extracted_timestamp").eq("source_name", "iphone_13").execute()
        if res.data:
            iso_str = res.data[0]["last_extracted_timestamp"]
            # Заміна Z на +00:00 для коректного парсингу в Python
            return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except Exception as e:
        print(f"Не вдалося отримати watermark з Supabase: {e}")

    # За замовчуванням — за останні 24 години
    return datetime.now(timezone.utc) - timedelta(days=1)


def update_iphone_watermark(supabase: Client, raw_events: list[dict]):
    """Оновлює watermark новим максимальним часом після успішного збереження."""
    if not raw_events:
        return

    # Знаходимо максимальний timestamp серед подій
    max_ts_str = max(e["timestamp"] for e in raw_events if "timestamp" in e)
    max_dt = datetime.fromisoformat(max_ts_str.replace("Z", "+00:00"))

    try:
        supabase.table("etl_watermarks").update({
            "last_extracted_timestamp": max_dt.isoformat()
        }).eq("source_name", "iphone_13").execute()
        print(f"💧 Watermark для 'iphone_13' успішно оновлено до {max_dt.isoformat()}")
    except Exception as e:
        print(f"Помилка оновлення watermark: {e}")


def fetch_iphone_events_from_db(since_dt: datetime) -> list[dict]:
    """Витягує з knowledgeC.db тільки події, новіші за since_dt."""
    if not os.path.exists(ORIGINAL_DB_PATH):
        print(f"Базу даних за шляхом {ORIGINAL_DB_PATH} не знайдено.")
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
        print(f"Помилка зчитування knowledgeC.db: {e}")
    finally:
        if os.path.exists(TEMP_DB_PATH):
            os.remove(TEMP_DB_PATH)

    return events


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


def get_iphone_watermark(supabase: Client) -> datetime:
    """Отримує останній timestamp подій для iPhone 13 із etl_watermarks."""
    try:
        res = supabase.table("etl_watermarks").select("last_extracted_timestamp").eq("source_name", "iphone_13").execute()
        if res.data:
            iso_str = res.data[0]["last_extracted_timestamp"]
            # Заміна Z на +00:00 для коректного парсингу в Python
            return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except Exception as e:
        print(f"Не вдалося отримати watermark з Supabase: {e}")

    # За замовчуванням — за останні 24 години
    return datetime.now(timezone.utc) - timedelta(days=1)


def update_iphone_watermark(supabase: Client, raw_events: list[dict]):
    """Оновлює watermark новим максимальним часом після успішного збереження."""
    if not raw_events:
        return

    # Знаходимо максимальний timestamp серед подій
    max_ts_str = max(e["timestamp"] for e in raw_events if "timestamp" in e)
    max_dt = datetime.fromisoformat(max_ts_str.replace("Z", "+00:00"))

    try:
        supabase.table("etl_watermarks").update({
            "last_extracted_timestamp": max_dt.isoformat()
        }).eq("source_name", "iphone_13").execute()
        print(f"💧 Watermark для 'iphone_13' успішно оновлено до {max_dt.isoformat()}")
    except Exception as e:
        print(f"Помилка оновлення watermark: {e}")


def fetch_iphone_events_from_db(since_dt: datetime) -> list[dict]:
    """Витягує з knowledgeC.db тільки події, новіші за since_dt."""
    if not os.path.exists(ORIGINAL_DB_PATH):
        print(f"Базу даних за шляхом {ORIGINAL_DB_PATH} не знайдено.")
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
        print(f"Помилка зчитування knowledgeC.db: {e}")
    finally:
        if os.path.exists(TEMP_DB_PATH):
            os.remove(TEMP_DB_PATH)

    return events


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


def insert_iphone_to_bronze(supabase: Client, chunks: dict) -> bool:
    """Зберігає події у bronze_screentime по днях (чанах). Повертає True, якщо все успішно."""
    if not chunks:
        return False

    success = True
    for logical_date, day_events in sorted(chunks.items()):
        payload = {
            "device": "iPhone 13",
            "bucket_id": "knowledgeC_iphone_usage",
            "events_count": len(day_events),
            "events": day_events,
        }

        try:
            supabase.table("bronze_screentime").insert({
                "logical_date": logical_date,
                "raw_payload": payload
            }).execute()
            print(
                f"✅ Успішно збережено {len(day_events)} подій для iPhone 13 за дату {logical_date} у bronze_screentime!"
            )
        except Exception as e:
            print(f"❌ Помилка відправки в Supabase для дати {logical_date}: {e}")
            success = False

    return success


if __name__ == "__main__":
    print("⏳ Інкрементальний запуск зчитування для iPhone 13...")
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Читаємо стан (watermark) з таблиці
    last_processed_dt = get_iphone_watermark(supabase_client)
    print(f"Шукаємо події новіші за: {last_processed_dt.isoformat()}")

    # 2. Зчитуємо тільки дельта-дані з локальної SQLite бази
    iphone_events = fetch_iphone_events_from_db(last_processed_dt)

    # 3. Групуємо за логічними днями та записуємо в Bronze
    if iphone_events:
        chunks = group_events_by_logical_day(iphone_events)
        is_success = insert_iphone_to_bronze(supabase_client, chunks)
        if is_success:
            update_iphone_watermark(supabase_client, iphone_events)
    else:
        print("Нових подій з iPhone 13 з моменту останньої синхронізації немає.")

if __name__ == "__main__":
    print("⏳ Інкрементальний запуск зчитування для iPhone 13...")
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Читаємо стан (watermark) з нової таблиці
    last_processed_dt = get_iphone_watermark(supabase_client)
    print(f"Шукаємо події новіші за: {last_processed_dt.isoformat()}")

    # 2. Зчитуємо тільки дельта-дані з локальної SQLite бази macOS
    iphone_events = fetch_iphone_events_from_db(last_processed_dt)

    # 3. Записуємо в Bronze і, якщо успішно, оновлюємо watermark
    if iphone_events:
        is_success = insert_iphone_to_bronze(supabase_client, iphone_events)
        if is_success:
            update_iphone_watermark(supabase_client, iphone_events)
    else:
        print("Нових подій з iPhone 13 з моменту останньої синхронізації немає.")