-- Вмикаємо розширення для роботи з UUID (якщо потрібно)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Music (Last.fm)
CREATE TABLE IF NOT EXISTS bronze_music (
    id SERIAL PRIMARY KEY,
    payload JSONB NOT NULL,
    is_processed BOOLEAN DEFAULT FALSE,
    inserted_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Screen Time (Active Watch / iPhone)
CREATE TABLE IF NOT EXISTS bronze_screentime (
    id SERIAL PRIMARY KEY,
    payload JSONB NOT NULL,
    is_processed BOOLEAN DEFAULT FALSE,
    inserted_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Health (Google Fit)
CREATE TABLE IF NOT EXISTS bronze_health (
    id SERIAL PRIMARY KEY,
    payload JSONB NOT NULL,
    is_processed BOOLEAN DEFAULT FALSE,
    inserted_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. iPhone System Data
CREATE TABLE IF NOT EXISTS bronze_iphone (
    id SERIAL PRIMARY KEY,
    payload JSONB NOT NULL,
    is_processed BOOLEAN DEFAULT FALSE,
    inserted_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Notion Journal / Productivity Logs
CREATE TABLE IF NOT EXISTS bronze_notion (
    id SERIAL PRIMARY KEY,
    payload JSONB NOT NULL,
    is_processed BOOLEAN DEFAULT FALSE,
    inserted_at TIMESTAMPTZ DEFAULT NOW()
);