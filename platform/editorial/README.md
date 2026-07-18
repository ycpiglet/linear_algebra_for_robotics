# 편집 이벤트 기록

`events/YYYY-MM.jsonl`은 편집 이력의 1차 기록이다 (EDITING_SYSTEM_PLAN.md §6).

- **직접 편집 금지.** 적재는 도구로만 한다:
  `platform/scripts/editorial.py ingest --record <record.json>`
  (스키마: `platform/schemas/editorial-event.schema.json`)
- append 전용이다. 잘못 적재한 레코드도 지우지 않고 `status: superseded`
  레코드를 덧붙여 바로잡는다.
- `rejected`·`reverted`도 동급 기록이다 — 무엇을 거부했는가가 스타일
  프로파일(§7)의 원료다.
