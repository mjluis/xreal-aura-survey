# AI 글라스 구매 의향 설문 v5 (Apple 스타일 프런트엔드 + Supabase)

구성: `index.html`(화면+로직, 외부 라이브러리 없음) · `config.js`(연결 정보) · `supabase/schema.sql`(테이블·RLS·분석 view) · `tests/`(자동 테스트)

## 동작 방식
- 정적 페이지가 Supabase REST(`POST /rest/v1/responses`)로 마지막에 한 번 저장합니다. 서버 코드 없음.
- 익명 키로는 **INSERT만** 가능합니다(SELECT/UPDATE/DELETE 불가). 값 검증은 DB의 CHECK 제약이 합니다.
- 응답마다 클라이언트가 만든 `resp_id`(UUID)를 사용합니다. 재전송으로 같은 응답이 다시 가면 DB가 409로 거부하고, 화면은 이를 "이미 저장됨"으로 처리합니다.
- `config.js`가 비어 있으면 로컬 테스트 모드(브라우저 localStorage에만 저장)로 동작합니다.

## URL 파라미터
- `?test=1` : 시험 응답(`is_test=true`로 저장, 중복 참여 방지 우회). 분석 전에 `is_test=false`만 사용하십시오.
- `?src=kakao` : 배포 경로 태그(`src` 컬럼). 표본 구성 파악용.

## 설문 흐름 (v5)
intro(동의) → age(연령대 4구간, "20~29세 아님"이면 종료·미저장) → **interests**(취미·관심 분야, 최대 2개, '기타' 단독, 앞 8개 무작위) → **adopt_style**(새 IT 기기 구매 성향, 5개 고정 순서) → q1(스마트폰) → q2(XR 경험) → **product**(XREAL AURA 소개 1화면, 자동 진행 없음, 체류 시간 intro_ms) → wtp(지불 가능 금액, 카드보다 먼저) → 카드 8장(무작위 순서) → q3(가장 망설이는 이유 1개) → q4(앱·콘텐츠가 있어도 망설이는 이유, 최대 2개) → **value_source**(가장 의미 있는 가치 1개, 앞 7개 무작위·'없다' 마지막) → **use_values**(사용하려면 필요한 기능, 최대 2개, '없다' 단독, 앞 8개 무작위) → 제출

- 무작위 보기 순서는 응답자별로 localStorage에 보존됩니다(새로고침·이전 버튼 후에도 동일). 복수 선택 값은 정해진(canonical) 순서로 저장합니다.
- localStorage 키는 `_v5`입니다. v4 중간 상태는 v5 흐름에 섞이지 않습니다.
- 대학생 여부는 묻지 않습니다. 대학생 대상 여부는 배포 채널(`?src=`)로 관리합니다.

## DB
- 처음 만들 때: `supabase/schema.sql` (v5)
- v4 테이블이 이미 있을 때: `supabase/migration_v5.sql` 전체를 SQL Editor에서 한 번에 실행. 기존 행은 지우지 않고, 여러 번 실행해도 결과가 같습니다(멱등).
- (참고) v3 → v4: `supabase/migration_v4.sql` (시험 응답을 삭제하므로 v4 이후 DB에는 실행하지 마십시오)
- v4 컬럼: age_band(20_22/23_25/26_27/28_29), wtp_band(lt100/100_150/150_170/170_200/gte200/none), q4_constraints(text[], 1~2개, none은 단독)
- v5 컬럼(모두 NULL 허용, `form_version='v5'`이면 필수):
  interests(text[], gaming/tech_gadget/video/study/creative/sports/travel/social/other, 1~2개, other 단독) ·
  adopt_style(early/review/price_drop/need_only/none) ·
  value_source(device/ai/apps/content/peers_info/peers_together/price/none) ·
  use_values(text[], assistant/translation/notifications/big_screen/capture/vision_ai/study_work_ai/ar_games/none, 1~2개, none 단독) ·
  intro_ms(제품 소개 화면 체류 ms, 0~3,600,000)

### v5 배포 순서 (반드시 이 순서)
1. 프런트 변경은 `v5` 브랜치에서만 작업합니다. Pages는 `main`을 서빙하므로 브랜치 푸시는 라이브에 영향이 없습니다.
2. **SQL 먼저**: Supabase SQL Editor에서 `supabase/migration_v5.sql`을 실행합니다.
3. **푸시는 그다음**: 마이그레이션이 끝난 뒤 `v5`를 `main`에 머지·푸시합니다. 순서가 바뀌면 새 프런트가 보내는 v5 필드를 DB가 몰라 응답 저장이 실패합니다.
4. 배포 후 `?test=1&src=deploy_check`로 한 번 제출해 저장되는지 확인하고, 시험 행은 `delete from responses where is_test;`로 지웁니다.

