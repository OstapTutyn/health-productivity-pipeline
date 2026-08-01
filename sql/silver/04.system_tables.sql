-- Системна таблиця для вотермарків та статусів інкрементальних завантажень
create table public.etl_watermarks (
    id uuid default gen_random_uuid() primary key,
    pipeline_name text not null,
    last_success_at timestamptz,
    updated_at timestamptz default now(),
    constraint unique_pipeline_name unique (pipeline_name)
);