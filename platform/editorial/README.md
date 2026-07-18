# 편집 이벤트 기록

`events/YYYY-MM.jsonl`은 편집 이력의 1차 기록이다 (EDITING_SYSTEM_PLAN.md §6).

- **직접 편집 금지.** 적재는 도구로만 한다:
  `platform/scripts/editorial.py ingest --record <record.json>`
  (스키마: `platform/schemas/editorial-event.schema.json`)
- append 전용이다. 잘못 적재한 레코드도 지우지 않고 `status: superseded`
  레코드를 덧붙여 바로잡는다.
- `rejected`·`reverted`도 동급 기록이다 — 무엇을 거부했는가가 스타일
  프로파일(§7)의 원료다.

## 주체 구분 규약 (EDITING_SYSTEM_PLAN.md §Phase 1-5)

이력에서 사람·에이전트의 개입을 기계적으로 분리하기 위한 규약이다.

**커밋:**

- 에이전트(브리지 포함)가 만드는 커밋은 전용 author 서명을 쓴다:
  `editorial-bridge <editorial-bridge@users.noreply.github.com>`
- 에이전트 커밋은 트레일러를 붙인다: `Actor: agent`, 근거가 이슈면 `Issue: #N`
- 감독자·편집자의 직접 커밋은 본인 GitHub 계정 author를 그대로 쓴다
  (그 자체가 주체 기록이다).

**라벨** (`editorial.py setup-labels --repo <owner/repo>`로 일괄 생성):

| 라벨 | 용도 |
|---|---|
| `editorial` | 리뷰 패널이 만든 수정 제안 이슈 — 다이제스트 수거 대상 |
| `bridged` | 브리지가 처리함(자동 반영 또는 소스 위치 회신) — 재수거 방지 |
| `actor:agent` | 에이전트가 만든 PR |
| `actor:supervisor` | 감독자가 만든 PR |
| `actor:editor` | 외부 편집자가 만든 PR |

**조회 예시:** 에이전트 개입만 보기 — `git log --grep="^Actor: agent"`,
사람 커밋만 보기 — `git log --invert-grep --grep="^Actor: agent"`.
