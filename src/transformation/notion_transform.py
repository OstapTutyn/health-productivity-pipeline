import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def fetch_unprocessed_records(supabase: Client) -> list[dict]:
    """Витягує всі батчі з Bronze, які ще не були оброблені."""
    response = (
        supabase.table("bronze_journal")
        .select("id, raw_payload")
        .eq("is_processed", False)
        .execute()
    )
    return response.data if response.data else []


def clamp_int_metric(value, min_val=1, max_val=10):
    """Конвертує в ціле число (int) та обмежує від 1 до 10 (для int2 колонок)."""
    if value is None:
        return None
    try:
        val = int(round(float(value)))
        return max(min_val, min(max_val, val))
    except (ValueError, TypeError):
        return None


def clamp_float_metric(value, min_val=1.0, max_val=10.0):
    """Конвертує в дробове число (float) та обмежує (для numeric колонок)."""
    if value is None:
        return None
    try:
        val = float(value)
        return max(min_val, min(max_val, val))
    except (ValueError, TypeError):
        return None


def parse_notion_journal(raw_json: dict) -> dict:
    """Трансформує сирий JSON із Notion у чистий словник із валідацією якості даних."""
    if not raw_json:
        return None

    props = raw_json.get("properties", {})

    # 1. Складні поля (теги, лог, дата)
    multi_select = props.get("Тег", {}).get("multi_select", [])
    tags = [t.get("name") for t in multi_select if "name" in t]

    rich_text = props.get("Лог", {}).get("rich_text", [])
    log_text = rich_text[0].get("plain_text") if rich_text else None

    date_block = props.get("Дата", {}).get("date")
    entry_date = date_block.get("start") if date_block else None

    # 2. Метрики з Data Quality Checks (відповідно до типів БД)
    overall_score = clamp_float_metric(props.get("Загальна оцінка дня", {}).get("formula", {}).get("number"))
    energy = clamp_int_metric(props.get("Енергія", {}).get("number"))
    mood = clamp_int_metric(props.get("Настрій", {}).get("number"))
    stress = clamp_int_metric(props.get("Стрес", {}).get("number"))
    productivity = clamp_int_metric(props.get("Продуктивність", {}).get("number"))

    return {
        "notion_page_id": raw_json.get("id"),
        "entry_date": entry_date,
        "overall_score": overall_score,
        "energy": energy,
        "mood": mood,
        "stress": stress,
        "productivity": productivity,
        "tags": tags,
        "log_text": log_text,
    }


def upsert_to_silver(supabase: Client, records: list[dict]):
    """Робить масовий UPSERT (вставку або оновлення) у таблицю silver_journal."""
    if not records:
        return

    supabase.table("silver_journal").upsert(records, on_conflict="notion_page_id").execute()
    print(f"Дані успішно трансформовано та збережено в silver_journal ({len(records)} записів)!")


def mark_as_processed(supabase: Client, record_ids: list[int]):
    """Позначає оброблені записи у Bronze."""
    if not record_ids:
        return

    supabase.table("bronze_journal").update(
        {"is_processed": True}
    ).in_("id", record_ids).execute()
    print(f"Позначено {len(record_ids)} батчів у bronze_journal як is_processed = True.")


if __name__ == "__main__":
    print("Запускаємо трансформацію Bronze ➔ Silver для Notion...")
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    unprocessed_records = fetch_unprocessed_records(supabase_client)

    if unprocessed_records:
        parsed_records = []
        processed_ids = []

        for record in unprocessed_records:
            parsed_data = parse_notion_journal(record["raw_payload"])
            if parsed_data and parsed_data.get("notion_page_id"):
                parsed_records.append(parsed_data)
            processed_ids.append(record["id"])

        if parsed_records:
            upsert_to_silver(supabase_client, parsed_records)

        mark_as_processed(supabase_client, processed_ids)
    else:
        print("Усі записи в bronze_journal вже оброблені. Нових даних немає.")