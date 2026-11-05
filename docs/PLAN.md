# dongseon 구현 계획서

이 문서는 Claude Code가 `dongseon` 레포를 처음부터 구현할 때 기준으로 삼는 계획서입니다. 작업 전에 전체를 읽고 18절의 마일스톤 순서대로 진행하세요. 레포에는 `docs/PLAN.md`로 둡니다.

이 문서에는 개인 정보가 없습니다. 실제 여행 날짜, 동행자, 예약 정보는 DB와 gitignore된 `config/profile.yaml`에만 둡니다.

---

## 0. 참고 구현 (jipsa)

같은 Mac의 `~/Projects/workspace/jipsa`는 같은 사람이 같은 방식으로 만든 레포입니다. 구조, 도구, 규칙, 스크립트는 jipsa에 맞추고, 아래 파일은 먼저 읽고 패턴을 그대로 가져오세요. 이름만 바꾸면 되는 파일은 복사해서 시작해도 됩니다.

| 가져올 것 | jipsa 경로 |
|---|---|
| 에이전트 규칙 | `CLAUDE.md`, `.claude/rules/*.md` (7개 파일 구성은 그대로, 내용은 이 계획에 맞게) |
| 사람용 문서 | `README.md`, `CONTRIBUTING.md`, `.gitmessage.txt` |
| Python 설정 | `pyproject.toml` (ruff, pyright, pytest 설정), `.python-version` |
| 품질·CI | `.pre-commit-config.yaml`, `.markdownlint.yaml`, `.github/workflows/*`, `.github/PULL_REQUEST_TEMPLATE.md` |
| 실행 | `Makefile`, `scripts/{env.sh,install_packages.sh,run_pytest.sh,launchd.sh}` |
| 설정·잠금 | `jipsa/core/{config.py,lock.py,profile.py}` |
| DB | `jipsa/db/session.py`, `LlmRun` 모델, Alembic 설정 (SQLite batch mode) |
| LLM | `jipsa/llm/claude_cli.py` (headless Claude Code 호출과 `llm_runs` 기록), `jipsa/llm/cost_estimates.py` (WebSearch 허용 조사와 결과 검증 패턴), `jipsa/llm/prompts/` |
| 프론트 | `frontend/`의 Vite·tsconfig·Prettier·oxlint 설정, `src/api/{client.ts,hooks.ts}`, `src/lib/format.ts`, `make gen-types` (typescript@5.9.3 dlx 우회 포함) |
| 원격 접속 | `config/Caddyfile`, `scripts/caddy.sh` (15절. 터널 연결기는 공유하고 `tunnel.sh`는 가져오지 않음) |

jipsa에서 얻은 교훈도 그대로 적용합니다.

- 외부 서비스는 구현 전에 약관부터 확인합니다. jipsa는 네이버 검색 API를 붙였다가 AI 입력 금지와 결과 저장 금지 약관 때문에 Google News RSS로 바꿨습니다.
- 지도·경로 결과를 저장해도 되는지는 서비스마다 다릅니다. jipsa는 Kakao 경로 결과를 저장하지 않습니다.
- LLM은 Anthropic API 키 없이 headless Claude Code(`claude -p`)를 사용자 구독으로 호출합니다.

---

## 1. 목표와 범위

여행을 준비하는 한 가구(동행자 포함)가 집 Mac에서 띄워 쓰고, 여행 중에는 휴대폰으로 접속하는 여행 계획 앱입니다. 첫 사용처는 연말 도쿄 5일 여행이고, 이후 다른 도시에도 계속 씁니다.

앱이 답하려는 질문은 다음과 같습니다.

1. 가고 싶은 곳(핀)을 어떻게 모으고 정리하나
2. 핀 위치를 기준으로 어느 동네에 묵는 게 유리하고, 후보 숙소들은 어떻게 비교되나
3. 항공편 후보 중 현지에서 쓸 수 있는 시간과 총비용 기준으로 무엇이 나은가
4. 영업시간, 휴무, 이동시간을 지키면서 날짜별 동선을 어떻게 짜나
5. 비 오는 날, 휴무, 연휴 같은 변수에 어떻게 대응하나
6. 여행 중에 오늘 일정과 다음 이동을 휴대폰에서 바로 보고 길찾기를 열 수 있나

### Non-goals

- 항공권·숙소 예약과 결제, 예약 사이트 스크래핑
- 다중 사용자와 로그인 (원격 접속은 Caddy basic auth 하나를 가구가 공유)
- 실시간 가격 비교 엔진
- 블로그·리뷰 크롤링

---

## 2. 기술 스택

jipsa와 같게 맞춥니다.

| 영역 | 선택 |
|---|---|
| Backend | Python 3.12, uv (루트 단일 프로젝트), FastAPI, SQLAlchemy 2.x + Alembic, SQLite, httpx, pydantic-settings, Typer, PyYAML |
| 동선 계산 | OR-Tools routing solver (VRP with time windows) |
| 기타 Python | `holidays` (국가별 공휴일), `zoneinfo` |
| LLM | headless Claude Code (`claude -p`, `--json-schema`). jipsa의 `claude_cli.py` 이식 |
| Frontend | Vite 8, React 19, TypeScript 7, pnpm, TanStack Query, React Router, Tailwind CSS 4, `@vis.gl/react-google-maps`, Vitest + Testing Library, oxlint, Prettier |
| PWA | 오프라인 캐시용 service worker. 플러그인(`vite-plugin-pwa` 등)은 Vite 8 호환을 확인하고 승인받은 뒤 추가 |
| 품질 | ruff, pyright, pytest + respx, pre-commit, GitHub Actions |

OR-Tools, `holidays`, `@vis.gl/react-google-maps`는 이 계획 승인으로 추가를 허락받은 것으로 봅니다. 그 밖의 패키지는 추가 전에 물어보세요.

포트는 jipsa와 겹치지 않게 정합니다.

| 용도 | jipsa | dongseon |
|---|---|---|
| 상시 앱 (`serve`, launchd) | 8000 | 8100 |
| 개발 백엔드 (`make dev`, reload) | 8001 | 8101 |
| Vite dev server | 5173 | 5174 |

---

## 3. 레포 구조

