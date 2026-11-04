## 1. PR 타입 (PR Type)

해당하는 모든 항목에 [x] 표시해주세요.

- [ ] feat: 새로운 기능 추가
- [ ] fix: 버그 수정
- [ ] docs: 문서 변경
- [ ] style: 코드 포맷팅
- [ ] refactor: 코드 리팩토링
- [ ] perf: 성능 개선
- [ ] test: 테스트 추가 또는 수정
- [ ] build: 빌드 시스템 또는 외부 종속성 변경
- [ ] ci: CI 설정 파일 및 스크립트 변경
- [ ] chore: 기타 변경 사항
- [ ] revert: 이전 커밋 되돌리기

## 2. 변경 사항 요약 (Summary of Changes)

- 이 PR에서 무엇이 바뀌었는지 1~3문장으로 설명해주세요.

## 3. 관련 마일스톤 (Milestone)

- 예: M1 여행과 장소

## 4. 변경 내용 상세 (Detailed Description of Changes)

- 어떤 문제를 해결했는지, 왜 이 방식을 택했는지
- 영향 범위: backend / frontend / planner / config / ci

## 5. 테스트 계획 (Test Plan)

- 실행한 명령과 결과 (예: `make lint`, `make test`, 화면 확인 스크린샷)

## 6. 리뷰어에게 (To Reviewers)

- [ ] `make lint`가 통과합니다.
- [ ] `make test`가 통과합니다.
- [ ] API 스키마를 바꿨다면 `make gen-types` 결과를 함께 커밋했습니다.
- [ ] 개인정보(여행 날짜, 동행자, 예약 정보, 집·숙소 위치)가 코드·fixture·커밋 메시지에 들어가지 않았습니다.
- [ ] 영업시간·연휴·요금·무료 한도를 코드에 하드코딩하지 않았습니다.
- [ ] Google 데이터는 `docs/google-terms.md`가 허용하는 범위에서만 다룹니다.
- [ ] 필요한 경우 README / CLAUDE.md / `.claude/rules/`를 갱신했습니다.
