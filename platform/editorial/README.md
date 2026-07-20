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

## 구조 변경 전 동결·drain

`EDITORIAL_FREEZE`는 새 job의 시작을 막는 repository variable이지 실행 중인 job과의
트랜잭션 잠금이 아니다. 저장소 개명·대량 이동 전에는 다음 순서를 지킨다.

1. `gh variable set EDITORIAL_FREEZE --body true --repo <owner/repo>`로 먼저 동결한다.
2. `editorial-digest.yml`의 `queued`·`in_progress` run을 모두 취소하고 terminal 상태가 될 때까지
   기다린다. 실행 중인 run이 0이 되기 전에는 구조 변경을 시작하지 않는다.
3. `editorial/batch` ref와 열린 main 대상 batch PR, pending editorial 이슈 수를 기록한다.
4. ref가 drain 직후 값에서 바뀌지 않았음을 다시 확인한 뒤 cutover를 시작한다.
5. 작업과 smoke test가 끝난 뒤 variable을 `false`로 바꾸고
   `gh api --method POST repos/<owner/repo>/dispatches -f event_type=editorial-digest`로
   default-branch 전용 `repository_dispatch`를 한 번 보내 정상 복귀를 검증한다.

privileged digest에는 임의 ref의 YAML을 실행할 수 있는 `workflow_dispatch`를 두지 않는다.
예약 실행과 `repository_dispatch`는 모두 default branch의 신뢰된 workflow 정의만 사용한다.

동결을 해제하기 전에 실패한 source push가 없는지 확인한다. 이슈의 댓글·`bridged` 라벨은
source push, main 대상 batch PR 보장, read-only quality dispatch가 모두 성공한 뒤에만 붙는다.
`editorial/batch`에는 direct update 제한 ruleset을 적용한다. 개인 소유 저장소의 내장
`GITHUB_TOKEN`은 eligible ruleset bypass App이 아니므로, bridge checkout은
`EDITORIAL_BATCH_SSH_KEY` Actions secret과 짝을 이루는 write deploy key
`editorial-batch-actions-only`만 사용한다. ruleset의 유일한 bypass actor는 `DeployKey`이며
저장소에는 이 전용 key 외 deploy key를 두지 않는다. dispatch 직전 workflow가 live ref를
방금 push한 SHA와 다시 비교하지만, ruleset이 이 비교 사이의 사람 push 경합을 구조적으로
줄이는 1차 경계다.

key를 교체할 때도 먼저 위의 freeze·drain 절차를 수행한다. 새 write deploy key와
`EDITORIAL_BATCH_SSH_KEY` secret을 같은 점검 창에서 교체하고, 기본 브랜치
`repository_dispatch` 복귀 검증이 성공한 뒤 이전 key를 제거한다. 개인 PAT나 계정 SSH key를
이 용도로 재사용하지 않는다.
