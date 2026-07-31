import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def fetch_unprocessed_notion_records(supabase: Client) -> list[dict]:
    """Витягує необроблені записи з bronze_journal."""
    try:
        response = (
            supabase.table("bronze_journal")
            .select("id, raw_payload")
            .eq("is_processed", False)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        print(f"Помилка отримання даних з bronze_journal: {e}")
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


def parse_notion_page(page: dict) -> tuple[dict | None, str | None]:
    """Парсить одну сторінку щоденника з сирого пейлоаду."""
    properties = page.get("properties", {})

    # Витягуємо дату з урахуванням вкладеної структури Notion API та української назви поля
    date_obj = properties.get("Дата", {}).get("date", {})
    date_str = date_obj.get("start") if date_obj else None

    if not date_str:
        created_time = page.get("created_time")
        if created_time:
            date_str = created_time.split("T")[0]
        else:
            return None, None

    entry_date = datetime.fromisoformat(date_str).strftime("%Y-%m-%d")

    # Витягуємо мітки та текст за правильними назвами у Notion
    energy_raw = properties.get("Енергія", {}).get("number")
    mood_raw = properties.get("Настрій", {}).get("number")
    notes_raw = properties.get("Лог", {}).get("rich_text", [])

    notes = "".join([n.get("plain_text", "") for n in notes_raw]) if notes_raw else None

    record = {
        "entry_date": entry_date,
        "energy_level": clamp_int_metric(energy_raw),
        "mood_score": clamp_int_metric(mood_raw),
        "notes": notes,
    }
    return record, entry_date


def generate_missing_null_records(supabase: Client, processed_dates: set[str]):
    """Генерує NULL-записи для днів, коли щоденник не заповнювався."""
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
        print("Необроблених даних у bronze_journal немає.")
        return

    processed_ids = [r["id"] for r in records]
    all_journal_records = []
    all_processed_dates = set()

    for record in records:
        # Кожен рядок у bronze_journal — це окрема сторінка у raw_payload
        payload = record.get("raw_payload", {})
        j_rec, p_date = parse_notion_page(payload)
        if j_rec:
            all_journal_records.append(j_rec)
        if p_date:
            all_processed_dates.add(p_date)

    # 1. Зберігаємо реальні записи у silver_journal
    if all_journal_records:
        try:
            supabase.table("silver_journal").upsert(
                all_journal_records, on_conflict="entry_date"
            ).execute()
            print(f"Успішно збережено {len(all_journal_records)} записів у silver_journal.")
        except Exception as e:
            print(f"Помилка запису у silver_journal: {e}")

    # 2. Заповнюємо пропущені дні NULL-значеннями
    if all_processed_dates:
        generate_missing_null_records(supabase, all_processed_dates)

    # 3. Позначаємо рядки в bronze_journal як оброблені
    try:
        supabase.table("bronze_journal").update(
            {"is_processed": True}
        ).in_("id", processed_ids).execute()
        print("Записи в bronze_journal успішно позначено як оброблені.")
    except Exception as e:
        print(f"Помилка оновлення статусу в bronze_journal: {e}")


if __name__ == "__main__":
    print("Запуск трансформації даних Notion...")
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    process_notion_transform(supabase_client)