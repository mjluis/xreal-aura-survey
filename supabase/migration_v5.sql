-- v4 → v5 마이그레이션. Supabase SQL Editor에서 이 파일 전체를 한 번에 실행하십시오.
-- 기존 행은 지우지 않습니다. 새 컬럼은 NULL 허용이며, form_version = 'v5' 인 행에서만 필수입니다.
-- 여러 번 실행해도 결과가 같습니다(멱등). RLS·정책·anon 권한(INSERT 전용)은 바꾸지 않습니다.
begin;

-- interests(최대 2개) 검증: 허용값만, 1~2개, 중복 불가, 'other'는 단독.
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

-- use_values(최대 2개) 검증: 허용값만, 1~2개, 중복 불가, 'none'은 단독.
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

alter table public.responses
  add column if not exists interests    text[],
  add column if not exists adopt_style  text,
  add column if not exists value_source text,
  add column if not exists use_values   text[],
  add column if not exists intro_ms     integer;

-- 값 CHECK (NULL이면 통과). 다시 실행해도 되도록 지우고 다시 만듭니다.
alter table public.responses
  drop constraint if exists responses_interests_check,
  drop constraint if exists responses_adopt_style_check,
  drop constraint if exists responses_value_source_check,
  drop constraint if exists responses_use_values_check,
  drop constraint if exists responses_intro_ms_check,
  drop constraint if exists responses_v5_required_check;

alter table public.responses
  add constraint responses_interests_check
    check (interests is null or public.interests_valid(interests)),
  add constraint responses_adopt_style_check
    check (adopt_style is null or adopt_style in ('early','review','price_drop','need_only','none')),
  add constraint responses_value_source_check
    check (value_source is null or value_source in ('device','ai','apps','content','peers_info','peers_together','price','none')),
  add constraint responses_use_values_check
    check (use_values is null or public.use_values_valid(use_values)),
  add constraint responses_intro_ms_check
    check (intro_ms is null or intro_ms between 0 and 3600000),
  add constraint responses_v5_required_check
    check (form_version <> 'v5' or (interests is not null and adopt_style is not null and value_source is not null
                                    and use_values is not null and intro_ms is not null));

-- 분석용 view: 기존 컬럼·순서 유지, 새 컬럼은 끝에 추가.
drop view if exists public.conjoint_long;
create view public.conjoint_long with (security_invoker = true) as
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

commit;
