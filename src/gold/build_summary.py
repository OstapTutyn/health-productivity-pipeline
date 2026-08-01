import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if __name__ == "__main__":
    print("⏳ Запуск оновлення Gold-вітрини (gold_daily_summary)...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    try:
        # Викликаємо функцію через RPC
        response = supabase.rpc("refresh_gold_summary").execute()
        print("Gold-вітрина успішно оновлена!")
    except Exception as e:
        print(f"Помилка при оновленні Gold-вітрини: {e}")
        exit(1)