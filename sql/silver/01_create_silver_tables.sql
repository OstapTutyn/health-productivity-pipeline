-- ==========================================
-- SILVER: MUSIC LAYER
-- ==========================================

-- Деталізовані треки
CREATE TABLE IF NOT EXISTS stg_music_tracks (
    id SERIAL PRIMARY KEY,
    played_at TIMESTAMPTZ NOT NULL,
    entry_date DATE NOT NULL,
    track_name TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    album_name TEXT,
    genre TEXT,
    CONSTRAINT unique_track_play UNIQUE (artist_name, track_name, played_at)
);

-- Погодинна агрегація музики
CREATE TABLE IF NOT EXISTS stg_music_hourly (
    id SERIAL PRIMARY KEY,
    hourly_timestamp TIMESTAMPTZ NOT NULL,
    entry_date DATE NOT NULL,
    tracks_count INT NOT NULL,
    dominant_genre TEXT,
    dominant_artist TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_hourly_music UNIQUE (hourly_timestamp)
);


-- ==========================================
-- SILVER: SCREEN TIME LAYER
-- ==========================================

-- Події екранного часу
CREATE TABLE IF NOT EXISTS stg_screentime_events (
    id SERIAL PRIMARY KEY,
    event_timestamp TIMESTAMPTZ NOT NULL,
    entry_date DATE NOT NULL,
    app_name TEXT NOT NULL,
    duration_minutes INT NOT NULL,
    category TEXT
);

-- Погодинна агрегація екранного часу
CREATE TABLE IF NOT EXISTS stg_screentime_hourly (
    id SERIAL PRIMARY KEY,
    hourly_timestamp TIMESTAMPTZ NOT NULL,
    entry_date DATE NOT NULL,
    total_screen_time_minutes INT NOT NULL,
    primary_app TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_hourly_screentime UNIQUE (hourly_timestamp)
);


-- ==========================================
-- SILVER: HEALTH & FITNESS LAYER (Google Fit)
-- ==========================================

CREATE TABLE IF NOT EXISTS stg_health_daily (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL UNIQUE,
    steps INT,
    calories_burned FLOAT,
    active_minutes INT,
    sleep_hours FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


-- ==========================================
-- SILVER: NOTION PRODUCTIVITY LAYER
-- ==========================================

CREATE TABLE IF NOT EXISTS stg_notion_journal (
    id SERIAL PRIMARY KEY,
    entry_date DATE NOT NULL UNIQUE,
    productivity_score INT,
    mood TEXT,
    key_highlights TEXT,
    tasks_completed INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);