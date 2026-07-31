import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def fetch_unprocessed_notion_records(supabase: Client) -> list[dict]:
    """Витягує необроблені батчі з bronze_notion."""
    try:
        response = (
            supabase.table("bronze_notion")
            .select("id, raw_payload")
            .eq("is_processed", False)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        print(f"Помилка отримання даних з bronze_notion: {e}")
        return []


def clamp_int_metric(val, min_val=1, max_val=10):
    """Валідує та обмежує цілочисельні мітки в межах норми."""
    if val is None:
        return None
    try:
        num = int(val)
        return max(min_val, min(max_val, num))
    except (ValueError, TypeError):
        return None


def parse_notion_pages(payload: dict) -> tuple[list[dict], set[str]]:
    """Парсить сторінки щоденника з сирого пейлоаду та повертає записи і множину дат."""
    pages = payload.get("pages", [])
    journal_records = []
    processed_dates = set()

    for page in pages:
        properties = page.get("properties", {})

        # Витягуємо дату з урахуванням вкладеної структури Notion API та української назви поля
        date_obj = properties.get("Дата", {}).get("date", {})
        date_str = date_obj.get("start") if date_obj else None

        if not date_str:
            # Фолбек на дату створення, якщо дата не вказана явно
            created_time = page.get("created_time")
            if created_time:
                date_str = created_time.split("T")[0]
            else:
                continue

        entry_date = datetime.fromisoformat(date_str).strftime("%Y-%m-%d")
        processed_dates.add(entry_date)

        # Витягуємо мітки та текст за правильними назвами у Notion
        energy_raw = properties.get("Енергія", {}).get("number")
        mood_raw = properties.get("Настрій", {}).get("number")
        notes_raw = properties.get("Лог", {}).get("rich_text", [])

        notes = "".join([n.get("plain_text", "") for n in notes_raw]) if notes_raw else None

        journal_records.append({
            "entry_date": entry_date,
            "energy_level": clamp_int_metric(energy_raw),
            "mood_score": clamp_int_metric(mood_raw),
            "notes": notes,
        })

    return journal_records, processed_dates


def generate_missing_null_records(supabase: Client, processed_dates: set[str]):
    """Генерує NULL-записи для днів, коли щоденник не заповнювався (забув записати)."""
    if not processed_dates:
        return

    min_date_str = min(processed_dates)
    min_date = datetime.strptime(min_date_str, "%Y-%m-%d").date()
    today = datetime.now(timezone.utc).date()

    current_date = min_date
    null_records = []

    while current_date <= today:
        date_str = current_date.strftime("%Y-%m-%d")
        if date_str not in processed_dates:
            null_records.append({
                "entry_date": date_str,
                "energy_level": None,
                "mood_score": None,
                "notes": None,
            })
        current_date += timedelta(days=1)

    if null_records:
        try:
            supabase.table("silver_journal").upsert(
                null_records, on_conflict="entry_date"
            ).execute()
            print(f"Створено {len(null_records)} NULL-записів для пропущених днів у silver_journal.")
        except Exception as e:
            print(f"Помилка генерації NULL-записів для щоденника: {e}")


def process_notion_transform(supabase: Client):
    records = fetch_unprocessed_notion_records(supabase)
    if not records:
        print("Необроблених даних у bronze_notion немає.")
        return

    processed_ids = [r["id"] for r in records]
    all_journal_records = []
    all_processed_dates = set()

    for record in records:
        payload = record.get("raw_payload", {})
        j_records, p_dates = parse_notion_pages(payload)
        all_journal_records.extend(j_records)
        all_processed_dates.update(p_dates)

    # 1. Зберігаємо реальні записи у silver_journal
    if all_journal_records:
        try:
            supabase.table("silver_journal").upsert(
                all_journal_records, on_conflict="entry_date"
            ).execute()
            print(f"Успішно збережено {len(all_journal_records)} записів у silver_journal.")
        except Exception as e:
            print(f"Помилка запису у silver_journal: {e}")

    # 2. Заповнюємо пропущені дні NULL-значеннями (захист від забутого щоденника)
    if all_processed_dates:
        generate_missing_null_records(supabase, all_processed_dates)

    # 3. Позначаємо батчі в Bronze як оброблені
    try:
        supabase.table("bronze_notion").update(
            {"is_processed": True}
        ).in_("id", processed_ids).execute()
        print("Батчі в bronze_notion успішно позначено як оброблені.")
    except Exception as e:
        print(f"Помилка оновлення статусу в bronze_notion: {e}")


if __name__ == "__main__":
    print("Запуск трансформації даних Notion...")
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    process_notion_transform(supabase_client)