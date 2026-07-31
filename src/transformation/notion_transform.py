import os
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def fetch_unprocessed_notion_records(supabase: Client) -> list[dict]:
    """Витягує необроблені нові записи з bronze_journal."""
    response = (
        supabase.table("bronze_journal")
        .select("id, raw_payload")
        .eq("is_processed", False)
        .execute()
    )
    return response.data if response.data else []


def get_existing_page_ids(supabase: Client) -> set[str]:
    """Отримує множину вже наявних notion_page_id з silver_journal, щоб уникнути дублікатів."""
    try:
        response = supabase.table("silver_journal").select("notion_page_id").execute()
        return {row["notion_page_id"] for row in response.data} if response.data else set()
    except Exception as e:
        print(f"Помилка отримання існуючих записів з silver_journal: {e}")
        return set()


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
    """Парсить одну сторінку щоденника з сирого пейлоаду під структуру silver_journal."""
    page_id = page.get("id")
    properties = page.get("properties", {})

    date_obj = properties.get("Дата", {}).get("date", {})
    date_str = date_obj.get("start") if date_obj else None

    if not date_str:
        created_time = page.get("created_time")
        if created_time:
            date_str = created_time.split("T")[0]
        else:
            return None, None

    try:
        clean_date_str = str(date_str).split("T")[0]
        entry_date = datetime.strptime(clean_date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except (ValueError, TypeError, AttributeError):
        return None, None

    energy_raw = properties.get("Енергія", {}).get("number")
    mood_raw = properties.get("Настрій", {}).get("number")
    stress_raw = properties.get("Стрес", {}).get("number")
    prod_raw = properties.get("Продуктивність", {}).get("number")

    overall_score = properties.get("Загальна оцінка дня", {}).get("formula", {}).get("number")

    notes_raw = properties.get("Лог", {}).get("rich_text", [])
    log_text = "".join([n.get("plain_text", "") for n in notes_raw]) if notes_raw else None

    tags_raw = properties.get("Тег", {}).get("multi_select", [])
    tags = [t.get("name") for t in tags_raw if t.get("name")] if tags_raw else []

    record = {
        "notion_page_id": page_id,
        "entry_date": entry_date,
        "overall_score": overall_score,
        "energy": clamp_int_metric(energy_raw),
        "mood": clamp_int_metric(mood_raw),
        "stress": clamp_int_metric(stress_raw),
        "productivity": clamp_int_metric(prod_raw),
        "tags": tags,
        "log_text": log_text,
    }
    return record, entry_date


def process_notion_transform(supabase: Client):
    records = fetch_unprocessed_notion_records(supabase)
    if not records:
        print("Необроблених даних у bronze_journal немає.")
        return

    processed_ids = [r["id"] for r in records]
    existing_page_ids = get_existing_page_ids(supabase)
    all_journal_records = []

    for record in records:
        payload = record.get("raw_payload", {})
        j_rec, _ = parse_notion_page(payload)

        if j_rec:
            page_id = j_rec["notion_page_id"]
            # Якщо запису ще немає в silver_journal — додаємо його
            if page_id not in existing_page_ids:
                all_journal_records.append(j_rec)
                existing_page_ids.add(page_id)
                можна
                додати
                щоб
                уникнути
                дублів
                усередині
                батчу
            else:
                print(f"Запис з notion_page_id {page_id} вже існує в silver_journal. Пропускаємо.")

    # Зберігаємо лише нові унікальні записи у silver_journal
    if all_journal_records:
        supabase.table("silver_journal").insert(all_journal_records).execute()
        print(f"Успішно додано {len(all_journal_records)} нових записів у silver_journal.")
    else:
        print("Нових унікальних записів для додавання немає.")

    # Позначаємо рядки в bronze_journal як оброблені
    supabase.table("bronze_journal").update(
        {"is_processed": True}
    ).in_("id", processed_ids).execute()
    print("Записи в bronze_journal успішно позначено як оброблені.")


if __name__ == "__main__":
    print("Запуск трансформації даних Notion...")
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    process_notion_transform(supabase_client)