```text
dongseon/
├── CLAUDE.md
├── README.md / CONTRIBUTING.md
├── Makefile
├── pyproject.toml / uv.lock
├── .env.example
├── .gitignore                    # .env, config/profile.yaml, data/ 등
├── alembic/ + alembic.ini
├── config/
│   ├── profile.example.yaml      # 가짜 값. 테스트와 예시용
│   ├── profile.yaml              # gitignore. 여행자 라벨, 출발 공항, 선호, 버퍼
│   ├── defaults.yaml             # 카테고리 매핑, 카테고리별 기본 체류시간
│   ├── checklist.yaml            # 준비물·사전 절차 템플릿
│   └── cities/
│       └── tokyo.yaml            # 시간대, 통화, 공항, 숙소 후보 동네, 연휴 규칙
├── data/                         # gitignore. dongseon.db, 로그, 잠금, openapi.json
├── docs/
│   ├── PLAN.md
│   └── google-terms.md           # M0에서 작성하는 Google 약관 요약 (6절)
├── dongseon/
│   ├── main.py / cli.py / daily.py
│   ├── core/                     # config, profile, cities, lock, usage meter
│   ├── db/                       # models, session
│   ├── sources/                  # google_places, google_routes, open_meteo, fx, takeout
│   ├── places/                   # 핀 가져오기, place_id 해석, 날짜별 영업 정보 병합
│   ├── matrix/                   # 이동시간 행렬 (근사, transit)
│   ├── stays/                    # 동네 점수, 숙소 후보 비교
│   ├── flights/                  # 항공 후보 평가
│   ├── planner/                  # OR-Tools 모델, validator, 편집 적용
│   ├── llm/                      # claude_cli, payloads, prompts/*.md, review, research, parse
│   ├── export/                   # ICS, 인쇄용 HTML, Google Maps URL
│   └── api/routes/
├── tests/unit_test/ (+ fixtures/)
├── frontend/src/{pages,components,api,lib}
└── scripts/
```

---

## 4. 핵심 개념

| 개념 | 설명 |
|---|---|
| Trip | 도시, 시작·종료일, 시간대, 일정 강도(pace) |
| Place | Google `place_id`와 사용자가 붙인 라벨·카테고리·메모. 여러 여행에서 재사용 |
| Pin | 특정 Trip에 넣은 Place. 우선순위(must / want / maybe), 체류시간, 예약 시각, 식사 구분 |
| Stay | 숙소 후보 또는 확정 숙소 (체크인·체크아웃, 총액, 예약 링크) |
| Flight option | 왕복 항공 후보 (구간별 출발·도착 시각과 공항, 총액, 수하물) |
| Itinerary | 날짜별 방문 순서와 시각. solver 초안, AI 제안 반영, 사용자 편집이 버전으로 쌓임 |
| Hours override | 특정 날짜의 영업 정보 (Google 특별 영업일, AI 조사, 사용자 입력) |

---

## 5. 외부 데이터 소스

| 소스 | 용도 | 인증 | 비고 |
|---|---|---|---|
| Google Places API (New) | 장소 검색, 자동완성, 상세(좌표, 영업시간, 유형) | 서버 키 | FieldMask로 필드를 최소화. 요청 필드에 따라 Essentials / Pro / Enterprise SKU로 과금 |
| Google Routes API | 도보 이동시간, 일자별 경로 표시(computeRoutes) | 서버 키 | **일본은 transit 경로를 돌려주지 않음** (2026-11-05 확인: 도쿄 TRANSIT는 행렬·단일 경로 모두 결과 없음, 서울·뉴욕은 정상). 도보는 됨 |
| Google Maps JavaScript API | 프론트 지도 | 브라우저 키 + Map ID | Advanced Marker를 쓰려면 Map ID 필요 |
| Google Maps URLs | 길찾기·장소 열기 딥링크 | 없음 | 휴대폰에서 Google Maps 앱으로 넘김 |
| Google Takeout (저장됨) | 사용자가 Google Maps에 저장한 리스트 가져오기 | 없음 (사용자 파일) | 리스트마다 CSV 하나. 알려진 컬럼은 Title, Note, URL, Comment, Tag이고 좌표나 place_id 컬럼은 없음. 실제 파일로 확인 후 파서 작성 |
| Open-Meteo | 일자별 예보, 같은 날짜의 과거 기후 | 없음 | 비상업 무료, 예보는 최대 16일 |
| Frankfurter (ECB 기준환율) | JPY 등을 KRW로 환산 | 없음 | 영업일 기준 하루 한 번 |
| `holidays` 패키지 | 여행지 공휴일 | 없음 | 연휴 기간 영업 변동은 `config/cities/*.yaml` (12절) |
| Claude Code (headless) | 일정 검토, 맛집·영업시간 웹 조사, 예약 메일 파싱 | 사용자 구독 | 13절 |

### 5.1 Google 과금과 사용량 관리

2026-11 기준 가격표의 월 무료 한도입니다. 구현 시 공식 가격표로 다시 확인하세요.

| SKU | 월 무료 | 이후 1,000건당 |
|---|---|---|
| Place Details Essentials / Pro / Enterprise | 10,000 / 5,000 / 1,000 | $5 / $17 / $20 |
| Text Search Pro / Enterprise | 5,000 / 1,000 | $32 / $35 |
| Text Search IDs Only | 무제한으로 표시됨 | |
| Autocomplete Requests | 10,000 | $2.83 |
| Compute Routes Essentials / Pro | 10,000 / 5,000 | $5 / $10 |
| Compute Route Matrix Essentials / Pro | 10,000 / 5,000 | $5 / $10 |
| Dynamic Maps | 10,000 | $7 |

- 이름으로 place_id만 찾을 때는 Text Search IDs Only를 먼저 씁니다.
- 영업시간처럼 상위 SKU로 과금되는 필드는 must/want 핀에만, 필요한 날에만 요청합니다. 어떤 필드가 어느 SKU인지는 SKU 문서로 확인해서 `sources/google_places.py`의 FieldMask 상수 옆에 주석으로 남깁니다.
- 개인 사용량이면 무료 한도 안에서 충분하지만 Cloud 결제 계정 등록이 필요합니다. 그래서 두 겹으로 막습니다.
  - Cloud Console에서 API별 일일 quota 상한과 예산 알림을 설정합니다 (README에 절차 기록).
  - 앱은 SKU별 월간 호출 수를 `api_usage`에 기록하고, 무료 한도 대비 `GOOGLE_FREE_TIER_WARN_RATIO`에서 경고, `GOOGLE_FREE_TIER_STOP_RATIO`에서 해당 호출을 막습니다. SKU별 한도 숫자는 `config/defaults.yaml`에 두고 코드에 넣지 않습니다.

