create extension if not exists pgcrypto;

create table if not exists public.matches (
  id uuid primary key default gen_random_uuid(),
  room_id text not null unique,
  mode text not null check (mode in ('1000cc', '2000cc', 'turbo')),
  target_text text not null,
  state text not null default 'COUNTDOWN' check (state in ('COUNTDOWN', 'RUNNING', 'FINISHED')),
  winner text,
  reason text,
  rematch_requests text[] not null default '{}',
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists public.match_players (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null references public.matches(id) on delete cascade,
  username text not null,
  typed_text text not null default '',
  typed_chars integer not null default 0,
  correct_chars integer not null default 0,
  progress numeric not null default 0,
  accuracy numeric not null default 0,
  wpm numeric not null default 0,
  score integer not null default 0,
  finished boolean not null default false,
  finish_time numeric,
  rank integer,
  connected boolean not null default true,
  latency_ms numeric,
  joined_at timestamptz not null default now(),
  last_update_at timestamptz not null default now(),
  unique (match_id, username)
);

create table if not exists public.matchmaking_queue (
  id uuid primary key default gen_random_uuid(),
  username text not null unique,
  mode text not null check (mode in ('1000cc', '2000cc', 'turbo')),
  joined_at timestamptz not null default now()
);

create index if not exists idx_matchmaking_queue_mode_joined
  on public.matchmaking_queue (mode, joined_at);

create index if not exists idx_matches_room_id
  on public.matches (room_id);

create index if not exists idx_match_players_match_id
  on public.match_players (match_id);

alter table public.matches enable row level security;
alter table public.match_players enable row level security;
alter table public.matchmaking_queue enable row level security;

drop policy if exists "public matches demo access" on public.matches;
drop policy if exists "public match players demo access" on public.match_players;
drop policy if exists "public queue demo access" on public.matchmaking_queue;

create policy "public matches demo access"
  on public.matches
  for all
  to anon, authenticated
  using (true)
  with check (true);

create policy "public match players demo access"
  on public.match_players
  for all
  to anon, authenticated
  using (true)
  with check (true);

create policy "public queue demo access"
  on public.matchmaking_queue
  for all
  to anon, authenticated
  using (true)
  with check (true);

grant usage on schema public to anon, authenticated;
grant all on public.matches to anon, authenticated;
grant all on public.match_players to anon, authenticated;
grant all on public.matchmaking_queue to anon, authenticated;
