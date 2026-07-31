import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def fetch_unprocessed_records(supabase: Client) -> list[dict]:
    res = supabase.table("bronze_health").select("id, raw_payload, source").eq("is_processed", False).execute()
    return res.data or []

def process_health_data(supabase: Client):
    records = fetch_unprocessed_records(supabase)
    if not records:
        print("Необроблених даних у bronze_health немає.")
        return

    processed_ids = [r["id"] for r in records]
    hourly_records = []
    extracted_sleep = {}
    extracted_rhr = {}

    for record in records:
        source = record.get("source")
        payload = record.get("raw_payload", {}).get("data", {})
        buckets = payload.get("bucket", [])

        if source == "google_fit_hourly":
            for bucket in buckets:
                start_ms = int(bucket.get('startTimeMillis', 0))
                end_ms = int(bucket.get('endTimeMillis', 0))
                start_dt = datetime.fromtimestamp(start_ms / 1000.0, tz=timezone.utc).isoformat()
                end_dt = datetime.fromtimestamp(end_ms / 1000.0, tz=timezone.utc).isoformat()
                entry_date = datetime.fromtimestamp(end_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")

                steps, hr_sum, hr_count, calories = 0, 0, 0, 0.0
                for dataset in bucket.get('dataset', []):
                    data_source = dataset.get('dataSourceId', '')
                    for point in dataset.get('point', []):
                        values = point.get('value', [])
                        if not values: continue
                        if "step_count" in data_source:
                            steps += values[0].get('intVal', 0)
                        elif "heart_rate" in data_source:
                            avg_hr = values[0].get('fpVal', 0)
                            if avg_hr > 0:
                                hr_sum += avg_hr
                                hr_count += 1
                                if entry_date not in extracted_rhr:
                                    extracted_rhr[entry_date] = []
                                extracted_rhr[entry_date].append(avg_hr)
                        elif "calories" in data_source:
                            calories += values[0].get('fpVal', 0.0)

                hr_avg = (hr_sum / hr_count) if hr_count > 0 else None
                if steps > 0 or hr_avg or calories > 0:
                    hourly_records.append({
                        "start_time": start_dt,
                        "end_time": end_dt,
                        "step_count": steps,
                        "heart_rate_avg": round(hr_avg, 2) if hr_avg else None,
                        "active_energy_kcal": round(calories, 2)
                    })

        elif source == "google_fit_daily":
            for bucket in buckets:
                start_ms = bucket.get("startTimeMillis")
                end_ms = bucket.get("endTimeMillis")
                if not start_ms or not end_ms: continue

                start_dt = datetime.fromtimestamp(int(start_ms) / 1000, tz=timezone.utc)
                end_dt = datetime.fromtimestamp(int(end_ms) / 1000, tz=timezone.utc)
                record_date = end_dt.strftime("%Y-%m-%d")
                duration_min = round((end_dt - start_dt).total_seconds() / 60)

                extracted_sleep[record_date] = {
                    "sleep_onset_time": start_dt.isoformat(),
                    "sleep_wake_time": end_dt.isoformat(),
                    "sleep_duration_min": duration_min
                }

    # Зберігаємо погодинні метрики у Silver
    if hourly_records:
        supabase.table("health_hourly_metrics").upsert(hourly_records, on_conflict="start_time,end_time").execute()
        print(f"Збережено {len(hourly_records)} записів у health_hourly_metrics.")

    # Формуємо добові знімки (health_daily_snapshot) з урахуванням NULL для розрядженого годинника
    all_dates = set(list(extracted_sleep.keys()) + list(extracted_rhr.keys()))
    if all_dates:
        snapshot_records = []
        for d in all_dates:
            sleep_info = extracted_sleep.get(d, {})
            hrs = extracted_rhr.get(d, [])
            min_rhr = round(min(hrs), 2) if hrs else None

            snapshot_records.append({
                "record_date": d,
                "sleep_onset_time": sleep_info.get("sleep_onset_time"),
                "sleep_wake_time": sleep_info.get("sleep_wake_time"),
                "sleep_duration_min": sleep_info.get("sleep_duration_min"),
                "resting_heart_rate": min_rhr
            })

        supabase.table("health_daily_snapshot").upsert(snapshot_records, on_conflict="record_date").execute()
        print(f"Збережено {len(snapshot_records)} записів у health_daily_snapshot (включно з NULL).")

    # Позначаємо батчі як оброблені в Bronze
    supabase.table("bronze_health").update({"is_processed": True}).in_("id", processed_ids).execute()
    print("Батчі в bronze_health успішно позначено як оброблені!")

if __name__ == "__main__":
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    process_health_data(supabase_client)