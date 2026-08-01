from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def fetch_unprocessed_records(supabase: Client) -> list[dict]:
  res = (
      supabase.table("bronze_health")
      .select("id, raw_payload")  # <-- прибрали 'source'
      .eq("is_processed", False)
      .execute()
  )
  return res.data or []


def process_health_data(supabase: Client):
  records = fetch_unprocessed_records(supabase)
  if not records:
    print("Необроблених даних у bronze_health немає.")
    return

  processed_ids = [r["id"] for r in records]
  hourly_data_map = {}
  daily_sleep = {}
  advanced_raw_map = {}

  for record in records:
    payload = record.get("raw_payload", {}).get("data", {})
    metrics = payload.get("metrics", [])

    for metric in metrics:
      name = metric.get("name")
      metric_data = metric.get("data", [])

      # --- БАЗОВІ ПОГОДИННІ МЕТРИКИ ---
      if name == "step_count":
        for item in metric_data:
          date_str = item.get("date")
          qty = item.get("qty", 0)
          if not date_str:
            continue
          dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
          start_time = dt.isoformat()
          end_time = (dt + timedelta(hours=1)).isoformat()
          key = (start_time, end_time)

          if key not in hourly_data_map:
            hourly_data_map[key] = {
                "start_time": start_time,
                "end_time": end_time,
                "step_count": 0,
                "active_energy_kcal": 0.0,
                "heart_rate_avg": None,
                "exercise_min": None,
            }
          hourly_data_map[key]["step_count"] += int(
              round(qty)
          )

      elif name == "active_energy":
        for item in metric_data:
          date_str = item.get("date")
          qty_kj = item.get("qty", 0)
          qty_kcal = qty_kj / 4.184
          if not date_str:
            continue
          dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
          start_time = dt.isoformat()
          end_time = (dt + timedelta(hours=1)).isoformat()
          key = (start_time, end_time)

          if key not in hourly_data_map:
            hourly_data_map[key] = {
                "start_time": start_time,
                "end_time": end_time,
                "step_count": 0,
                "active_energy_kcal": 0.0,
                "heart_rate_avg": None,
                "exercise_min": None,
            }
          hourly_data_map[key]["active_energy_kcal"] += round(qty_kcal, 2)

      elif name == "heart_rate":
        for item in metric_data:
          date_str = item.get("date")
          avg_val = item.get("Avg")
          if not date_str or avg_val is None:
            continue
          dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
          start_time = dt.isoformat()
          end_time = (dt + timedelta(hours=1)).isoformat()
          key = (start_time, end_time)

          if key not in hourly_data_map:
            hourly_data_map[key] = {
                "start_time": start_time,
                "end_time": end_time,
                "step_count": 0,
                "active_energy_kcal": 0.0,
                "heart_rate_avg": avg_val,
                "exercise_min": None,
            }
          else:
            hourly_data_map[key]["heart_rate_avg"] = avg_val

      elif name == "apple_exercise_time":
        for item in metric_data:
          date_str = item.get("date")
          qty = item.get("qty", 0)
          if not date_str:
            continue
          dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
          start_time = dt.isoformat()
          end_time = (dt + timedelta(hours=1)).isoformat()
          key = (start_time, end_time)

          if key not in hourly_data_map:
            hourly_data_map[key] = {
                "start_time": start_time,
                "end_time": end_time,
                "step_count": 0,
                "active_energy_kcal": 0.0,
                "heart_rate_avg": None,
                "exercise_min": int(qty),
            }
          else:
            hourly_data_map[key]["exercise_min"] = int(qty)

      # --- ДОБОВИЙ СОН ---
      elif name == "sleep_analysis":
        for item in metric_data:
          sleep_start = item.get("sleepStart")
          sleep_end = item.get("sleepEnd")
          total_sleep_hr = item.get("totalSleep", 0)
          deep_hr = item.get("deep", 0)
          rem_hr = item.get("rem", 0)
          date_str = item.get("date")

          if date_str:
            day_key = date_str.split()[0]
            total_min = int(total_sleep_hr * 60)
            deep_min = int(deep_hr * 60)
            rem_min = int(rem_hr * 60)

            if day_key not in daily_sleep:
              daily_sleep[day_key] = {
                  "sleep_onset_time": sleep_start,
                  "sleep_wake_time": sleep_end,
                  "sleep_duration_min": total_min,
                  "deep_sleep_min": deep_min,
                  "rem_sleep_min": rem_min,
              }
            else:
              daily_sleep[day_key]["sleep_duration_min"] += total_min
              daily_sleep[day_key]["deep_sleep_min"] += deep_min
              daily_sleep[day_key]["rem_sleep_min"] += rem_min

      # --- РОЗШИРЕНІ МЕТРИКИ (З 07:00 ДО 01:00, БЛОКИ ПО 3 ГОДИНИ) ---
      else:
        advanced_metric_names = {
            "walking_speed",
            "walking_step_length",
            "walking_asymmetry_percentage",
            "walking_double_support_percentage",
            "stair_speed_up",
            "stair_speed_down",
            "flights_climbed",
            "heart_rate_variability",
            "respiratory_rate",
            "resting_heart_rate",
            "walking_heart_rate_average",
            "headphone_audio_exposure",
            "environmental_audio_exposure",
            "time_in_daylight",
            "apple_stand_hour",
            "apple_stand_time",
        }

        if name in advanced_metric_names:
          for item in metric_data:
            date_str = item.get("date")
            qty = item.get("qty")
            if not date_str or qty is None:
              continue

            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")

            # Фільтруємо ніч (з 02:00 до 08:00 не записуємо)
            if 2 <= dt.hour < 8:
              continue

            # Зсуваємо час на 7 годин назад для правильного розбиття на 6 блоків доби
            dt_shifted = dt - timedelta(hours=7)
            total_seconds_shifted = (
                dt_shifted
                - dt_shifted.replace(hour=0, minute=0, second=0, microsecond=0)
            ).total_seconds()
            block_index = int(total_seconds_shifted // (3 * 3600))

            if block_index >= 6:
              continue

            block_start_shifted = dt_shifted.replace(
                hour=block_index * 3, minute=0, second=0, microsecond=0
            )
            block_start = block_start_shifted + timedelta(hours=7)
            time_key = block_start.isoformat()

            if time_key not in advanced_raw_map:
              advanced_raw_map[time_key] = {}
            if name not in advanced_raw_map[time_key]:
              advanced_raw_map[time_key][name] = []

            advanced_raw_map[time_key][name].append(qty)

  # --- ЗБЕРЕЖЕННЯ В БАЗУ ---

  # 1. Погодинні метрики
  hourly_records = list(hourly_data_map.values())
  if hourly_records:
    supabase.table("health_hourly_metrics").upsert(
        hourly_records, on_conflict="start_time,end_time"
    ).execute()
    print(f"Збережено {len(hourly_records)} записів у health_hourly_metrics.")

  # 2. Добові знімки сну
  snapshot_records = []
  for d, sleep_info in daily_sleep.items():
    snapshot_records.append({
        "record_date": d,
        "sleep_onset_time": sleep_info.get("sleep_onset_time"),
        "sleep_wake_time": sleep_info.get("sleep_wake_time"),
        "sleep_duration_min": sleep_info.get("sleep_duration_min"),
        "deep_sleep_min": sleep_info.get("deep_sleep_min"),
        "rem_sleep_min": sleep_info.get("rem_sleep_min"),
    })

  if snapshot_records:
    supabase.table("health_daily_snapshot").upsert(
        snapshot_records, on_conflict="record_date"
    ).execute()
    print(f"Збережено {len(snapshot_records)} записів у health_daily_snapshot.")

  # 3. Розширені метрики (6 записів на добу)
  advanced_records = []
  for time_key, metrics_dict in advanced_raw_map.items():
    record = {"metric_time": time_key}
    for name, values in metrics_dict.items():
      if not values:
        continue
      if name in ["flights_climbed", "apple_stand_hour"]:
        record[name] = sum(int(v) for v in values)
      elif name in ["apple_stand_time", "time_in_daylight"]:
        record[name] = round(sum(float(v) for v in values), 2)
      else:
        record[name] = round(sum(float(v) for v in values) / len(values), 2)

    advanced_records.append(record)

  if advanced_records:
    supabase.table("health_advanced_metrics").upsert(
        advanced_records, on_conflict="metric_time"
    ).execute()
    print(
        f"Збережено {len(advanced_records)} записів у health_advanced_metrics (6"
        " на добу)."
    )

  # Позначення батчів як оброблених
  supabase.table("bronze_health").update({"is_processed": True}).in_(
      "id", processed_ids
  ).execute()
  print("Батчі в bronze_health успішно позначено як оброблені!")


if __name__ == "__main__":
  supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
  process_health_data(supabase_client)