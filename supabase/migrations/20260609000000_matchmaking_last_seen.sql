alter table public.matchmaking_queue
  add column if not exists last_seen_at timestamptz not null default now();

update public.matchmaking_queue
  set last_seen_at = joined_at
  where last_seen_at is null;

create index if not exists idx_matchmaking_queue_mode_last_seen
  on public.matchmaking_queue (mode, last_seen_at);
