import os
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")


def get_notion_watermark(supabase: Client) -> str:
    """Отримує timestamp останнього завантаженого запису з etl_watermarks."""
    try:
        res = supabase.table("etl_watermarks").select("last_extracted_timestamp").eq("source_name",
                                                                                     "notion_journal").execute()
        if res.data:
            return res.data[0]["last_extracted_timestamp"]
    except Exception as e:
        print(f"Не вдалося отримати watermark з Supabase: {e}")

    # Fallback: останні 24 години, якщо бази недоступна
    default_ts = datetime.now(timezone.utc) - timedelta(days=1)
    return default_ts.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def update_notion_watermark(supabase: Client, pages: list[dict]):
    """Оновлює watermark найновішим часом редагування серед завантажених сторінок."""
    edited_times = [p.get("last_edited_time") for p in pages if "last_edited_time" in p]
    if not edited_times:
        return

    max_ts = max(edited_times)

    try:
        supabase.table("etl_watermarks").update({
            "last_extracted_timestamp": max_ts
        }).eq("source_name", "notion_journal").execute()
        print(f"💧 Watermark для 'notion_journal' успішно оновлено до {max_ts}")
    except Exception as e:
        print(f"Помилка оновлення watermark: {e}")


def fetch_notion_data(watermark_iso: str) -> list[dict]:
    """Витягує ВСІ записи, які були створені або змінені після watermark_iso."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    # Фільтруємо за часом редагування, щоб ловити навіть оновлення старих записів
    payload = {
        "filter": {
            "timestamp": "last_edited_time",
            "last_edited_time": {
                "after": watermark_iso
            }
        },
        "sorts": [
            {
                "timestamp": "last_edited_time",
                "direction": "ascending"
            }
        ]
    }

    all_results = []
    has_more = True
    next_cursor = None

    # Цикл обробляє пагінацію (на випадок, якщо відредаговано більше 100 сторінок за раз)
    while has_more:
        if next_cursor:
            payload["start_cursor"] = next_cursor

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            all_results.extend(results)

            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")
        else:
            print(f"Помилка Notion API ({response.status_code}): {response.text}")
            break

    return all_results


def insert_notion_to_bronze(supabase: Client, pages: list[dict]) -> bool:
    """Зберігає список сирих сторінок у bronze_journal."""
    if not pages:
        return False

    # Кожну сторінку зберігаємо як окремий JSON-об'єкт в окремому рядку
    payloads = [{"raw_payload": page} for page in pages]

    try:
        supabase.table("bronze_journal").insert(payloads).execute()
        print(f"Успішно збережено {len(pages)} НОВИХ/ОНОВЛЕНИХ записів з Notion у bronze_journal!")
        return True
    except Exception as e:
        print(f"Помилка збереження в Supabase: {e}")
        return False


if __name__ == "__main__":
    print("⏳ Запускаємо інкрементальне затягування даних з Notion...")
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Читаємо стан (watermark)
    last_processed_dt = get_notion_watermark(supabase_client)
    print(f"Шукаємо записи Notion, відредаговані після: {last_processed_dt}")

    # 2. Отримуємо дані
    new_pages = fetch_notion_data(last_processed_dt)

    # 3. Зберігаємо і, якщо успішно, оновлюємо watermark
    if new_pages:
        is_success = insert_notion_to_bronze(supabase_client, new_pages)
        if is_success:
            update_notion_watermark(supabase_client, new_pages)
    else:
        print("Нових або оновлених записів у щоденнику Notion не знайдено.")