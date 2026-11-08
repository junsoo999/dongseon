<p align="center">
    <img src="frontend/public/icon.svg" width="96" alt="dongseon icon">
</p>

<h3 align="center">
가고 싶은 곳을 모아 날짜별 동선으로 짜 주는 개인 여행 계획 앱
</h3>

<p align="center">
| <a href="./CONTRIBUTING.md"><b>Contributing</b></a> | <a href="./CLAUDE.md"><b>Agent Guide</b></a> | <a href="./docs/PLAN.md"><b>Plan</b></a> |
</p>

---

`dongseon`(동선)은 한 가구가 집 Mac에서 띄워 쓰고, 여행 중에는 휴대폰으로 접속하는 여행 계획 앱입니다. 가고 싶은 곳(핀)을 모으고, 핀 위치를 기준으로 숙소 동네와 항공편 후보를 비교하고, 영업시간·휴무·이동시간을 지키는 날짜별 동선을 만듭니다. 첫 사용처는 연말 도쿄 여행입니다.

> 일정의 시각은 모두 추정입니다. 영업 정보는 출처와 확인일을 함께 보여 주며, 연휴 기간에는 직접 확인이 필요합니다.

## ✨ 기능 (계획)

- **장소**: Google 검색·자동완성, 공유 URL 붙여넣기, 우선순위(must / want / maybe)와 체류시간
- **숙소**: 핀까지의 가중 평균 이동시간으로 동네 순위, 후보 숙소 비교
- **항공**: 후보별 현지 가용 시간과 총비용 비교 (검색은 Google Flights 등에서 직접, 공항별 시간대로 입력)
- **일정**: OR-Tools로 영업시간·예약·식사 시간을 지키는 초안, 경고 배지, 드래그·잠금·다시 맞추기, 버전 비교
- **AI 추천**: headless Claude Code가 가볼 곳·맛집·호텔을 웹에서 조사해 출처와 함께 추천 (수락하면 핀·숙소 후보), 이후 일정 검토·비 오는 날 대체안·연휴 영업 조사
- **실시간 가격**: 매일 아침 Ignav 왕복 운임(현지 1시간당 비용 순 추천)과 楽天トラベル 빈방을 가져와 바로 후보로 추가
- **검색 링크**: 항공권(Google, 네이버)·에어비앤비·부킹닷컴 검색을 여행 날짜·인원·상위 동네가 채워진 채로 열기
- **오늘**: 지금과 다음 일정, Google Maps 길찾기 버튼, 날씨, 환율 계산기, 오프라인 읽기
- **준비**: 체크리스트(기본 항목 템플릿), 확정한 항공·숙소·예약 시각 모음, Google 내 지도용 CSV·캘린더(ICS)·인쇄용 내보내기, AI가 찾고 Google 무료 검색으로 확인하는 현지 이름(내 지도가 이름으로 장소를 찾음)

진행 상황은 아래 로드맵을 보세요.

## 🧭 설계 원칙

- **개인정보는 저장소 밖에**: 여행 날짜, 동행자, 예약 정보는 로컬 DB에만, 선호는 `config/profile.yaml`(gitignore)에만 둡니다.
- **약관 먼저**: 외부 서비스는 약관을 확인한 뒤 붙입니다. Google 약관 요약은 [`docs/google-terms.md`](./docs/google-terms.md)에 있습니다.
- **바뀌는 사실은 코드 밖에**: 영업시간, 연휴, 요금, 무료 한도는 출처가 붙은 config나 조사 결과로만 다룹니다.
- **시간 계산은 코드가**: 동선과 제약 검사는 solver와 validator가 하고, LLM은 제안과 설명만 합니다.

## 🚀 시작하기

### 1. 준비물

