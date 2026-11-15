-- AI 글라스 구매 의향 설문 v5 스키마 (Supabase / Postgres)  — 처음부터 만들 때 사용
-- 설계 원칙: 익명 사용자는 INSERT만 가능, SELECT/UPDATE/DELETE 불가. 값 검증은 CHECK 제약으로 DB가 직접 수행.
-- 이미 v4 테이블이 있는 DB는 이 파일 대신 migration_v5.sql 을 실행하십시오(v3이면 migration_v4.sql → migration_v5.sql 순서).

-- Q4(최대 2개 선택) 검증: 허용값만, 1~2개, 중복 불가, 'none'은 단독. (CHECK에는 서브쿼리를 못 쓰므로 함수로 분리)
create or replace function public.q4_valid(a text[]) returns boolean
language sql immutable set search_path = ''
as $$
  select a is not null
     and cardinality(a) between 1 and 2
     and a <@ array['apps_lack','substitute','complex','peers_lack','supply_uncertain','none']::text[]
     and cardinality(a) = (select count(distinct x) from unnest(a) as x)
     and (not ('none' = any(a)) or cardinality(a) = 1)
$$;
grant execute on function public.q4_valid(text[]) to anon;

-- v5: interests(최대 2개, 'other' 단독) / use_values(최대 2개, 'none' 단독) 검증
create or replace function public.interests_valid(a text[]) returns boolean
language sql immutable set search_path = ''
as $$
  select a is not null
     and cardinality(a) between 1 and 2
     and a <@ array['gaming','tech_gadget','video','study','creative','sports','travel','social','other']::text[]
     and cardinality(a) = (select count(distinct x) from unnest(a) as x)
     and (not ('other' = any(a)) or cardinality(a) = 1)
$$;
grant execute on function public.interests_valid(text[]) to anon;

create or replace function public.use_values_valid(a text[]) returns boolean
language sql immutable set search_path = ''
as $$
  select a is not null
     and cardinality(a) between 1 and 2
     and a <@ array['assistant','translation','notifications','big_screen','capture','vision_ai','study_work_ai','ar_games','none']::text[]
     and cardinality(a) = (select count(distinct x) from unnest(a) as x)
     and (not ('none' = any(a)) or cardinality(a) = 1)
$$;
grant execute on function public.use_values_valid(text[]) to anon;

create table if not exists public.responses (
  resp_id       uuid primary key,                       -- 클라이언트가 만든 UUID: 재전송해도 중복 저장되지 않음
  received_at   timestamptz not null default now(),     -- 서버 수신 시각
  t_start       timestamptz not null,
  t_end         timestamptz not null,
  duration_sec  integer not null check (duration_sec between 0 and 7200),
  age_band      text not null check (age_band in ('20_22','23_25','26_27','28_29')),  -- 20대만 저장(비해당자는 저장하지 않음)
  q1_phone      text not null check (q1_phone in ('iphone','galaxy','other')),
  q2_xr         text not null check (q2_xr in ('none','tried','owner')),
  wtp_band      text not null check (wtp_band in ('lt100','100_150','150_170','170_200','gte200','none')),  -- 카드보다 먼저 질문(앵커링 방지)
  card_order    smallint[] not null
                check (cardinality(card_order) = 8 and card_order @> array[1,2,3,4,5,6,7,8]::smallint[]),
  card_ms       integer[]  not null check (cardinality(card_ms) = 8),
  intent_p1     smallint not null check (intent_p1 between 1 and 7),
  intent_p2     smallint not null check (intent_p2 between 1 and 7),
  intent_p3     smallint not null check (intent_p3 between 1 and 7),
  intent_p4     smallint not null check (intent_p4 between 1 and 7),
  intent_p5     smallint not null check (intent_p5 between 1 and 7),
  intent_p6     smallint not null check (intent_p6 between 1 and 7),
  intent_p7     smallint not null check (intent_p7 between 1 and 7),
  intent_p8     smallint not null check (intent_p8 between 1 and 7),
  q3_barrier    text not null check (q3_barrier in ('price','apps','peers','comfort','privacy','other')),
  q3_other      text check (q3_other is null or char_length(q3_other) <= 100),
  q4_constraints text[] not null check (public.q4_valid(q4_constraints)),
  device_type   text not null check (device_type in ('mobile','tablet','desktop')),
  form_version  text not null check (char_length(form_version) <= 10),
  is_test       boolean not null default false,         -- ?test=1 로 접속한 시험 응답
  src           text check (src is null or src ~ '^[A-Za-z0-9_-]{1,40}$'),  -- 배포 경로 태그(?src=)
  -- v5 신규 (NULL 허용: v4 이전 행. form_version = 'v5' 이면 필수)
  interests     text[]  constraint responses_interests_check    check (interests is null or public.interests_valid(interests)),
  adopt_style   text    constraint responses_adopt_style_check  check (adopt_style is null or adopt_style in ('early','review','price_drop','need_only','none')),
  value_source  text    constraint responses_value_source_check check (value_source is null or value_source in ('device','ai','apps','content','peers_info','peers_together','price','none')),
  use_values    text[]  constraint responses_use_values_check   check (use_values is null or public.use_values_valid(use_values)),
  intro_ms      integer constraint responses_intro_ms_check     check (intro_ms is null or intro_ms between 0 and 3600000),  -- 제품 소개 화면 체류 시간(ms)
  constraint responses_v5_required_check
    check (form_version <> 'v5' or (interests is not null and adopt_style is not null and value_source is not null
                                    and use_values is not null and intro_ms is not null))
);

alter table public.responses enable row level security;
revoke all on public.responses from anon, authenticated;
grant insert on public.responses to anon;
create policy "anon_insert_only" on public.responses for insert to anon with check (true);

-- 분석용 long 형식: 응답자 x 상품 (컨조인트 회귀에 바로 사용). API로 노출되지 않도록 anon/authenticated 권한 제거.
create or replace view public.conjoint_long with (security_invoker = true) as
select r.resp_id, r.is_test, r.src, r.age_band, r.q1_phone, r.q2_xr, r.wtp_band, r.q3_barrier, r.q4_constraints, r.duration_sec,
       d.profile_id, d.price_low, d.apps_many, d.peers_many, d.standalone,
       (array[r.intent_p1, r.intent_p2, r.intent_p3, r.intent_p4,
              r.intent_p5, r.intent_p6, r.intent_p7, r.intent_p8])[d.profile_id] as intent,
       array_position(r.card_order, d.profile_id::smallint) as order_pos,
       r.card_ms[array_position(r.card_order, d.profile_id::smallint)]  as card_ms,
       r.interests, r.adopt_style, r.value_source, r.use_values, r.intro_ms
from public.responses r
cross join (values (1,0,0,0,0),(2,0,0,1,1),(3,0,1,0,1),(4,0,1,1,0),
                   (5,1,0,0,1),(6,1,0,1,0),(7,1,1,0,0),(8,1,1,1,1))
       as d(profile_id, price_low, apps_many, peers_many, standalone);
revoke all on public.conjoint_long from anon, authenticated;
