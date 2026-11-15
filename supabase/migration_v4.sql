-- v3 → v4 마이그레이션. Supabase SQL Editor에서 이 파일 전체를 한 번에 실행하십시오.
-- 주의: 시험 응답(is_test = true)을 모두 삭제합니다. 실제 응답(is_test = false)이 하나라도 있으면 아무것도 바꾸지 않고 중단합니다.
begin;

do $$
begin
  if exists (select 1 from public.responses where not is_test) then
    raise exception '실제 응답(is_test=false)이 있어 마이그레이션을 중단합니다. 데이터를 백업하고 별도 이관 SQL이 필요합니다.';
  end if;
end $$;

delete from public.responses where is_test;

drop view if exists public.conjoint_long;

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

alter table public.responses drop column s1_20s;
alter table public.responses
  add column age_band text not null check (age_band in ('20_22','23_25','26_27','28_29')),
  add column wtp_band text not null check (wtp_band in ('lt100','100_150','150_170','170_200','gte200','none')),
  add column q4_constraints text[] not null check (public.q4_valid(q4_constraints));

create view public.conjoint_long with (security_invoker = true) as
select r.resp_id, r.is_test, r.src, r.age_band, r.q1_phone, r.q2_xr, r.wtp_band, r.q3_barrier, r.q4_constraints, r.duration_sec,
       d.profile_id, d.price_low, d.apps_many, d.peers_many, d.standalone,
       (array[r.intent_p1, r.intent_p2, r.intent_p3, r.intent_p4,
              r.intent_p5, r.intent_p6, r.intent_p7, r.intent_p8])[d.profile_id] as intent,
       array_position(r.card_order, d.profile_id::smallint) as order_pos,
       r.card_ms[array_position(r.card_order, d.profile_id::smallint)]  as card_ms
from public.responses r
cross join (values (1,0,0,0,0),(2,0,0,1,1),(3,0,1,0,1),(4,0,1,1,0),
                   (5,1,0,0,1),(6,1,0,1,0),(7,1,1,0,0),(8,1,1,1,1))
       as d(profile_id, price_low, apps_many, peers_many, standalone);
revoke all on public.conjoint_long from anon, authenticated;

commit;
