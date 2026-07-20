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
저장소 Actions 기본 권한은 `read`로 유지하고, trusted digest가 batch PR을 만들 수 있도록
`can_approve_pull_request_reviews=true`를 설정한다. PR write를 선언한 workflow는 default branch의
`editorial-digest.yml` 하나이며, 이 workflow는 PR 승인 명령을 실행하지 않는다.
`editorial/batch`에는 direct update 제한 ruleset을 적용한다. 개인 소유 저장소의 내장
`GITHUB_TOKEN`은 eligible ruleset bypass App이 아니므로, 적용·검증 이후의 `push-auth` checkout만
`EDITORIAL_BATCH_SSH_KEY` Actions secret과 짝을 이루는 write deploy key
`editorial-batch-actions-only`만 사용한다. ruleset의 유일한 bypass actor는 `DeployKey`이며
정상 운영 때는 이 전용 key 하나만 둔다(아래의 동결된 회전 창에서는 candidate key 하나를
일시 허용한다). dispatch 직전 workflow가 live ref를
방금 push한 SHA와 다시 비교하지만, ruleset이 이 비교 사이의 사람 push 경합을 구조적으로
줄이는 1차 경계다. `push-auth` checkout은 full history를 받아야 한다. shallow clone이면 원격
batch SHA가 새 SHA의 조상이어도 로컬 Git이 fast-forward임을 증명하지 못해 `fetch first`로
non-force push를 거부한다.

source push 뒤 PR 생성·quality dispatch가 실패하면 즉시 freeze·drain하되 batch ref를 되돌리지
않는다. 재시도는 현재 이벤트 원장의 `links.source`, 동일한 before/after, 현재 소스의 after 문구,
git의 `Issue: #N` 트레일러를 모두 확인해 이전 `applied` 결과와 커밋을 복구한다. 이 조건을
만족하지 못한 `not-found`는 자동 반영 성공으로 간주하지 않는다.

key 회전은 활성 secret을 덮어쓰지 않는 blue/green 방식으로 한다. workflow는
`EDITORIAL_BATCH_KEY_SLOT=primary`(기본값)의 `EDITORIAL_BATCH_SSH_KEY`와 `next`의
`EDITORIAL_BATCH_SSH_KEY_NEXT`를 번갈아 사용한다.

1. freeze·drain하고 현재 slot, `editorial/batch`의 `before_sha`, pending 이슈, 두 key의 ID·
   `verified`·`read_only`·`last_used`를 기록한다.
2. 비활성 slot에 새 write deploy key와 secret을 추가한다. 활성 secret/key는 그대로 두고,
   candidate의 `verified=true`, `read_only=false`를 먼저 확인한다.
3. 평문을 실제로 한 번 바꾸는 적용 가능한 통제 proposal을 준비해 이슈 번호와 기대 diff를
   기록하고 `EDITORIAL_BATCH_KEY_SLOT`을 candidate slot으로 바꾼다.
4. freeze를 `false`로 일시 해제하고 default-branch `repository_dispatch`를 보낸다. 실패하면
   즉시 `true`로 재동결·drain하고 slot을 기존 값으로 돌린 뒤 candidate만 철회한다.
5. 성공은 proposal의 `Issue: #<번호>` 트레일러가 있는 새 커밋, `pushed=true`,
   `before_sha != head_sha`, 실제 push 로그, 원격 batch ref와 `head_sha` 일치, candidate key의
   `last_used`가 회전 뒤 시각으로 갱신된 경우에만 인정한다. pending 0건이나 적용 불가 proposal의
   성공 run, credential checkout 도달만으로는 인정하지 않는다.
6. 성공 뒤 다시 freeze·drain하고 이전 key와 이전 slot의 secret만 제거한다. 마지막으로
   freeze를 `false`로 바꾸고 zero-pending dispatch를 확인한다.

이 절차는 실패 시 secret 값을 읽어 복원할 수 없는 GitHub의 특성 때문에 활성 secret을 직접
overwrite하지 않는다. 개인 PAT나 계정 SSH key도 이 용도로 재사용하지 않는다.

workflow를 구 `GITHUB_TOKEN` push 방식으로 rollback하는 일은 merge commit revert만으로 끝나지
않는다. 먼저 freeze·drain하고 main·batch ref, 열린 batch PR, pending 이슈와 외부 control-plane
상태를 기록한다. 그다음 `editorial/batch`의 deploy-key-only ruleset을 비활성화하고 보호된 main의
rollback PR로 workflow를 되돌린다. 적용 가능한 통제 proposal을 준비한 다음 freeze를 일시
해제해 이전 source push→batch PR→read-only quality dispatch 경로와 실제 ref 변경을 검증한다.
실패하면 즉시 재동결·drain한다. 성공한 경우에도 다시 동결·drain한 뒤 전용 deploy key·secret과
비활성 ruleset을 철회하고, 마지막으로 freeze를 해제해 zero-pending dispatch를 확인한다.
ruleset을 둔 채 workflow만 revert하거나, 동결 상태의 skipped run을 복귀 증거로 삼으면 rollback
완료로 판정하지 않는다.
