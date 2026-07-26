import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def fetch_latest_bronze_record(supabase: Client) -> dict:
    response = (
        supabase.table("bronze_journal")
        .select("raw_payload")
        .order("inserted_at", desc=True)
        .limit(1)
        .execute()
    )

    if response.data:
        # Повертаємо сам JSON-об'єкт із першого рядка
        return response.data[0]["raw_payload"]
    return None


def parse_notion_journal(raw_json: dict) -> dict:
    """Трансформує сирий JSON із Notion у чистий словник для silver_journal."""
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

    # 2. Витягуємо числові метрики
    overall_score = props.get("Загальна оцінка дня", {}).get("formula", {}).get("number")
    energy = props.get("Енергія", {}).get("number")
    mood = props.get("Настрій", {}).get("number")
    stress = props.get("Стрес", {}).get("number")
    productivity = props.get("Продуктивність", {}).get("number")

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


def upsert_to_silver(supabase: Client, data: dict):
    """Робить UPSERT (вставку або оновлення) у таблицю silver_journal."""
    if not data:
        print("Немає даних для запису у Silver.")
        return

    supabase.table("silver_journal").upsert(data).execute()
    print("Дані успішно трансформовано та збережено в silver_journal!")


if __name__ == "__main__":
    print("Запускаємо трансформацію Bronze ➔ Silver...")

    # Створюємо підключення
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Читаємо Bronze
    raw_record = fetch_latest_bronze_record(supabase_client)

    # 2. Трансформуємо
    parsed_record = parse_notion_journal(raw_record)

    # 3. Пишемо в Silver
    upsert_to_silver(supabase_client, parsed_record)