### 5.2 쓰지 않는 소스와 이유

- 항공권 검색 API: Amadeus Self-Service가 2026-07-17에 종료되었습니다. 대신 Ignav(무료 1,000회, 이후 1,000회당 $2, 약관상 결과 저장·분석 허용)를 2026-11-05 사용자 승인으로 붙였습니다. SerpApi는 Google 스크래핑이라 쓰지 않습니다. 비교는 `docs/travel-data-sources.md`.
- 숙소 가격 API: Booking, Agoda, Expedia, Airbnb API는 제휴 파트너용입니다. 楽天トラベル 공실 검색 API(무료, 공식)로 호텔 빈방·요금을 받고, 에어비앤비는 검색 링크와 직접 입력으로 대신합니다.
- 타베로그, 네이버 블로그, 항공·숙소 예약 사이트 화면: 공개 API가 없거나 자동 수집이 허용되지 않습니다. 수집하지 않고 검색 딥링크만 제공합니다.

---

## 6. Google 약관 준수 (M0에서 확정)

구현을 다 하고 나서 약관에 막히지 않도록, M0에서 Google Maps Platform Terms of Service, Service Specific Terms, Places API와 Routes API의 policies 원문을 읽고 `docs/google-terms.md`에 아래 네 가지를 원문 링크·확인일과 함께 정리한 뒤 사용자 확인을 받습니다.

1. 저장할 수 있는 것과 기간. Places policies는 place ID를 무기한 저장할 수 있다고 명시합니다. 좌표, 이름, 영업시간, 평점 등 나머지의 캐시 허용 범위는 원문으로 확인합니다.
2. Google 콘텐츠를 Google이 아닌 LLM의 입력으로 보내는 것에 대한 제한이 있는지
3. Google 데이터를 Google이 아닌 지도와 함께 쓰는 것에 대한 제한
4. 지도 없이 Places 데이터를 보여줄 때의 표기 의무 (Google Maps 로고 또는 텍스트, 사진·리뷰 작성자 표기와 `googleMapsUri` 링크)

2026-11-04에 원문을 확인해 `docs/google-terms.md`에 정리했고, 사용자와 아래 보수적 설계로 확정했습니다. 근거는 ToS 3.2.3(a)(b)(c)와 Service Specific Terms(캐시 허용 범위, 10.2.1 LLM 예외)입니다.

- DB에 영구 저장하는 Google 데이터는 `place_id`뿐입니다. 12개월마다 IDs Only 요청(무료)으로 갱신합니다.
- 라벨, 메모, 카테고리, 우선순위는 사용자 데이터입니다. Takeout CSV 제목은 사용자 본인 데이터라 라벨로 씁니다. 앱 검색으로 추가한 장소의 라벨 기본값은 사용자가 입력한 검색어이고, Google `displayName`은 복사해 저장하지 않습니다 (ToS 3.2.3(a)(iii)).
- 캐시할 수 있는 Google 응답은 좌표뿐이고 최대 30일입니다 (`geo_cache`). 이름, 주소, 영업시간, 이동시간, 거리는 DB나 디스크에 캐시하지 않고 필요할 때 조회해 그 요청 안에서만 씁니다.
- 비용은 캐시 대신 FieldMask 최소화(IDs Only, Essentials 우선)와 근사 행렬(11.3)로 줄입니다.
- LLM 입력에는 사용자 데이터(라벨, 앱 카테고리, 우선순위, 순서, 체류시간, 사용자가 입력한 영업 정보)와, 코드가 계산한 추상 플래그("3번째 일정이 영업시간 밖", "이동 여유 부족")만 넣습니다. Google에서 받은 영업 시각, 분 단위 이동시간, 상호명, 주소, 좌표는 넣지 않습니다. payload 생성은 `llm/payloads.py` 한 곳에 모읍니다.
- 지도는 Google Maps JavaScript API 하나로 통일합니다. 지도 타일은 service worker로 캐시하지 않습니다.
- 일정에는 계획한 순서와 solver가 정한 시각만 저장합니다. 이것은 앱이 만든 계획 데이터로 봅니다 (해석). Google 경로 객체(polyline 등)는 저장하지 않고 화면에 띄울 때 다시 조회합니다.
- 오프라인 캐시(15절)에는 사용자 데이터, `place_id`, 30일 이내 좌표, 계획 순서와 시각, Google Maps URLs 딥링크만 담습니다.
- Google 지도 없이 Google 콘텐츠를 보여 주는 화면에는 같은 영역에 Google Maps 로고(또는 `Google Maps` 텍스트)와 `attributions[]` 제공자를 표시하고, 사용자 콘텐츠와 시각적으로 구분합니다. 앱 정보 화면에 Google Maps 추가 약관과 개인정보처리방침 링크를 둡니다.

---

## 7. 데이터 모델 (SQLite)

| 테이블 | 주요 컬럼 |
|---|---|
| `trips` | `id`, `title`, `city_key`, `start_date`, `end_date`, `timezone`, `pace`, `status` |
| `places` | `id`, `google_place_id` UNIQUE nullable, `label`, `category`, `user_note`, `source` (takeout / url / search / ai), `source_ref`, `resolve_status`, `created_at` |
| `trip_pins` | `trip_id`, `place_id`, `priority` (must / want / maybe), `dwell_min`, `meal` (lunch / dinner / null), `reserved_start`, `reserved_end`, `locked_date`, `note`, `added_by` (user / ai) |
| `hours_overrides` | `place_id`, `date`, `status` (open / closed / special / unknown), `open_time`, `close_time`, `source` (ai_research / user), `source_url`, `checked_at`. Google 영업시간은 저장하지 않음 (6절) |
| `stays` | `id`, `trip_id`, `place_id`, `label`, `check_in`, `check_out`, `total_amount`, `currency`, `booking_url`, `status` (candidate / booked) |
| `flight_options` | `id`, `trip_id`, `label`, `total_amount`, `currency`, `baggage_note`, `booking_url`, `status` (candidate / booked) |
| `flight_legs` | `option_id`, `direction` (out / back), `seq`, `carrier`, `flight_no`, `dep_airport`, `dep_at`, `arr_airport`, `arr_at` |
| `itineraries` | `id`, `trip_id`, `version`, `origin` (solver / ai / user), `status` (draft / active / archived), `created_at`, `solver_stats_json` |
| `itinerary_items` | `itinerary_id`, `date`, `seq`, `kind` (visit / meal / move / stay / flight / free), `pin_id`, `start_at`, `end_at`, `move_mode`, `move_min`, `warnings_json` |
| `ai_suggestions` | `id`, `trip_id`, `itinerary_id`, `kind` (review / rain / food / hours / stay_area), `payload_json`, `status` (pending / accepted / rejected), `prompt_version`, `created_at` |
| `geo_cache` | `place_id`, `lat`, `lng`, `fetched_at`, `expires_at` (최대 30일, 6절) |
| `api_usage` | `month`, `sku`, `count` |
| `weather` | `city_key`, `date`, `kind` (forecast / climate), `payload_json`, `fetched_at` |
| `fx_rates` | `date`, `base`, `quote`, `rate` |
| `checklist_items` | `trip_id`, `text`, `done`, `sort` |
| `llm_runs` | jipsa와 동일 |
| `job_log` | `job`, `key`, `status`, `rows`, `ran_at`, `error` |

