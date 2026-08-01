create table public.gold_daily_summary (
    id uuid default gen_random_uuid() primary key,
    summary_date date not null,

    -- Здоров'я та активність
    total_steps int default 0,
    total_active_energy_kcal numeric default 0,
    avg_heart_rate numeric,
    time_in_daylight numeric default 0,

    -- Сон та відновлення
    sleep_duration_min int,
    deep_sleep_min int,
    rem_sleep_min int,
    sleep_onset_time timestamptz,
    sleep_wake_time timestamptz,
    hrv_rmssd numeric,

    -- Екранний час і продуктивність
    total_screentime_min numeric default 0,
    productive_screentime_min numeric default 0,

    -- Розваги
    total_tracks_played int default 0,

    -- Щоденник
    journal_rating numeric,
    journal_tags text,
    journal_content text,

    created_at timestamptz default now(),
    updated_at timestamptz default now(),

    constraint unique_summary_date unique (summary_date)
);