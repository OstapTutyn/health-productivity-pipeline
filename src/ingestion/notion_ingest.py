import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

def fetch_notion_data():
    """Витягує ЛИШЕ ОДИН найновіший запис з бази щоденника в Notion."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    # сортуємо за час створення (або за колонкою дати) та беремо 1 запис
    payload = {
        "page_size": 1,  # Забираємо тільки 1 найновіший запис
        "sorts": [
            {
                "timestamp": "created_time",  # Сортуємо за часом створення
                "direction": "descending",  # Від найновішого до найстарішого
            }
        ],
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])

        if not results:
            print("⚠️ База Notion порожня.")
            return None

        print("✅ Найновіший запис з Notion успішно отримано!")
        # Повертаємо тільки цей один об'єкт (а не весь масив results)
        return results[0]
    else:
        print(f"❌ Помилка Notion API ({response.status_code}):")
        print(response.text)
        return None

def save_to_supabase(data):
    """Записує отриманий сирий JSON у таблицю bronze_journal в Supabase."""
    if not data:
        print("⚠️ Немає даних для збереження.")
        return

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    payload = {"raw_payload": data}
    supabase.table("bronze_journal").insert(payload).execute()
    print("🚀 Сирий JSON успішно завантажено в Supabase (bronze_journal)!")

if __name__ == "__main__":
    print("⏳ Запускаємо процес затягування даних з Notion...")
    data = fetch_notion_data()
    save_to_supabase(data)