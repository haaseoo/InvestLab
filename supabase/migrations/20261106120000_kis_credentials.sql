-- 사용자별 한국투자증권 인증정보
--
-- - App Key·Secret·계좌번호는 API 서버가 AES-256-GCM으로 암호화한 뒤 저장한다. 평문은 DB에 없다.
--   마스터 키는 API 서버 환경변수(KIS_CREDENTIAL_KEY)에만 있다.
-- - 접근 토큰도 같은 방식으로 암호화해 둔다. 재시작 때 재발급(알림톡, 1분 1회 제한)을 피하려는 것이다.
-- - 사용자 한 명당 한 행. 본인 행만 다룰 수 있다(RLS).
-- - DROP, TRUNCATE, DELETE 문을 쓰지 않는다.

create table public.kis_credentials (
  user_id uuid primary key default auth.uid() references auth.users (id) on delete cascade,
  -- 형식: 버전(1) + nonce(12) + 암호문 + 태그(16)
  credentials_enc bytea not null check (octet_length(credentials_enc) between 29 and 4096),
  -- 화면 표시용. 마지막 2자리만 남긴 값이다.
  account_masked text not null check (account_masked ~ '^\*{8}[0-9]{2}$'),
  token_enc bytea check (token_enc is null or octet_length(token_enc) between 29 and 8192),
  token_expires_at timestamptz,
  created_at timestamptz not null default now(),
  -- 인증정보를 바꾼 시각. 토큰 갱신으로는 바뀌지 않는다(API가 직접 넣는다).
  updated_at timestamptz not null default now(),
  constraint kis_credentials_token_pair check ((token_enc is null) = (token_expires_at is null))
);

revoke all on table public.kis_credentials from anon, authenticated;

grant select, insert, delete on public.kis_credentials to authenticated;
grant update (credentials_enc, account_masked, token_enc, token_expires_at, updated_at)
  on public.kis_credentials to authenticated;

alter table public.kis_credentials enable row level security;

create policy kis_credentials_select_own on public.kis_credentials
  for select to authenticated using ((select auth.uid()) = user_id);
create policy kis_credentials_insert_own on public.kis_credentials
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy kis_credentials_update_own on public.kis_credentials
  for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy kis_credentials_delete_own on public.kis_credentials
  for delete to authenticated using ((select auth.uid()) = user_id);
