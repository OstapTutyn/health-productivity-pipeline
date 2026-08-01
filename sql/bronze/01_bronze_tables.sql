-- Сирий шар для Apple Health
create table public.bronze_health (
    id uuid default gen_random_uuid() primary key,
    raw_payload jsonb not null,
    is_processed boolean default false,
    created_at timestamptz default now()
);

-- Сирий шар для щоденника
create table public.bronze_journal (
    id uuid default gen_random_uuid() primary key,
    raw_payload jsonb not null,
    is_processed boolean default false,
    created_at timestamptz default now()
);

-- Сирий шар для музики
create table public.bronze_music (
    id uuid default gen_random_uuid() primary key,
    raw_payload jsonb not null,
    is_processed boolean default false,
    created_at timestamptz default now()
);

-- Сирий шар для екранного часу
create table public.bronze_screentime (
    id uuid default gen_random_uuid() primary key,
    raw_payload jsonb not null,
    is_processed boolean default false,
    created_at timestamptz default now()
);