단위 규칙

- 금액은 정수 `amount`와 ISO 4217 `currency`로 원래 통화 그대로 저장하고, KRW 환산은 표시할 때 `fx_rates`로 합니다. JPY와 KRW는 소수점이 없습니다.
- 시각은 모두 timezone-aware입니다. 항공 구간은 각 공항의 시간대, 현지 일정은 trip 시간대를 씁니다. 서울과 도쿄가 같은 UTC+9라도 코드에서 같다고 가정하지 않습니다.
- 시간 길이는 분 단위 정수(`_min`)입니다.

---

## 8. 장소(핀) 모으기

1. 앱 안 검색: Places Autocomplete와 Text Search. `languageCode=ko`, `regionCode`는 도시 config에서 가져옵니다. 결과를 추가하면 Place와 Pin이 생기고, 라벨 기본값은 사용자가 입력한 검색어입니다 (6절).
2. URL 붙여넣기: Google Maps 공유 URL(`maps.app.goo.gl` 단축 URL 포함)을 받아 place_id로 해석합니다. 단축 URL은 redirect를 따라가 이름과 좌표를 얻고 Text Search로 매칭합니다.
3. (M6 선택) Takeout 가져오기: `Takeout/Saved/*.csv`를 올리면 리스트 이름은 태그, Title은 라벨, Note는 메모로 넣고 URL로 place_id를 찾습니다. 해석에 실패하면 `resolve_status=failed`로 남기고 화면에서 수동 매칭합니다. 대량 해석은 백그라운드 CLI 잡으로 돌립니다.
4. AI 추천: 13절 맛집 조사 결과를 `priority=maybe`, `added_by=ai`로 넣습니다.

Google `types`(추가할 때 한 번 조회. Place Details에서 `types`는 Essentials, `primaryType`은 Pro라서 `types`를 씀)는 `config/defaults.yaml`의 매핑으로 앱 카테고리(food / cafe / bar / sight / museum / shopping / experience 등)에 대응시키고, 사용자가 바꿀 수 있습니다. 카테고리별 기본 체류시간도 defaults에 둡니다.

---

## 9. 숙소 위치 분석

"어느 동네에 묵으면 가고 싶은 곳들에 덜 돌아다니나"에 답합니다.

- 후보 지점은 `config/cities/tokyo.yaml`의 동네 목록(대표 역 기준)과 사용자가 넣은 숙소 후보입니다.
- 각 후보에서 must/want 핀까지 근사 이동시간(11.3)을 구하고, profile의 우선순위 가중치로 가중 평균 분을 계산합니다. 숙소 후보는 Google 장소 또는 사용자가 지도에서 찍은 위치(에어비앤비처럼 주소가 없는 곳)입니다.
- 도착·출발 공항까지의 접근 시간을 따로 보여줍니다. 공항 특급(예: 스카이라이너 닛포리 최단 36분)은 도시 config에 출처와 함께 두고, "허브역까지 근사 + 대기 + 공표 소요시간"이 더 짧으면 그 값을 씁니다.
- 화면은 지도 위 후보별 점수 색과, 가중 평균 이동시간, 가장 먼 핀까지의 시간, 공항 접근 시간, 1박 가격(환산)을 담은 표입니다.
- 동네 분위기, 소음, 주변 편의시설 같은 정성 메모는 AI 웹 조사로 덧붙일 수 있습니다 (출처 필수, M4).

순위는 근사 행렬(11.3)로 계산하고 화면에 "근사"로 표시합니다. Google이 일본 transit을 제공하지 않아 "확정 계산"은 두지 않습니다.

---

## 10. 항공 후보 평가

검색은 하지 않고 후보를 비교합니다.

- 입력은 수동 폼, 또는 예약 확인 메일이나 e-ticket 텍스트 붙여넣기입니다. 붙여넣은 텍스트는 LLM이 `flight_legs` 스키마로 파싱하고 사용자가 확인한 뒤 저장합니다.
- 현지 가용 시간 = (귀국편 출발 - 출국 공항 버퍼 - 마지막 장소에서 공항까지 이동) - (도착 + 입국 버퍼 + 공항에서 숙소까지 이동)
- 버퍼는 profile 값입니다. 공항 이동시간은 숙소(없으면 1순위 동네의 대표 역) 기준 근사(공항 특급 포함, 9절)로 계산합니다.
- 총액과 수하물 포함 여부, 가용 시간 1시간당 비용을 같이 보여줍니다.
- 화면은 후보 카드와, 후보별 도착·출발 시각을 나란히 놓은 타임라인입니다.
- 확정된 항공편은 일정 첫날의 시작점과 마지막 날의 끝점이 됩니다.

---

## 11. 일정(동선) 생성

시간 계산과 제약 검사는 코드(solver, validator)가 하고, LLM은 무엇을 넣고 뺄지와 순서에 대한 제안과 설명만 합니다. LLM의 제안은 항상 solver로 다시 풀고 validator를 통과해야 적용 후보가 됩니다.

### 11.1 입력