## 분석
`select * from conjoint_long where not is_test;` → 응답자×상품 long 형식 (intent, price_low, apps_many, peers_many, standalone, order_pos, card_ms + age_band, q1_phone, q2_xr, wtp_band, q3_barrier, q4_constraints + v5: interests, adopt_style, value_source, use_values, intro_ms). SQL Editor에서 CSV로 내려받습니다.
- 가격 이탈률: 169만 원 = wtp_band in (lt100,100_150,150_170,none), 199만 원 = 여기에 170_200 추가.
- v4로 받은 행은 v5 컬럼이 NULL입니다. v5 문항 분석은 `form_version = 'v5'` 행만 사용하십시오.

### 세분화 정의 (사전 지정, 결과를 보기 전에 정한 것)
아래 정의는 데이터를 보기 전에 정했으며, **데이터를 본 뒤에 바꾸지 않습니다.**
- 게이머 = interests에 `gaming` 포함
- 얼리어답터 성향 (**임시**, MJ 확정 전) = adopt_style이 `early` 또는 `review`이거나, interests에 `tech_gadget` 포함
- 기타 = 위 어디에도 해당하지 않는 응답
- (게이머이면서 얼리어답터 성향인 응답은 두 집단에 모두 포함됩니다.)

### 가치 제공 주체 묶음 (사전 지정)
value_source를 아래처럼 묶습니다. **데이터를 본 뒤에 바꾸지 않습니다.** (최종 묶음은 MJ 확정 전까지 **임시**)
- 기기·AI = `device`, `ai`
- 앱·콘텐츠 = `apps`, `content`
- 이용자 = `peers_info`, `peers_together`
- 가격 = `price`
- 없음 = `none`

### 한계
1. 표본이 약 50명이라 세분화 집단은 10~20명 수준이고, value_source도 선택지당 몇 명입니다. 통계 검정이 아니라 **기술 통계로만** 사용합니다.
2. 대학생 여부는 배포 채널(`?src=`)로만 관리하며, 응답에서 확인하지 않습니다.
3. value_source와 use_values는 응답자가 말로 답한 중요도(진술 선호)이므로, 컨조인트 카드 응답·q3와 방향이 다를 수 있습니다.

## 테스트
`python tests/e2e_local.py` (로컬 모드 전체 v5 흐름, 신규 문항 규칙, 제품 소개 금지 문구 자동 검사, payload가 DB CHECK 형식을 통과하는지), `python tests/e2e_network.py` (재시도·실패 복구·409/400 처리, 종료 경로 미전송), `python tests/shots.py` (신규 화면 스크린샷, 360/390/데스크톱 × 라이트/다크, 커밋 제외). Playwright + Chromium 필요(`pip install playwright` → `python -m playwright install chromium`).

## 배포 (GitHub Pages)
1. GitHub에서 **public** 저장소를 만듭니다(무료 플랜의 Pages는 public 저장소만 지원). README/.gitignore는 추가하지 않습니다.
2. 이 폴더(index.html이 있는 폴더)에서:
   `git init` → `git add .` → `git commit -m "survey v3"` → `git branch -M main` → `git remote add origin https://github.com/<계정>/<저장소>.git` → `git push -u origin main`
3. 저장소 **Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: main / (root) → Save**. 1~2분 뒤 `https://<계정>.github.io/<저장소>/` 로 열립니다.
4. `index.html`의 `YOUR-USERNAME` / `YOUR-REPO` 두 곳(og:url, og:image)을 실제 값으로 바꾸고 push 합니다.
5. 공개 저장소이므로 비밀 키(secret/service_role)는 절대 커밋하지 마십시오. config.js의 publishable 키는 공개되어도 됩니다.

## 링크 미리보기
- 이미지는 `og.png`(1200x600, 2:1). 이미지를 바꾸면 `og:image`의 `?v=1`을 `?v=2`로 올려 캐시를 우회하십시오.
- 카카오톡은 주소 끝의 `/` 유무를 서로 다른 캐시로 처리할 수 있으니, 공유 링크는 항상 같은 형태(끝에 `/`)로 쓰십시오.
