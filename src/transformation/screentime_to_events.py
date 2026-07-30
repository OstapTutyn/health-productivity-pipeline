import os
import re
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


def parse_app_or_website(app_name: str, window_title: str) -> str:
    """Витягує назву конкретного сайту, якщо відкритий браузер."""
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


def transform_to_events(payload: dict) -> list[dict]:
    """Розпаковує сирий payload у список очищених, дедуплікованих подій із розпізнаванням сайтів."""
    events = payload.get("events", [])
    device = payload.get("device", "Unknown device")

    unique_events = {}
    for event in events:
        data = event.get("data", {})
        started_at = event.get("timestamp")
        raw_app = data.get("app", "Unknown")
        window_title = data.get("title", "")
        duration = event.get("duration", 0)

        # --- DATA QUALITY CHECKS ---
        if duration <= 0 or duration > 86400:
            continue

        # --- РОЗПІЗНАВАННЯ САЙТІВ ---
        parsed_app_name = parse_app_or_website(raw_app, window_title)

        # Ключ для унікальності
        key = (device, started_at, parsed_app_name)

        unique_events[key] = {
            "device": device,
            "app_name": parsed_app_name,  # Тепер тут буде GitHub, YouTube або конкретний домен
            "window_title": window_title,
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
            clean_events = transform_to_events(record["raw_payload"])
            all_clean_events.extend(clean_events)
            processed_ids.append(record["id"])

        if all_clean_events:
            upsert_to_silver(supabase_client, all_clean_events)

        mark_as_processed(supabase_client, processed_ids)
    else:
        print("Усі записи в bronze_screentime вже оброблені. Нових даних немає.")