- 날짜별 하루 시간창은 profile의 pace에서 가져옵니다.
- 첫날은 도착 공항에서 (도착 시각 + 입국 버퍼)에 시작하고, 마지막 날은 출발 공항에 도착해야 하는 시각이 끝입니다.
- 숙소가 매일의 시작·끝 지점입니다. 중간에 숙소를 옮기면 날짜별로 다릅니다.
- 핀은 우선순위, 체류시간, 날짜별 영업 시간창(12절), 예약 시각(고정), `locked_date`를 가집니다.
- `meal`이 지정된 핀의 시간창은 profile의 점심·저녁 시간창과 영업시간의 교집합입니다.
- 이동시간은 transit와 walking 중 짧은 쪽을 쓰고, 구간마다 profile의 환승 버퍼를 더합니다.

### 11.2 Solver (OR-Tools)

- 하루를 vehicle 하나로 보는 VRP with time windows로 풉니다.
- 날짜별 영업 여부는 `SetAllowedVehiclesForIndex`로 표현합니다 (휴무일 vehicle 제외).
- 체류시간은 service time, 시간창은 time dimension으로 넣습니다.
- 우선순위는 disjunction penalty입니다. must는 drop이 사실상 불가능할 만큼 크게, want는 중간, maybe는 작게 둡니다. 가중치는 profile에서 읽습니다.
- 예약이 있는 핀은 해당 날짜와 시각에 고정합니다.
- 결과는 날짜별 순서와 도착·출발 시각, drop된 핀 목록과 사유입니다. 풀 수 없으면 어떤 제약 때문인지 알려줍니다.

### 11.3 이동시간 행렬

- Google Routes API는 일본 transit 경로를 돌려주지 않습니다 (2026-11-05 확인). 그래서 대중교통은 좌표(`geo_cache`, 30일) 사이 직선거리로 만든 근사로 계산하고 화면에 "근사"로 표시합니다.
- 근사: 우회 계수를 곱한 거리가 도보 한계 이하면 도보(분속 80 m), 아니면 "역 접근 + 대기 + 거리 ÷ 철도 평균 속도" 중 짧은 쪽입니다. 계수는 `config/cities/<city>.yaml`의 `approx`에 출처나 "가정" 표시와 함께 둡니다.
- 일정의 도보 구간(근사 기준 도보 한계 이하)은 M3에서 Google Routes WALK로 조회해 validator에 쓰고, 결과는 화면에만 보여 주고 저장하지 않습니다.
- 정확한 일본 대중교통이 필요해지면 일본 경로 API(駅すぱあと, NAVITIME)나 공개 시간표(ODPT GTFS + 경로 엔진)를 M6에서 검토합니다 (약관·가격 확인 후 승인).

### 11.4 Validator

일정 버전마다 아래를 검사해 `warnings_json`에 남기고 화면에 배지로 보여줍니다.

- 영업시간 밖 방문, 휴무일 방문, 연휴 기간인데 영업 정보 미확인
- 이동 여유가 버퍼보다 적음, 하루 시간창 초과
- 식사 시간대에 식사 일정이 없음
- 예약 시각 충돌

### 11.5 사용자 편집

드래그로 순서·날짜를 바꾸고, 핀을 잠글 수 있습니다(이 날짜, 이 순서 고정). "다시 맞추기"를 누르면 잠긴 항목은 그대로 두고 나머지만 다시 풉니다. 모든 결과는 새 버전으로 저장하고 이전 버전과 비교할 수 있습니다.

---

## 12. 영업시간과 연휴

영업시간은 여행 계획에서 가장 틀리기 쉬운 데이터이고, 첫 여행이 연말연시라 따로 다룹니다.

- 기본값은 Google `regularOpeningHours`(주간 반복)입니다.
- Google의 특별 영업일 정보(`currentOpeningHours`)는 오늘부터 7일만 다룹니다 (Place 레퍼런스로 확인). 여행 D-7부터 매일 `hours refresh`가 must/want 핀의 해당 날짜 정보를 조회해 validator를 돌리고, 경고가 바뀌면 홈과 일정 화면에 알립니다. 조회한 영업시간 자체는 저장하지 않고 경고 문구만 남깁니다 (6절).
- 연휴 규칙은 `config/cities/<city>.yaml`에 기간, 설명, `source_url`, `as_of`로 둡니다. 날짜와 설명을 코드에 넣지 않습니다.
- 연휴 기간에 걸린 must/want 핀은 AI 웹 조사(`hours research`)로 해당 날짜 영업 여부를 출처와 함께 조사해 `hours_overrides(source=ai_research)`에 넣고, 화면에 "AI 조사, 출처, 확인 필요"로 표시합니다.
- 우선순위는 사용자 입력 > Google 특별 영업일 (조회 시점) > AI 조사 > 정기 영업시간 (조회 시점)입니다. 연휴 기간인데 정기 영업시간만 있으면 "미확인" 경고를 띄웁니다.

도쿄 연휴 규칙 초안입니다 (출처는 구현 시 다시 확인).

```yaml
holiday_periods:
  - key: year_end
    start: "12-29"
    end: "01-04"
    note: >-
      많은 관광지, 상점, 식당, 은행이 이 기간 중 하루 이상 쉬며 1월 1일이 가장 제한적이다.
      박물관은 며칠씩 쉬는 경우가 많다. 신사·절은 열지만 1월 1~3일 하쓰모데로 메이지 신궁 등은
      본전까지 1시간 이상 대기할 수 있다. 연말 출발, 연초 귀경으로 교통이 붐빈다.
    source_url: https://www.japan-guide.com/e/e2276.html
    as_of: 2026-11-04
```

---

## 13. LLM 사용

jipsa의 `claude_cli.py`를 이식합니다. 기본은 도구 없이 호출하고, 조사 작업만 `WebSearch`, `WebFetch`를 허용합니다. 모든 출력은 고정 JSON 스키마와 pydantic 검증을 거칩니다. 프롬프트는 `dongseon/llm/prompts/<name>_v<N>.md`이고 파일 이름이 버전입니다.

