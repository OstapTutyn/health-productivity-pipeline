-- Погодинні метрики здоров'я
create table public.health_hourly_metrics (
    id uuid default gen_random_uuid() primary key,
    start_time timestamptz not null,
    end_time timestamptz not null,
    step_count int,
    active_energy_kcal numeric,
    heart_rate_avg numeric,
    exercise_min int,
    created_at timestamptz default now(),
    constraint unique_hourly_interval unique (start_time, end_time)
);

-- Добові знімки (сон та відновлення)
create table public.health_daily_snapshot (
    id uuid default gen_random_uuid() primary key,
    record_date date not null,
    sleep_duration_min int,
    sleep_onset_time timestamptz,
    sleep_wake_time timestamptz,
    deep_sleep_min int,
    rem_sleep_min int,
    resting_heart_rate numeric,
    hrv_rmssd numeric,
    created_at timestamptz default now(),
    constraint unique_record_date unique (record_date)
);

-- Розширені біомеханічні та середовищні метрики (блоки по 3 години)
create table public.health_advanced_metrics (
    id uuid default gen_random_uuid() primary key,
    metric_time timestamptz not null,
    walking_speed numeric,
    walking_step_length numeric,
    walking_asymmetry_percentage numeric,
    walking_double_support_percentage numeric,
    stair_speed_up numeric,
    stair_speed_down numeric,
    flights_climbed int,
    heart_rate_variability numeric,
    respiratory_rate numeric,
    resting_heart_rate numeric,
    walking_heart_rate_average numeric,
    headphone_audio_exposure numeric,
    environmental_audio_exposure numeric,
    time_in_daylight numeric,
    apple_stand_hour int,
    apple_stand_time numeric,
    created_at timestamptz default now(),
    constraint unique_advanced_metric_time unique (metric_time)
);