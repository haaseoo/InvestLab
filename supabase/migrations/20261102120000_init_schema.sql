-- InvestLab Phase 3 초기 스키마
--
-- 원칙
-- - DROP, TRUNCATE, DELETE 문을 쓰지 않는다. 이미 있는 객체가 있으면 실패하고 전체가 롤백된다.
-- - Supabase 기본 권한(anon·authenticated에 모든 권한)을 회수하고 필요한 권한만 다시 준다.
-- - 모든 사용자 데이터 테이블에 RLS를 켜고, 본인 행만 다루는 정책을 작업별로 따로 둔다.
-- - 실제 투자 실적(포트폴리오 스냅샷)은 source = 'live'만 저장할 수 있다. Mock은 DB 제약으로 막는다.

-- ------------------------------------------------------------------ 공통 함수

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ------------------------------------------------------------------ profiles

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text check (display_name is null or char_length(display_name) between 1 and 50),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- ------------------------------------------------------------------ user_settings

create table public.user_settings (
  user_id uuid primary key references auth.users (id) on delete cascade,
  theme text not null default 'light' check (theme in ('light', 'dark', 'system')),
  preferred_currency text not null default 'KRW' check (preferred_currency ~ '^[A-Z]{3}$'),
  preferred_source text not null default 'mock' check (preferred_source in ('mock', 'live')),
  mask_account_numbers boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger user_settings_set_updated_at
  before update on public.user_settings
  for each row execute function public.set_updated_at();

-- ------------------------------------------------------------------ portfolio_snapshots

create table public.portfolio_snapshots (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  -- 실제 계좌 데이터만 저장한다. Mock(가상 데이터)은 투자 실적이 아니므로 저장할 수 없다.
  source text not null check (source in ('live')),
  valuation_currency text not null check (valuation_currency ~ '^[A-Z]{3}$'),
  total_market_value numeric(24, 4) not null check (total_market_value >= 0),
  total_cost_basis numeric(24, 4) not null check (total_cost_basis >= 0),
  holding_count integer not null check (holding_count >= 0),
  valued_holding_count integer not null check (valued_holding_count >= 0),
  is_complete boolean not null,
  -- [{base_currency, quote_currency, rate, as_of, source}]
  fx_rates jsonb not null default '[]'::jsonb check (jsonb_typeof(fx_rates) = 'array'),
  -- 데이터 기준 시각(시세 시각). captured_at은 저장 시각이다.
  as_of timestamptz not null,
  captured_at timestamptz not null default now(),
  -- 저장 내용의 SHA-256. 같은 내용이 다시 들어오는지 확인할 때 쓴다.
  content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  constraint portfolio_snapshots_valued_le_total check (valued_holding_count <= holding_count),
  constraint portfolio_snapshots_complete_flag check (is_complete = (valued_holding_count = holding_count)),
  constraint portfolio_snapshots_as_of_not_future check (as_of <= captured_at + interval '5 minutes'),
  -- 같은 기준 시각의 스냅샷은 한 번만 저장한다.
  constraint portfolio_snapshots_unique_as_of unique (user_id, source, as_of),
  -- holding_snapshots의 복합 외래키 대상
  constraint portfolio_snapshots_id_user_unique unique (id, user_id)
);

create index portfolio_snapshots_user_as_of_idx
  on public.portfolio_snapshots (user_id, as_of desc);

-- ------------------------------------------------------------------ holding_snapshots

create table public.holding_snapshots (
  id uuid primary key default gen_random_uuid(),
  portfolio_snapshot_id uuid not null,
  user_id uuid not null default auth.uid(),
  symbol text not null check (char_length(symbol) between 1 and 32),
  market text not null check (char_length(market) between 1 and 16),
  name text not null check (char_length(name) between 1 and 200),
  asset_type text not null check (asset_type in ('stock', 'etf', 'other')),
  quantity numeric(28, 8) not null check (quantity >= 0),
  average_cost numeric(28, 8) not null check (average_cost >= 0),
  current_price numeric(28, 8) check (current_price >= 0),
  currency text not null check (currency ~ '^[A-Z]{3}$'),
  cost_basis numeric(24, 4) not null check (cost_basis >= 0),
  market_value numeric(24, 4) check (market_value >= 0),
  fx_rate numeric(20, 8) check (fx_rate > 0),
  cost_basis_valuation numeric(24, 4) check (cost_basis_valuation >= 0),
  market_value_valuation numeric(24, 4) check (market_value_valuation >= 0),
  valuation_status text not null check (valuation_status in ('reported', 'calculated', 'unavailable')),
  created_at timestamptz not null default now(),
  -- 종목 스냅샷의 사용자와 상위 스냅샷의 사용자가 반드시 같도록 복합 외래키로 묶는다.
  constraint holding_snapshots_parent_fk foreign key (portfolio_snapshot_id, user_id)
    references public.portfolio_snapshots (id, user_id) on delete cascade,
  constraint holding_snapshots_unique_symbol unique (portfolio_snapshot_id, market, symbol),
  -- 평가금액이 없으면 반드시 unavailable 상태여야 하고, 그 반대도 같다.
  constraint holding_snapshots_status_matches_value
    check ((valuation_status = 'unavailable') = (market_value is null))
);

create index holding_snapshots_user_idx on public.holding_snapshots (user_id);

-- ------------------------------------------------------------------ ai_reports

create table public.ai_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  portfolio_snapshot_id uuid,
  report_json jsonb not null check (jsonb_typeof(report_json) = 'object'),
  model text check (model is null or char_length(model) <= 100),
  created_at timestamptz not null default now(),
  constraint ai_reports_snapshot_fk foreign key (portfolio_snapshot_id, user_id)
    references public.portfolio_snapshots (id, user_id) on delete set null (portfolio_snapshot_id)
);

