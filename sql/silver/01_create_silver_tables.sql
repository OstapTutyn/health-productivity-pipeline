create table if not exists silver_journal (
  notion_page_id uuid primary key,
  entry_date date not null,
  overall_score numeric(2, 1),
  energy smallint,
  mood smallint,
  stress smallint,
  productivity smallint,
  tags text[],
  log_text text,
  updated_at timestamptz default now()
);