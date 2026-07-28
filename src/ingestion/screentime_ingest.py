import os
import json
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

AW_BUCKET_ID = "aw-watcher-window_MacBook-Air-Ostap.local"
AW_URL = f"http://localhost:5600/api/0/buckets/{AW_BUCKET_ID}/events"
BUFFER_FILE = "events_buffer.json"


def load_local_buffer() -> list[dict]:
    """Зчитує накопичені події з локального файлу на диску."""
    if os.path.exists(BUFFER_FILE):
        try:
            with open(BUFFER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    print(f"📦 Знайдено {len(data)} невідправлених подій у локальному буфері.")
                return data
        except Exception as e:
            print(f"⚠️ Помилка зчитання буфера: {e}")
            return []
    return []


def save_local_buffer(events: list[dict]):
    """Записує події у локальний файл для захисту від вимкнення Mac."""
    with open(BUFFER_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)


def clear_local_buffer():
    """Видаляє буфер після успішної відправки в Supabase."""
    if os.path.exists(BUFFER_FILE):
        os.remove(BUFFER_FILE)


def fetch_screentime_events(limit: int = 100) -> list[dict]:
    """Витягує нові події з ActivityWatch."""
    try:
        params = {"limit": limit}
        response = requests.get(AW_URL, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️ Не вдалося отримати дані з ActivityWatch: {e}")
        return []


def insert_to_bronze(supabase: Client, raw_events: list[dict]) -> bool:
    """Відправляє події у bronze_screentime. Повертає True, якщо відправка успішна."""
    if not raw_events:
        print("⚠️ Немає нових подій для запису.")
        return True

    payload = {
        "device": "MacBook Air",
        "bucket_id": AW_BUCKET_ID,
        "events_count": len(raw_events),
        "events": raw_events
    }

    try:
        supabase.table("bronze_screentime").insert({"raw_payload": payload}).execute()
        print(f"✅ Успішно збережено {len(raw_events)} подій у bronze_screentime!")
        return True
    except Exception as e:
        print(f"❌ Помилка відправки в Supabase: {e}")
        return False


if __name__ == "__main__":
    print("⏳ Перевіряємо буфер та отримуємо дані про екранний час...")

    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Завантажуємо невідправлені події з диска (якщо ноут вимикався або не було мережі)
    buffered_events = load_local_buffer()

    # 2. Витягуємо нові події з ActivityWatch
    new_events = fetch_screentime_events(limit=100)

    # 3. Об'єднуємо події та прибираємо можливі дублікати за id події
    all_events_dict = {ev["id"]: ev for ev in (buffered_events + new_events) if "id" in ev}
    combined_events = list(all_events_dict.values()) if all_events_dict else (buffered_events + new_events)

    if combined_events:
        # 4. Негайно дампимо все на диск перед відправкою (захист)
        save_local_buffer(combined_events)

        # 5. Пробуємо відправити у Supabase
        success = insert_to_bronze(supabase_client, combined_events)

        if success:
            # 6. Очищаємо диск ТІЛЬКИ якщо Supabase прийняв дані
            clear_local_buffer()
            print("🧹 Локальний буфер очищено.")
        else:
            print("💾 Відправка не вдалася. Події збережено на диску до наступного запуску.")
    else:
        print("✨ Немає нових подій для обробки.")