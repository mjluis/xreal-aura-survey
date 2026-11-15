# AI 글라스 구매 의향 설문 v3 (Apple 스타일 프런트엔드 + Supabase)

구성: `index.html`(화면+로직, 외부 라이브러리 없음) · `config.js`(연결 정보) · `supabase/schema.sql`(테이블·RLS·분석 view) · `tests/`(자동 테스트)

## 동작 방식
- 정적 페이지가 Supabase REST(`POST /rest/v1/responses`)로 마지막에 한 번 저장합니다. 서버 코드 없음.
- 익명 키로는 **INSERT만** 가능합니다(SELECT/UPDATE/DELETE 불가). 값 검증은 DB의 CHECK 제약이 합니다.
- 응답마다 클라이언트가 만든 `resp_id`(UUID)를 사용합니다. 재전송으로 같은 응답이 다시 가면 DB가 409로 거부하고, 화면은 이를 "이미 저장됨"으로 처리합니다.
- `config.js`가 비어 있으면 로컬 테스트 모드(브라우저 localStorage에만 저장)로 동작합니다.

## URL 파라미터
- `?test=1` : 시험 응답(`is_test=true`로 저장, 중복 참여 방지 우회). 분석 전에 `is_test=false`만 사용하십시오.
- `?src=kakao` : 배포 경로 태그(`src` 컬럼). 표본 구성 파악용.

## 설문 흐름 (v4)
intro(동의) → age(연령대 4구간, "20~29세 아님"이면 종료·미저장) → q1(스마트폰) → q2(XR 경험) → wtp(지불 가능 금액, 카드보다 먼저) → 카드 8장(무작위 순서) → q3(가장 망설이는 이유 1개) → q4(앱·콘텐츠가 있어도 망설이는 이유, 최대 2개) → 제출

## DB
- 처음 만들 때: `supabase/schema.sql`
- v3 테이블이 이미 있을 때: `supabase/migration_v4.sql` 전체를 SQL Editor에서 한 번에 실행. 시험 응답(is_test=true)을 모두 삭제하고, 실제 응답이 하나라도 있으면 아무것도 바꾸지 않고 중단합니다.
- 새 컬럼: age_band(20_22/23_25/26_27/28_29), wtp_band(lt100/100_150/150_170/170_200/gte200/none), q4_constraints(text[], 1~2개, none은 단독)

## 분석
`select * from conjoint_long where not is_test;` → 응답자×상품 long 형식 (intent, price_low, apps_many, peers_many, standalone, order_pos, card_ms + age_band, q1_phone, q2_xr, wtp_band, q3_barrier, q4_constraints). SQL Editor에서 CSV로 내려받습니다.
- 가격 이탈률: 169만 원 = wtp_band in (lt100,100_150,150_170,none), 199만 원 = 여기에 170_200 추가.

## 테스트
`python3 tests/e2e_local.py` (로컬 모드 전체 흐름), `python3 tests/e2e_network.py` (재시도·실패 복구·409/400 처리). Playwright + Chrome 필요.

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