create index ai_reports_user_created_idx on public.ai_reports (user_id, created_at desc);

-- ------------------------------------------------------------------ simulation_history

create table public.simulation_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  simulation_type text not null check (simulation_type in ('buy', 'rebalance', 'scenario')),
  -- 시뮬레이션은 투자 실적이 아니므로 Mock도 저장할 수 있다. 대신 출처를 반드시 남긴다.
  source text not null check (source in ('mock', 'live')),
  is_demo boolean not null,
  input_json jsonb not null check (jsonb_typeof(input_json) = 'object'),
  result_json jsonb not null check (jsonb_typeof(result_json) = 'object'),
  as_of timestamptz,
  created_at timestamptz not null default now(),
  constraint simulation_history_demo_matches_source check (is_demo = (source = 'mock')),
  constraint simulation_history_size_limit
    check (pg_column_size(input_json) + pg_column_size(result_json) <= 524288)
);

create index simulation_history_user_created_idx
  on public.simulation_history (user_id, created_at desc);

-- ------------------------------------------------------------------ 새 사용자 기본 행

create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id) values (new.id) on conflict (id) do nothing;
  insert into public.user_settings (user_id) values (new.id) on conflict (user_id) do nothing;
  return new;
end;
$$;

revoke execute on function public.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- 이미 있는 사용자(소유자 계정)의 기본 행. 삭제 없이 없을 때만 추가한다.
insert into public.profiles (id) select id from auth.users on conflict (id) do nothing;
insert into public.user_settings (user_id) select id from auth.users on conflict (user_id) do nothing;

-- ------------------------------------------------------------------ 권한

revoke all on table
  public.profiles,
  public.user_settings,
  public.portfolio_snapshots,
  public.holding_snapshots,
  public.ai_reports,
  public.simulation_history
from anon, authenticated;

-- 수정 가능한 열을 명시해 user_id·id·생성 시각은 바꿀 수 없게 한다.
grant select, insert on public.profiles to authenticated;
grant update (display_name) on public.profiles to authenticated;

grant select, insert on public.user_settings to authenticated;
grant update (theme, preferred_currency, preferred_source, mask_account_numbers)
  on public.user_settings to authenticated;

-- 스냅샷과 기록은 수정하지 않는다(불변). 조회·추가·삭제만 허용한다.
grant select, insert, delete on public.portfolio_snapshots to authenticated;
grant select, insert, delete on public.holding_snapshots to authenticated;
grant select, insert, delete on public.ai_reports to authenticated;
grant select, insert, delete on public.simulation_history to authenticated;

revoke execute on function public.set_updated_at() from public, anon, authenticated;

-- ------------------------------------------------------------------ RLS

alter table public.profiles enable row level security;
alter table public.user_settings enable row level security;
alter table public.portfolio_snapshots enable row level security;
alter table public.holding_snapshots enable row level security;
alter table public.ai_reports enable row level security;
alter table public.simulation_history enable row level security;

-- profiles: 본인 행 조회·추가·수정. 삭제는 계정 삭제(cascade)로만.
create policy profiles_select_own on public.profiles
  for select to authenticated using ((select auth.uid()) = id);
create policy profiles_insert_own on public.profiles
  for insert to authenticated with check ((select auth.uid()) = id);
create policy profiles_update_own on public.profiles
  for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

-- user_settings: 본인 행 조회·추가·수정.
create policy user_settings_select_own on public.user_settings
  for select to authenticated using ((select auth.uid()) = user_id);
create policy user_settings_insert_own on public.user_settings
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy user_settings_update_own on public.user_settings
  for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

-- portfolio_snapshots: 본인 행 조회·추가·삭제. 추가는 live만.
create policy portfolio_snapshots_select_own on public.portfolio_snapshots
  for select to authenticated using ((select auth.uid()) = user_id);
create policy portfolio_snapshots_insert_own on public.portfolio_snapshots
  for insert to authenticated with check ((select auth.uid()) = user_id and source = 'live');
create policy portfolio_snapshots_delete_own on public.portfolio_snapshots
  for delete to authenticated using ((select auth.uid()) = user_id);

-- holding_snapshots: 본인 행 조회·추가·삭제. 상위 스냅샷 소유는 복합 외래키가 보장한다.
create policy holding_snapshots_select_own on public.holding_snapshots
  for select to authenticated using ((select auth.uid()) = user_id);
create policy holding_snapshots_insert_own on public.holding_snapshots
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy holding_snapshots_delete_own on public.holding_snapshots
  for delete to authenticated using ((select auth.uid()) = user_id);

-- ai_reports: 본인 행 조회·추가·삭제.
create policy ai_reports_select_own on public.ai_reports
  for select to authenticated using ((select auth.uid()) = user_id);
create policy ai_reports_insert_own on public.ai_reports
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy ai_reports_delete_own on public.ai_reports
  for delete to authenticated using ((select auth.uid()) = user_id);

-- simulation_history: 본인 행 조회·추가·삭제.
create policy simulation_history_select_own on public.simulation_history
  for select to authenticated using ((select auth.uid()) = user_id);
create policy simulation_history_insert_own on public.simulation_history
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy simulation_history_delete_own on public.simulation_history
  for delete to authenticated using ((select auth.uid()) = user_id);
