-- Оброблений шар щоденника
create table public.silver_journal (
    id uuid default gen_random_uuid() primary key,
    entry_date date not null,
    content text,
    created_at timestamptz default now(),
    constraint unique_journal_date unique (entry_date)
);

-- Staging-шар для музичних треків
create table public.stg_music_tracks (
    id uuid default gen_random_uuid() primary key,
    track_name text not null,
    artist_name text not null,
    played_at timestamptz not null,
    created_at timestamptz default now(),
    constraint unique_track_play unique (track_name, artist_name, played_at)
);

-- Staging-шар для подій екранного часу
create table public.stg_screentime_events (
    id uuid default gen_random_uuid() primary key,
    app_name text not null,
    duration_min numeric not null,
    event_date date not null,
    created_at timestamptz default now()
);