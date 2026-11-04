# Contributing to dongseon

이 문서는 `dongseon`을 일관되고 안전하게 개발하기 위한 규칙입니다. 작업을 시작하기 전에 아래 지침을 확인해 주세요. 에이전트용 요약은 `CLAUDE.md`와 `.claude/rules/`에 있습니다.

---

## 🛠 권장 환경

- **언어**: Python 3.12, TypeScript
- **패키지 관리**: [uv](https://github.com/astral-sh/uv) (Python), pnpm (frontend)
- **품질 검증**: pre-commit (ruff, pyright, oxlint, prettier, tsc, actionlint, bashate, markdownlint)
- **에디터/에이전트**: Claude Code

초기 셋업:

```bash
make install    # uv sync + pre-commit install + pnpm install + .env / profile.yaml 복사
```

그 다음 `.env`에 API 키를, `config/profile.yaml`에 본인 값을 채웁니다. 두 파일은 커밋되지 않습니다.

---

## 📁 디렉토리 규칙

```text
dongseon/         # Python 패키지 (FastAPI API, Typer CLI, 동선 계산)
tests/unit_test/  # pytest
frontend/         # Vite + React + TypeScript
config/           # 공개 설정 (defaults, cities) + 개인 설정 profile.yaml (gitignore)
scripts/          # 설치·테스트 스크립트
```

- Python 프로젝트는 레포 루트의 `pyproject.toml` 하나만 둡니다.
- 자주 쓰는 명령은 `Makefile`에 등록하고 `make help`에 설명을 추가합니다.

---

## 🔒 개인정보 규칙

이 레포는 GitHub에 올라갑니다. 다음 내용은 **커밋되는 어떤 파일에도** 쓰지 않습니다.

- 실제 여행 날짜, 동행자, 예약 정보 (예약번호 포함)
- 집·숙소 주소와 좌표

선호 값은 `config/profile.yaml`과 `.env`에, 여행 날짜·동행자·예약은 로컬 DB에만 둡니다. 테스트와 예시는 `config/profile.example.yaml`의 가짜 값을 씁니다. 외부 API 응답을 fixture로 저장할 때도 개인 좌표·주소는 가짜 값으로 바꿉니다.

---

## 🌿 브랜치 네이밍 규칙

- **형식**: `<TAG>-<description>` (`<TAG>`는 아래 태그 목록에서 대문자, 설명은 소문자 kebab-case)
- **예시**:
  - `FEAT-takeout-import`
  - `FIX-year-end-hours-merge`
  - `DOCS-update-contribution-guide`

---

## ✍️ 커밋 메시지 컨벤션

### 제목 형식

`[TAG] <요약 내용>` (영문, 50자 이내, 명령형). 템플릿은 `.gitmessage.txt`이며 `make install`이 자동으로 등록합니다.

### 본문 규칙

- 제목과 본문 사이에 빈 줄을 둡니다.
- "어떻게"보다 **"무엇을"**, **"왜"** 바꿨는지 설명합니다.
- 명령형 어조를 씁니다. (예: "Add Takeout parser" (O), "Added Takeout parser" (X))

---

## 🚀 풀 리퀘스트 (PR) 절차

### 1. PR 제목 규칙

`[TAG] <요약 내용>` 형식을 따릅니다. 본문은 **영문**, 1–150자, 영숫자와 `` _-.,&*[]:/`<>=#+ ``만 허용합니다.

| 태그 | 의미 |
|---|---|
| `[FEAT]` | 새로운 기능 추가 |
| `[FIX]` | 버그 수정 |
| `[DOCS]` | 문서 변경 |
| `[STYLE]` | 코드 포맷팅 |
| `[REFACTOR]` | 동작 변화 없는 리팩토링 |
| `[PERF]` | 성능 개선 |
| `[TEST]` | 테스트 추가/수정 |
| `[BUILD]` | 빌드 시스템 또는 외부 종속성 변경 |
| `[CI]` | CI 설정 파일 및 스크립트 변경 |
| `[CHORE]` | 그 외 기타 변경 |
| `[REVERT]` | 이전 커밋 되돌리기 |
| `[HOTFIX]` | 긴급 수정 |
| `[BOT]` | 자동화 작업 |

예시: `[FEAT] Add Takeout saved-list import with place_id resolution`

### 2. PR 체크리스트

- [ ] `make lint`가 통과하는가?
- [ ] `make test`가 통과하는가?
- [ ] API 스키마를 바꿨다면 `make gen-types` 결과를 함께 커밋했는가?
- [ ] 개인정보가 코드·fixture·커밋 메시지에 들어가지 않았는가?
- [ ] 영업시간·연휴·요금·무료 한도를 코드에 하드코딩하지 않았는가?
- [ ] Google 데이터를 `docs/google-terms.md`가 허용하는 범위에서만 저장·캐시·표시·LLM 전송하는가?
- [ ] 필요한 경우 README / CLAUDE.md / `.claude/rules/`를 갱신했는가?

---

## 🔍 코드 리뷰 기준

- **단위 정확성**: 금액은 정수 `amount`와 `currency`, 시간 길이는 분 정수, 시각은 timezone-aware인가?
- **불확실성 표시**: 근사 이동시간, AI 조사, 미확인 영업시간에 그 사실이 표시되는가?
- **개인정보**: 추적되는 파일에 개인 값이 없는가?
- **타입 안정성**: 공개 API에 타입 힌트와 docstring이 있는가?
- **일관성**: 기존 모듈과 명명·구조가 일관되는가?

---

## 🤝 작업 방법 (Step-by-Step)

1. **환경 설정**: `make install`
2. **Branch Out**: 규칙에 맞는 이름으로 브랜치 생성
3. **구현**: `docs/PLAN.md`의 마일스톤 단위로 작업
4. **Local 검증**: `make lint && make test`
5. **Submit PR**: PR 템플릿을 채워 제출
