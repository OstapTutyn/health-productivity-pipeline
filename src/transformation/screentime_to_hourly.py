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


def fetch_latest_bronze_record(supabase: Client) -> dict:
    payload = (
        supabase.table("bronze_screentime")
        .select("raw_payload")
        .order("inserted_at", desc=True)
        .limit(1)
        .execute()
    )

    if payload.data:
        return payload.data[0]["raw_payload"]
    return {}


def transform_data(payload: dict) -> list[dict]:
    events = payload.get("events", [])
    device = payload.get("device", "Unknown device")

    if not events:
        return []

    first_event_time = datetime.fromisoformat(events[0]["timestamp"])
    hourly_ts = first_event_time.replace(minute=0, second=0, microsecond=0)

    app_durations = {}

    for event in events:
        raw_app = event.get("data", {}).get("app", "Unknown")
        window_title = event.get("data", {}).get("title", "")
        duration = event.get("duration", 0)

        display_name = parse_app_or_website(raw_app, window_title)
        app_durations[display_name] = app_durations.get(display_name, 0) + duration

    records = []
    for app_or_site, seconds in app_durations.items():
        records.append({
            "hourly_timestamp": hourly_ts.isoformat(),
            "entry_date": str(hourly_ts.date()),
            "active_device": device,
            "app_name": app_or_site,
            "category": get_app_category(app_or_site),
            "active_minutes": round(seconds / 60, 2)
        })

    return records


def upsert_hourly_summary(supabase: Client, hourly_data: list[dict]):
    if not hourly_data:
        print("Немає даних для збереження.")
        return

    supabase.table("stg_screentime_hourly").upsert(
        hourly_data,
        on_conflict="hourly_timestamp,active_device,app_name"
    ).execute()

    print("Погодинні деталізовані дані успішно збережено!")


if __name__ == "__main__":
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Зчитуємо дані з Bronze...")
    raw_payload = fetch_latest_bronze_record(supabase_client)

    if raw_payload:
        print("Розраховуємо погодинну агрегацію та витягуємо сайти...")
        hourly_summary = transform_data(raw_payload)

        print("Вставляємо в stg_screentime_hourly...")
        upsert_hourly_summary(supabase_client, hourly_summary)
    else:
        print("Не вдалося знайти записи в bronze_screentime.")