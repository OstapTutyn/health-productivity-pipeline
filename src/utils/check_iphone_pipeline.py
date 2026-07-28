import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def inspect_iphone_pipeline():
    print("==================================================")
    print("ДІАГНОСТИКА ІФОН-ПАЙПЛАЙНУ (BRONZE ➔ SILVER)")
    print("==================================================\n")

    # 1. Отримуємо останній батч з Bronze для iPhone 13
    res = supabase.table("bronze_screentime") \
        .select("*") \
        .filter("raw_payload->>device", "eq", "iPhone 13") \
        .order("inserted_at", desc=True) \
        .limit(1) \
        .execute()

    if not res.data:
        print("❌ Жодного батчу для 'iPhone 13' у bronze_screentime не знайдено!")
        return

    latest_batch = res.data[0]
    batch_id = latest_batch["id"]
    inserted_at = latest_batch["inserted_at"]
    is_processed = latest_batch["is_processed"]
    payload = latest_batch["raw_payload"]
    events = payload.get("events", [])

    print(f"Останній Bronze батч ID: {batch_id}")
    print(f"Записано в Bronze: {inserted_at}")
    print(f"Статус обробки (is_processed): {is_processed}")
    print(f"Кількість подій у батчі: {len(events)}\n")

    if not events:
        print("Батч порожній.")
        return

    # 2. Перевірка реальності даних з iPhone (Bundle IDs)
    print("--- 1. Перевірка Джерела Даних (чи це справді iPhone?) ---")
    bundle_ids = set(e.get("data", {}).get("bundle_id", "") for e in events if e.get("data", {}).get("bundle_id"))
    mobile_samples = [b for b in bundle_ids if "apple" in b or "burbn" in b or "zhiliao" in b or "google" in b][:5]
    print(f"Приклади Bundle IDs з бази: {mobile_samples if mobile_samples else list(bundle_ids)[:5]}")

    # 3. Перевірка дат, тривалості та дублікатів
    print("\n--- 2. Перевірка Часу, Тривалості та Дублікатів ---")
    invalid_durations = 0
    seen_events = set()
    duplicates_count = 0

    for e in events:
        ts = e.get("timestamp")
        dur = e.get("duration", 0)
        app = e.get("data", {}).get("app")

        if dur <= 0:
            invalid_durations += 1

        event_key = (app, ts)
        if event_key in seen_events:
            duplicates_count += 1
        else:
            seen_events.add(event_key)

    print(f"Подій із некоректною тривалістю (<= 0 сек): {invalid_durations}")
    print(f"Кількість дублікатів усередині батчу: {duplicates_count}")

    # Приклад першого івенту
    first_ev = events[0]
    print(
        f"Приклад першої події: Додаток={first_ev.get('data', {}).get('app')}, Старт={first_ev.get('timestamp')}, Тривалість={first_ev.get('duration')} сек")

    # 4. Перевірка трансформації у Silver
    print("\n--- 3. Перевірка Трансформації у Silver (stg_screentime_hourly) ---")
    silver_res = supabase.table("stg_screentime_hourly") \
        .select("*") \
        .eq("active_device", "iPhone 13") \
        .order("created_at", desc=True) \
        .limit(5) \
        .execute()

    if not silver_res.data:
        print("⚠У Silver-таблиці (stg_screentime_hourly) ще немає записів для iPhone 13.")
        print("Запусти: .venv/bin/python src/transformation/screentime_to_hourly.py")
    else:
        print(f"У Silver знайшовся {len(silver_res.data)} останніх агрегованих записів під 'iPhone 13':")
        for row in silver_res.data:
            print(
                f"   • [{row['hourly_timestamp']}] {row['app_name']} -> {row.get('duration_minutes', 0)} хв (Категорія: {row.get('category', 'N/A')})")


if __name__ == "__main__":
    inspect_iphone_pipeline()