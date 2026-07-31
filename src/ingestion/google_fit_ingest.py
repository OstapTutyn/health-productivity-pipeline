import os
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv
from supabase import create_client, Client

SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.sleep.read',
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/fitness.heart_rate.read'
]

def get_google_credentials():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())
    return creds

if __name__ == "__main__":
    load_dotenv()
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    credentials = get_google_credentials()
    service = build('fitness', 'v1', credentials=credentials)

    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    start_time_daily = (now - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. Запит погодинних метрик
    hourly_payload = {
        "aggregateBy": [
            {"dataTypeName": "com.google.step_count.delta"},
            {"dataTypeName": "com.google.heart_rate.bpm"},
            {"dataTypeName": "com.google.calories.expended"}
        ],
        "bucketByTime": {"durationMillis": 900000},
        "startTimeMillis": int(yesterday.timestamp() * 1000),
        "endTimeMillis": int(now.timestamp() * 1000)
    }
    hourly_resp = service.users().dataset().aggregate(userId="me", body=hourly_payload).execute()

    # 2. Запит сну
    daily_payload = {
        "aggregateBy": [{"dataTypeName": "com.google.sleep.segment"}],
        "bucketByTime": {"durationMillis": 86400000},
        "startTimeMillis": int(start_time_daily.timestamp() * 1000),
        "endTimeMillis": int(now.timestamp() * 1000)
    }
    daily_resp = service.users().dataset().aggregate(userId="me", body=daily_payload).execute()

    # Зберігаємо у Bronze
    supabase_client.table("bronze_health").insert([
        {"source": "google_fit_hourly", "raw_payload": {"import_time": now.isoformat(), "data": hourly_resp}},
        {"source": "google_fit_daily", "raw_payload": {"import_time": now.isoformat(), "data": daily_resp}}
    ]).execute()
    print("Сирі дані здоров'я успішно записані в bronze_health!")