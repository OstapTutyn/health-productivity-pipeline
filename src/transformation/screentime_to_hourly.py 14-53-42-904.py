import os
import re
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def parse_app_or_website(app_name: str, window_title: str) -> str:
    browsers = ["Google Chrome", "Safari", "Arc", "Firefox"]

    if app_name not in browsers or not window_title:
        return app_name

    title_lower = window_title.lower()

    if "gemini" in title_lower:
        return "Google Gemini"
    elif "github" in title_lower:
        return "GitHub"
    elif "supabase" in title_lower:
        return "Supabase"
    elif "localhost" in title_lower or "127.0.0.1" in title_lower:
        return "Localhost (Dev)"
    elif "youtube" in title_lower:
        return "YouTube"
    elif "notion" in title_lower:
        return "Notion Web"
    elif "google search" in title_lower or "пошук google" in title_lower:
        return "Google Search"
    elif "перекладач" in title_lower or "translate" in title_lower:
        return "Google Translate"

    domain_match = re.search(r"([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", window_title)
    if domain_match:
        return domain_match.group(1)

    return f"{app_name} (Web)"


def get_app_category(app_or_site: str) -> str:
    categories = {
        "PyCharm": "Development",
        "VS Code": "Development",
        "Terminal": "Development",
        "GitHub": "Development",
        "Localhost (Dev)": "Development",
        "Supabase": "Development",
        "Google Gemini": "AI / Research",
        "Google Search": "Browsing / Research",
        "Google Translate": "Browsing / Research",
        "Notion": "Productivity",
        "Notion Web": "Productivity",
        "Telegram": "Communication",
        "YouTube": "Entertainment",
        "Music": "Entertainment",
        "Apple Music": "Entertainment",
    }
    return categories.get(app_or_site, "Other")


def fetch_unprocessed_bronze_records(supabase: Client) -> list[dict]:
    response = (
        supabase.table("bronze_screentime")
        .select("id, raw_payload")
        .eq("is_processed", False)
        .execute()
    )
    return response.data if response.data else []


def transform_data(records: list[dict]) -> list[dict]:
    hourly_app_durations = {}

    for record in records:
        payload = record.get("raw_payload", {})
        events = payload.get("events", [])
        device = payload.get("device", "Unknown device")

        for event in events:
            raw_timestamp = event.get("timestamp")
            if not raw_timestamp:
                continue

            event_time = datetime.fromisoformat(raw_timestamp)
            hourly_ts = event_time.replace(minute=0, second=0, microsecond=0)
            hourly_ts_str = hourly_ts.isoformat()
            entry_date_str = str(hourly_ts.date())

            raw_app = event.get("data", {}).get("app", "Unknown")
            window_title = event.get("data", {}).get("title", "")
            duration = event.get("duration", 0)

            display_name = parse_app_or_website(raw_app, window_title)

            group_key = (hourly_ts_str, entry_date_str, device, display_name)
            hourly_app_durations[group_key] = (
                hourly_app_durations.get(group_key, 0) + duration
            )

    transformed_records = []
    for (hourly_ts_str, entry_date_str, device, app_name), total_seconds in hourly_app_durations.items():
        transformed_records.append({
            "hourly_timestamp": hourly_ts_str,
            "entry_date": entry_date_str,
            "active_device": device,
            "app_name": app_name,
            "category": get_app_category(app_name),
            "active_minutes": round(total_seconds / 60, 2),
        })

    return transformed_records


def upsert_hourly_summary(supabase: Client, hourly_data: list[dict]):
    if not hourly_data:
        return

    supabase.table("stg_screentime_hourly").upsert(
        hourly_data,
        on_conflict="hourly_timestamp,active_device,app_name"
    ).execute()

    print(f"Успішно збережено/оновлено {len(hourly_data)} записів у stg_screentime_hourly!")


def mark_bronze_records_as_processed(supabase: Client, record_ids: list[int]):
    if not record_ids:
        return

    supabase.table("bronze_screentime").update(
        {"is_processed": True}
    ).in_("id", record_ids).execute()

    print(f"Позначено {len(record_ids)} батчів у Bronze як is_processed = True.")


if __name__ == "__main__":
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Шукаємо необроблені записи в Bronze...")
    unprocessed_records = fetch_unprocessed_bronze_records(supabase_client)

    if unprocessed_records:
        record_ids = [r["id"] for r in unprocessed_records]
        print(f"Знайдено {len(unprocessed_records)} необроблених батчів. Обробляємо...")

        transformed_data = transform_data(unprocessed_records)

        print("Вставляємо трансформовані дані в stg_screentime_hourly...")
        upsert_hourly_summary(supabase_client, transformed_data)

        print("Оновлюємо статус у Bronze...")
        mark_bronze_records_as_processed(supabase_client, record_ids)

        print("ІНКРЕМЕНТАЛЬНУ ОБРОБКУ ЗАВЕРШЕНО УСПІШНО!")
    else:
        print("Усі записи в Bronze вже оброблені. Нових даних немає.")