| 작업 | 도구 | 입력 | 출력 |
|---|---|---|---|
| `plan_review` | 없음 | solver 결과(라벨, 카테고리, 순서, 체류시간, 계획 시각), 코드가 계산한 경고 플래그, drop 목록, 선호, 연휴 메모 (Google 영업 시각·이동 분은 넣지 않음) | 편집 제안 목록(`move` / `swap` / `drop` / `add_from_pool` / `set_dwell`)과 사유, 날짜별 제목, 주의사항 |
| `rain_plan` | 없음 | 비 예보가 있는 날의 일정, 실내 후보 핀 | 대체안 (편집 제안 형식) |
| `food_research` | WebSearch, WebFetch | 숙소·동선 동네 이름, 식사 시간대, 음식 선호 | 후보 목록 {이름, 동네, 추천 이유, 예약 필요 여부, 가격대, 출처 URL} |
| `hours_research` | WebSearch, WebFetch | 연휴 기간 날짜, 핀 라벨과 동네 이름 | {날짜, 상태, 시각, 출처 URL, 확신도} |
| `stay_area_notes` | WebSearch, WebFetch | 후보 동네 이름 | 동네별 장단점 메모와 출처 |
| `booking_parse` | 없음 | 사용자가 붙여넣은 예약 메일 텍스트 (마스킹 후) | `flight_legs` 또는 `stays` 스키마 |

규칙

- 편집 제안은 solver로 다시 풀고 validator를 통과한 것만 "적용 가능"으로 보이며, 사용자가 수락해야 새 버전이 됩니다. 시각은 LLM이 정하지 않습니다.
- 웹 조사 결과 중 출처 URL이 없는 항목은 버립니다. 맛집 후보는 이름으로 Text Search를 해서 place_id를 찾고, 못 찾으면 수동 매칭 대기로 둡니다.
- 입력 payload는 6절 원칙을 따르고 `llm/payloads.py`에서만 만듭니다.
- 예약 메일은 LLM에 보내기 전에 여권번호, 생년월일, 카드번호 패턴을 마스킹합니다.
- `LLM_DAILY_TOKEN_LIMIT`을 지키고, 결과는 입력 스냅샷 해시와 프롬프트 버전으로 캐시합니다.
- AI가 만든 모든 내용에는 "AI 제안" 표시를 붙입니다.

---

## 14. 화면 (모바일 우선)

jipsa처럼 390px 폭을 먼저 설계합니다. 하단 탭바, 44px 이상 터치 영역, bottom sheet 필터를 씁니다.

1. 홈: 다가오는 여행 D-day, 경고(영업 변동, 미확인, Google 무료 한도), 지난 여행
2. 장소: 지도와 리스트, 카테고리·우선순위 필터, 검색·URL·Takeout 추가, AI 추천 묶음, 해석 실패 항목 수동 매칭
3. 숙소: 동네 점수 지도와 표, 후보 숙소 비교, 확정
4. 항공: 후보 카드, 현지 가용 시간 타임라인, 확정
5. 일정: 날짜 탭, 방문·식사·이동 타임라인, 날짜별 지도 경로, 경고 배지, 드래그·잠금·다시 맞추기, AI 제안 diff(수락/거절), 비 예보 날 대체안, 버전 비교
6. 오늘 (여행 기간에 기본 탭): 지금과 다음 일정, "Google Maps로 길찾기" 버튼(Maps URLs, transit), 날씨, 환율 계산기, 오프라인 배너
7. 준비: 체크리스트(`config/checklist.yaml` 템플릿에서 생성), 예약 정보 모음
8. 설정: API 키 설정 여부, SKU별 이번 달 Google 사용량과 무료 한도, 마지막 갱신 시각, 도시 config `as_of`

UI 문구는 한국어입니다. 금액은 원래 통화와 KRW 환산을 같이 보여주고 환율 기준일을 붙입니다. Google 데이터 표기 의무(6절 4번)를 지킵니다.

---

## 15. 여행 중 사용 (원격 접속, 오프라인)

여행 중에는 휴대폰이 도쿄에, 앱은 집 Mac에 있습니다.

- 원격 접속은 dongseon이 자기 Caddy(basic auth, `config/Caddyfile`)를 `127.0.0.1:8081`에서 띄우고(`com.dongseon.caddy`), 이 Mac에서 이미 돌고 있는 Cloudflare Tunnel 연결기를 같이 씁니다. Cloudflare 대시보드에 `DONGSEON_DOMAIN` → `http://localhost:8081` published route를 하나 추가합니다. 연결기는 대시보드 경로를 따르므로 jipsa 코드에는 dongseon 정보를 넣지 않습니다. (처음 계획은 jipsa Caddyfile에 site block을 추가하는 방식이었으나, 두 레포가 엉키지 않도록 바꿨습니다.)
- `dongseon serve`는 launchd로 상시 실행(`com.dongseon.serve`)하고, 일일 잡은 `com.dongseon.daily`입니다. jipsa `scripts/launchd.sh`를 이식합니다.
- 여행 중 Mac이 잠들거나 꺼지면 앱이 끊깁니다. README에 출발 전 점검 항목(잠자기 방지, 정전 후 자동 시작, 휴대폰 데이터망으로 원격 접속 테스트)을 적습니다.
- 활성 여행의 일정(순서, 계획 시각, 라벨, 메모, 길찾기 딥링크), 체크리스트, 예약 정보는 service worker와 IndexedDB에 캐시해서 연결이 끊겨도 읽을 수 있게 합니다. Google 영업시간·이동시간·지도 타일은 담지 않습니다 (6절). basic auth 뒤에서 service worker가 정상 동작하는지 원격 도메인으로 확인합니다.
- 일정은 ICS(휴대폰 캘린더), 인쇄용 HTML, 날짜별 Google Maps 경로 URL 목록으로 내보낼 수 있습니다.
- 여행 중에는 Google 지도 앱을 쓰므로(2026-11-05 사용자 결정), 계획은 dongseon에서 하고 출발 직전에 **Google 내 지도용 CSV**로 내보냅니다. 날짜마다 CSV 하나(순서, 시각, 라벨, 현지 이름, 동네, 메모)를 zip으로 받아 내 지도에 레이어로 가져오면, 내 지도가 이름으로 위치를 찾습니다. Google 좌표는 파일에 넣지 않습니다(6절). Google 지도 계정과의 자동 동기화는 공개 API가 없어 하지 않습니다.
- Google Maps JS 브라우저 키는 HTTP referrer를 `http://localhost:5174/*`와 원격 도메인으로 제한합니다. 서버 키는 API 제한만 겁니다.

---

## 16. 프로세스 모델과 CLI

jipsa와 달리 검색, 자동완성, 일정 풀기, 편집은 사용자와 바로 주고받아야 하므로 API 서버에서 처리합니다. 오래 걸리거나 대량으로 외부 호출을 하는 작업(Takeout 해석, 확정 행렬, AI 조사, daily)은 CLI 잡으로 돌리고, 설정·각 화면의 버튼은 jipsa처럼 파일 잠금을 건 백그라운드 CLI 잡을 띄웁니다.