- macOS, [uv](https://docs.astral.sh/uv/), Node 24+, [pnpm](https://pnpm.io/)
- [Claude Code](https://claude.com/claude-code) (로그인된 상태, M4부터)
- Google Cloud 프로젝트 (아래 "Google Maps Platform 설정", M1부터)

### 2. 설치와 실행

```bash
make install    # uv sync + pre-commit + pnpm install + .env / profile.yaml 복사
make dev        # http://localhost:5174 (같은 네트워크의 휴대폰은 http://<맥 IP>:5174)
```

설정 확인은 `uv run --no-sync dongseon info`, 이번 달 Google 사용량은 `make usage`로 봅니다.

| 용도 | 포트 |
|---|---|
| 상시 앱 (`serve`, launchd) | 8100 |
| 개발 백엔드 (`make dev`) | 8101 |
| Vite 개발 서버 | 5174 |

jipsa(8000 / 8001 / 5173)와 동시에 띄울 수 있습니다.

## 📱 어디서든 접속하기

dongseon은 `127.0.0.1:8100`에서만 받습니다. 바깥에서 들어오는 길(Cloudflare Tunnel, 비밀번호 확인, 앱별 주소 연결)은 여러 앱이 함께 쓰는 별도의 edge 레포가 맡고, dongseon은 그 구성을 모릅니다.

1. `make launchd-install JOB=serve`로 상시 앱을 실행합니다 (로그 `data/logs/serve.log`).
2. edge 쪽에 dongseon 주소를 `127.0.0.1:8100`으로 연결하는 항목을 추가합니다.
3. Google 브라우저 키의 HTTP referrer 제한에 `https://dongseon.<도메인>/*`를 추가합니다.

코드를 업데이트한 뒤에는 `make app-restart`로 다시 빌드하고 재시작합니다.

### ✈️ 출발 전 점검

여행 중에는 휴대폰이 집 Mac에 접속합니다. Mac이 잠들거나 꺼지면 앱도 끊기므로 출발 전에 확인합니다.

1. **잠자기 끄기**: 시스템 설정 → 에너지(또는 배터리 → 옵션)에서 "디스플레이가 꺼져 있을 때 자동으로 잠자지 않기"를 켭니다. 터미널에서는 `sudo pmset -c sleep 0`이고, `pmset -g`의 `sleep`이 0이면 됩니다.
2. **정전 후 자동 시작**: 같은 화면의 "정전 후 자동으로 시작"을 켭니다 (`sudo pmset -a autorestart 1`). launchd 작업은 사용자가 로그인해야 돌기 때문에 자동 로그인도 필요합니다. FileVault를 켜 두면 재시작 후 잠금 화면에서 멈추므로, 이때는 정전이 나면 앱이 다시 뜨지 않는다는 점을 감안합니다.
3. **상시 실행 확인**: `make launchd-status`에서 `serve`와 `daily`가 모두 실행 중인지 확인합니다.
4. **휴대폰 데이터망으로 접속**: 와이파이를 끄고 원격 주소를 열어 오늘 탭과 길찾기가 열리는지 확인합니다.
5. **오프라인 저장**: 휴대폰에서 앱을 한 번 열면 활성 일정, 체크리스트, 예약 정보가 휴대폰에 저장됩니다. 비행기 모드로 바꾼 뒤 다시 열어 오늘·준비 탭이 읽히는지 확인합니다. 영업시간, 이동시간, 지도는 저장하지 않습니다.
6. **내보내기**: 준비 탭의 "현지 이름"에서 AI로 채우기 → 확인된 것 모두 적용을 먼저 하면 내 지도가 장소를 더 정확히 찾습니다. 그다음 준비 탭에서 Google 내 지도용 CSV(날짜별 zip)를 받아 [내 지도](https://www.google.com/maps/d/)에 레이어로 가져오고, 필요하면 캘린더(ICS)도 휴대폰에 넣습니다. 일정을 바꾼 뒤에는 다시 내보냅니다.

준비 탭의 "기본 항목 채우기"에도 같은 점검 항목이 들어 있습니다.

## 🗺️ Google Maps Platform 설정

1. Google Cloud 프로젝트를 만들고 결제 계정을 연결합니다. 개인 사용량은 대부분 무료 한도 안이지만 결제 계정이 있어야 API를 쓸 수 있습니다.
2. **Places API (New)**, **Routes API**, **Maps JavaScript API**를 사용 설정합니다.
3. 키를 두 개 만듭니다.
   - 서버 키 → `.env`의 `GOOGLE_MAPS_SERVER_KEY`. API 제한: Places API (New), Routes API
   - 브라우저 키 → `VITE_GOOGLE_MAPS_JS_KEY`. API 제한: Maps JavaScript API, HTTP referrer 제한: `http://localhost:5174/*`와 원격 도메인
4. **Map Management**에서 Map ID를 만들어 `VITE_GOOGLE_MAP_ID`에 넣습니다 (Advanced Marker에 필요).
5. 과금 사고를 두 겹으로 막습니다.
   - Cloud Console **APIs & Services → 각 API → Quotas**에서 일일 요청 상한을 낮게 걸고, **Billing → Budgets & alerts**에서 소액 예산 알림을 만듭니다.
   - 앱은 SKU별 월간 호출 수를 세서 무료 한도(`config/defaults.yaml`)의 80%에서 경고, 100%에서 호출을 막습니다 (`GOOGLE_FREE_TIER_WARN_RATIO`, `GOOGLE_FREE_TIER_STOP_RATIO`).

## 🧰 Make 타깃

| 타깃 | 설명 |
|---|---|
| `make install` | 개발 환경 설치 (`PYTHON_VERSION=3.12\|3.13`) |
| `make dev` | 백엔드 + 프론트엔드 개발 서버 |
| `make lint` / `make fmt` | pre-commit 전체 실행 / 자동 포맷 |
| `make test` | pytest + Vitest (`TEST_MODE=all\|backend\|frontend`, `COVERAGE=1`) |
| `make gen-types` | OpenAPI → `frontend/src/api/schema.d.ts` |
| `make db-upgrade` | DB 마이그레이션 적용 |
| `make usage` | 이번 달 Google SKU별 사용량과 무료 한도 |
| `make prices` / `make scout` / `make daily` | 실시간 가격 / AI 추천 / 매일 작업 전체 (가격, 추천, 날씨, 출발 전 영업시간 재검사·비 오는 날 대안; 매일 자동은 `make launchd-install JOB=daily`) |
| `make serve` | 프론트엔드를 빌드해 API와 한 포트로 실행 |
| `make launchd-install` / `launchd-status` / `launchd-uninstall` | 상시 실행 관리 (`JOB=serve\|daily`) |
| `make app-restart` | 상시 앱 재빌드 + 재시작 |
| `make clean` | 캐시와 빌드 산출물 정리 |

## 🛠 기술 스택

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2, Alembic (SQLite), Typer, httpx, OR-Tools (M3)
- **Frontend**: Vite, React 19, TypeScript, TanStack Query, React Router, Tailwind CSS 4, Google Maps JavaScript API
- **품질 검증**: uv, ruff, pyright, pytest + respx, Vitest, oxlint, Prettier, pre-commit, GitHub Actions

## 🗺️ 로드맵

| 단계 | 내용 | 상태 |
|---|---|---|
| M0 | 뼈대, health, 규칙·CI, Google 약관 요약, 사용량 계측, 원격 접속 | 완료 |
| M1 | 여행과 장소 (검색, 지도 링크, 핀, 지도) | 완료 |
| M2 | 숙소 동네 점수, 숙소·항공 후보 비교 | 완료 |
| M2.5 | AI 자동 후보 찾기(가볼 곳·맛집·호텔), 항공·숙소 검색 링크 | 검토 중 |
| M2.6 | 실시간 가격: Ignav 항공 운임, 楽天トラベル 빈방, 매일 자동 갱신 | 검토 중 |
| M3 | 일정 solver, validator, 편집·다시 맞추기 | 완료 |
| M4 | AI 검토·조사·예약 메일 파싱 | 완료 |
| M5 | 오늘 화면, 날씨, D-7 영업시간 재검사, 오프라인, 내보내기 | 완료 |
| M5+ | 현지 이름 AI 채우기, 공항 근처 장소를 공항 가는 날 동선에 배치 | 검토 중 |

## 📄 라이선스

개인 프로젝트이며 아직 라이선스를 지정하지 않았습니다.