```text
uv run --no-sync dongseon trip create --city tokyo --start YYYY-MM-DD --end YYYY-MM-DD --title "..."
uv run --no-sync dongseon places import-takeout <csv...> --trip <id>
uv run --no-sync dongseon places resolve [--trip <id>]
uv run --no-sync dongseon matrix build --trip <id> [--exact]
uv run --no-sync dongseon stays score --trip <id>
uv run --no-sync dongseon plan solve --trip <id>
uv run --no-sync dongseon plan review --trip <id>        # AI
uv run --no-sync dongseon hours refresh --trip <id>      # Google, D-7부터
uv run --no-sync dongseon hours research --trip <id>     # AI 웹 조사, 연휴 기간 핀
uv run --no-sync dongseon research food --trip <id>      # AI 웹 조사
uv run --no-sync dongseon weather refresh
uv run --no-sync dongseon fx refresh
uv run --no-sync dongseon usage                          # SKU별 이번 달 Google 사용량
uv run --no-sync dongseon daily
uv run --no-sync dongseon serve
```

`daily`는 활성 여행의 D-14부터 종료일까지만 영업시간·날씨·행렬 재계산을 하고, 그 밖에는 환율만 갱신합니다. 각 단계는 별도 프로세스로 돌고 하나가 실패해도 다음으로 넘어갑니다. 자주 쓰는 명령은 Make target과 `make help`에 등록합니다.

---

## 17. 백엔드 API

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/health` | 상태, 마지막 daily 시각 |
| GET/POST/PATCH | `/api/trips`, `/api/trips/{id}` | 여행 |
| GET | `/api/places/autocomplete`, `/api/places/search` | Google 검색 (사용량 계측) |
| POST | `/api/places/resolve-url` | 공유 URL을 place 후보로 |
| POST | `/api/trips/{id}/import/takeout` | CSV 업로드 후 백그라운드 해석 잡 |
| GET/POST/PATCH/DELETE | `/api/trips/{id}/pins` | 핀 |
| GET | `/api/places/{id}/details` | Google 상세(그때 조회, 저장 안 함)와 날짜별 영업 병합 결과 |
| GET/POST | `/api/trips/{id}/stays`, `/api/trips/{id}/stays/score` | 숙소 후보, 동네 점수 |
| GET/POST | `/api/trips/{id}/flights` | 항공 후보와 평가 |
| POST | `/api/trips/{id}/parse-booking` | 예약 메일 파싱 (AI) |
| POST | `/api/trips/{id}/itineraries/solve` | 초안 생성 (잠금 반영) |
| GET/PATCH | `/api/itineraries/{id}` | 일정 조회와 편집 |
| POST | `/api/itineraries/{id}/review` | AI 검토 제안 생성 |
| POST | `/api/suggestions/{id}/accept`, `/api/suggestions/{id}/reject` | 제안 처리 (재solve와 검증 포함) |
| GET | `/api/itineraries/{id}/export.ics`, `/api/itineraries/{id}/print` | 내보내기 |
| GET | `/api/trips/{id}/today` | 오늘 화면 |
| GET | `/api/usage`, `/api/settings/status` | 사용량, 키 설정 여부 |
| POST | `/api/jobs/{name}` | 백그라운드 CLI 잡 (파일 잠금) |

요청·응답은 pydantic 모델이고, 프론트 타입은 `make gen-types`로 생성해 커밋합니다.

---

## 18. 마일스톤

출발 2주 전까지 M5를 끝내는 것이 목표입니다. 숙소를 고르는 데 M2가 필요하므로 M1과 M2를 먼저 빠르게 끝냅니다. 각 마일스톤 끝에 `make lint`와 `make test`를 통과시키고, 바뀐 점과 확인 방법을 보고한 뒤 확인을 받고 넘어갑니다.

| # | 내용 | 완료 기준 |
|---|---|---|
| M0 | jipsa 패턴 스캐폴드(0절 표), 포트 8100/8101/5174, `/api/health`, React 앱, rules, CI, `docs/google-terms.md`, `api_usage` 계측 골격 | `make dev`로 두 서버가 뜨고 health가 보임. 사용자가 약관 요약을 확인 |
| M1 | 여행과 장소: trips, Places 검색·자동완성, URL 붙여넣기, 핀 CRUD, Google 지도와 리스트 (모바일) | 검색이나 링크로 추가한 장소가 지도에 찍히고 우선순위·체류시간을 편집할 수 있음 |
| M2 | 숙소와 항공: 이동시간 행렬(근사, transit), 동네 점수, 숙소 후보 비교, 항공 후보 입력과 평가 | 휴대폰에서 핀 기준 동네 순위와 숙소·항공 후보 비교를 볼 수 있음 |
| M2.5 | 자동 후보 찾기 (2026-11-05 사용자 요청으로 추가): claude_cli 이식, 가볼 곳·맛집 AI 추천(`places_research`), 상위 동네 호텔 AI 추천(`stay_research`), 수락·거절 흐름, 항공권·에어비앤비·부킹닷컴 검색 링크, `scout` 잡. 항공·호텔 자동 가격 수집은 `docs/travel-data-sources.md` 검토 후 결정 | 버튼 한 번으로 출처가 붙은 추천이 쌓이고, 수락하면 핀·숙소 후보가 됨 |
| M2.6 | 실시간 가격 (2026-11-05 사용자 요청): Ignav 왕복 운임(인천 출발 직항, 1시간당 비용 순 추천), 楽天トラベル 빈방(상위 동네 역 반경 1km), 날짜별 최저가 기록, 후보로 추가, `prices`·`daily` 잡과 launchd `com.dongseon.daily` | 매일 아침 운임·빈방이 갱신되고 화면에서 바로 후보로 넣을 수 있음 |
| M3 | (M3a: 영업시간·연휴, OR-Tools solver(날짜별 복사본 + 하루 분량 균형), 경고, 버전 저장, 타임라인·날짜별 지도·길찾기 / M3b: 편집·잠금·다시 맞추기, 버전 비교, Google 도보 확인) 일정: 날짜별 영업 시간창, OR-Tools solver, validator, 타임라인·날짜별 지도, 드래그·잠금·다시 맞추기, 버전, Google Maps 딥링크 | 5일 일정 초안이 경고와 함께 나오고 편집 후 다시 맞추기가 동작 |
| M4 | AI: plan_review, rain_plan, hours_research, stay_area_notes, booking_parse (claude_cli·맛집 조사·수락 흐름은 M2.5에서 먼저 함) | AI 제안이 재solve와 검증을 거쳐 diff로 보이고 수락하면 새 버전이 생김 |
| M5 | 여행 모드: 오늘 화면, 날씨·환율, D-7 영업시간 갱신, `daily`와 launchd, `serve` 상시 실행, 원격 접속, PWA 오프라인, ICS·인쇄 내보내기, 체크리스트 | 휴대폰 데이터망으로 원격 도메인에서 오늘 일정과 길찾기가 열리고, 비행기 모드에서도 일정을 읽을 수 있음 |
| M6 | (선택) Google Takeout "저장됨" 가져오기(2026-11-05 사용자 요청으로 M1에서 이동), 여행 중 지출 기록, 여행 후 회고(실제 방문 체크, 체류시간 보정), 항공·숙소 가격 adapter, 다른 도시 config | 사용자와 범위를 합의한 뒤 |

---

## 19. Claude Code 작업 원칙

- jipsa CLAUDE.md의 운영 원칙을 그대로 따릅니다. 마일스톤 단위로 진행하고, 비자명한 변경은 계획부터 승인받고, 범위 밖 기능은 제안만 하고, 외부 API는 실제 응답 fixture부터 만들고, 키가 없으면 멈추고 요청하고, 의존성은 추가 전에 확인합니다.
- Google 응답 fixture는 저장 전에 집, 숙소 같은 개인 관련 좌표·주소를 가짜 값으로 바꿉니다.
- 테스트에서 실제 외부 호출은 하지 않습니다 (respx + fixture). solver 테스트는 작은 합성 행렬로 만듭니다.
- 여권번호, 생년월일, 결제 정보는 저장하지 않습니다. 예약번호는 로컬 DB에만 둡니다.
- 커밋, 브랜치, PR 규칙은 jipsa와 같습니다 (`[TAG] summary`, `<TAG>-<description>` 브랜치).
- 코드, 주석, 커밋은 영어로, UI와 CLI 도움말은 한국어로 씁니다.
- 영업시간, 연휴, 요금, 무료 한도처럼 바뀌는 사실은 코드에 넣지 않고 config나 출처가 붙은 조사 결과로만 다룹니다.
- 일정 화면의 시각은 모두 추정이므로 영업 정보의 출처와 확인일을 함께 보여줍니다.

---

## 20. 사용자가 준비할 것

`.env.example`

```text
# Google Maps Platform (Cloud 프로젝트와 결제 계정 필요)
# 서버 키. API 제한: Places API (New), Routes API
GOOGLE_MAPS_SERVER_KEY=
# 브라우저 키. API 제한: Maps JavaScript API. HTTP referrer 제한: localhost:5174, 원격 도메인
VITE_GOOGLE_MAPS_JS_KEY=
VITE_GOOGLE_MAP_ID=
# 무료 한도 대비 경고·차단 비율
GOOGLE_FREE_TIER_WARN_RATIO=0.8
GOOGLE_FREE_TIER_STOP_RATIO=1.0

# LLM (headless Claude Code, 사용자 구독). jipsa와 같은 방식
LLM_MODEL=
LLM_DAILY_TOKEN_LIMIT=

# Paths (relative paths resolve from the repo root)
DATABASE_PATH=data/dongseon.db
PROFILE_PATH=config/profile.yaml

# Ports
DONGSEON_PORT=8100
DONGSEON_DEV_PORT=8101
```

원격 접속 값(`DONGSEON_DOMAIN`, `DONGSEON_AUTH_USER`, `DONGSEON_AUTH_HASH`, `DONGSEON_PROXY_PORT=8081`)도 dongseon `.env`에 둡니다.

`config/profile.example.yaml` (예시 값)

```yaml
travelers:
  - label: 나
  - label: 동행
home_airports: [ICN, GMP]
pace: normal
day_windows:
  relaxed: ["10:00", "20:00"]
  normal: ["09:00", "21:00"]
  packed: ["08:00", "22:00"]
meal_windows:
  lunch: ["11:30", "13:30"]
  dinner: ["18:00", "20:30"]
buffers_min:
  departure_airport: 120
  arrival_immigration: 60
  transfer: 10
priority_weights: {must: 100, want: 10, maybe: 1}
walking:
  max_walk_min_per_leg: 15
food:
  likes: []
  avoid: []
```

`config/cities/tokyo.yaml` (뼈대)

```yaml
key: tokyo
name: 도쿄
country: JP
timezone: Asia/Tokyo
currency: JPY
airports:
  - {code: HND, query: "Haneda Airport"}
  - {code: NRT, query: "Narita International Airport"}
stay_areas:
  - {label: 신주쿠, query: "Shinjuku Station"}
  - {label: 시부야, query: "Shibuya Station"}
  - {label: 긴자, query: "Ginza Station"}
  - {label: 도쿄역·니혼바시, query: "Tokyo Station"}
  - {label: 우에노, query: "Ueno Station"}
  - {label: 아사쿠사, query: "Asakusa Station"}
  - {label: 이케부쿠로, query: "Ikebukuro Station"}
approx_speed_kmh: null   # 근사 행렬용. transit 표본으로 보정한 뒤 채움
holiday_periods: []      # 12절 초안을 출처 확인 후 채움
```

그 밖에 준비할 것

- Google Cloud 프로젝트 생성, 결제 계정 연결, Places API (New)·Routes API·Maps JavaScript API 사용 설정, 키 2개와 Map ID 발급, quota 상한과 예산 알림
- Google Maps 앱에 여행용 리스트를 만들어 가고 싶은 곳을 저장해두고, Takeout에서 "저장됨"만 골라 내보내기
- `config/profile.yaml` 작성

---

## 21. 열린 질문 (사용자 결정 필요)

- 여행 날짜와 출발 공항 (인천 / 김포)
- 숙소를 한 곳으로 고정할지, 중간에 옮길지
- 기본 일정 강도 (relaxed / normal / packed)
- 동행자도 핀을 추가할지 (같은 basic auth로 같은 화면을 쓰면 됨)
- 레포 공개 여부 (공개라면 개인 정보 규칙을 jipsa와 똑같이 적용)
