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
- PR은 `actor:agent`·`actor:supervisor`·`actor:editor` 중 정확히 한 라벨을 가진다.
  `actor:agent` PR이 새로 도입하는 모든 커밋(동기화 merge 포함)은 Git이 실제 trailer로
  파싱하는 `Actor: agent`를 정확히 하나 가져야 한다. literal `\\n` 문자열은 줄바꿈이 아니다.
- 보호된 `main`의 merge commit은 PR 주체와 같은 `Actor` trailer를 하나 갖는다. 사람의
  branch commit은 author identity를 사용하므로 `Actor` trailer를 강제하지 않는다.
- `publish-web`의 provenance gate는 네트워크 조회 없이 Actions event payload의 PR 라벨과
  checked-out full Git graph만 검사한다. PR 라벨·base 변경도 quality check를 다시 실행한다.
- `37289c06a3c7752ef09d5348f4bc7b5e15bae291`까지는 immutable trusted-through
  cutline이다. 그 이전의 비정규 trailer는 history를 재작성하지 않고 보존하되, PR·main
  first-parent integration·수동 dispatch가 새로 도입하는 전체 범위에는 같은 예외를 허용하지 않는다.
  main 검사 범위는 매 push마다 이 cutline부터 다시 계산하므로 앞선 실패는 다음 push로
  덮이지 않는다. 사고 복구 후 cutline 갱신은 별도 control-plane 변경으로 명시적으로 심사한다.
- `trusted-provenance` 상태는 default branch의 base-side 코드만 실행해 PR test-merge SHA에
  게시한다. token은 contents read·pull-requests read·statuses write로 제한하고, PR head는 read-only Git
  object로만 fetch하며 checkout·import·build하지 않는다. verifier는 Python isolated mode로
  실행해 PR이 추가한 sibling module·환경 변수의 import shadowing도 막는다. workflow와 verifier는
  bootstrap 이후 PUB-017의 외부 supervisor 신뢰 결박이 끝날 때까지 모든 역할에 대해 동결한다.
- `GITHUB_TOKEN`으로 만든 PR·label 이벤트는 다른 workflow run을 시작하지 않는다. 따라서 editorial
  digest는 PR 생성 뒤 live `actor:agent` label과 원격 batch head를 확인하고 default-branch 전용
  `repository_dispatch`에 exact PR 번호와 head SHA를 전달한다. controller는 live PR API의 head와
  payload를 다시 대조하고 base/head/test-merge 두 부모를 검증한 뒤에만 같은 status context를 게시한다.
- `actor:supervisor` 라벨은 역할 주장이지 인증된 사람 신원은 아니다. 같은 GitHub 계정을 쓰는
  agent와 사람을 라벨만으로 구분하지 않는다. bootstrap 이후 `.github/workflows/**`, verifier,
  CODEOWNERS 후보 위치, write credential을 사용하는 editorial controller 의존성은 모든 역할에
  대해 동결하고, PUB-017에서 agent 전용 GitHub App/봇 identity와 별도 사람
  CODEOWNER 승인(또는 동등한 외부 trust root)을 결박한 뒤에만 해제한다. 그전에는
  `trusted-provenance`를 ruleset required context로 승격하지 않는다. YAML anchor·alias나 중첩 권한
  표현을 텍스트 검사로 판별하지 않고 파일 경계 자체를 차단한다.
- agent/editorial branch의 수동 quality dispatch는 `trusted_main` exact SHA를 입력으로 받고,
  그 SHA가 현재 main first-parent history에 있으며 dispatch head의 조상일 때만 전체 범위를 검사한다.

PUB-017의 최초 trust bootstrap은 현재 동결을 일반 라벨 예외로 풀지 않는다. 다음 순서를 하나의
동결 창에서 수행한다.

1. editorial을 freeze·drain하고 ruleset 전체 JSON, main SHA, 열린 PR을 보존한다.
2. agent 작업에서 사용할 최소 권한 GitHub App/봇 identity를 사람 계정과 분리하고, 사람 admin
   credential이 agent 실행 환경에 없음을 확인한다.
3. PUB-017 branch 생성 전에 ruleset에 approving review 1건, stale approval 무효화, 마지막 push와
   다른 주체의 승인을 먼저 요구한다. `trusted-provenance`는 아직 required로 추가하지 않는다.
4. 봇 identity가 CODEOWNERS와 verifier transition만 담은 PUB-017 PR을 만들고, 별도 사람 owner가
   exact head diff와 ruleset snapshot을 검토해 승인한다. 이 PR의 `source-contract`는 PR 버전
   verifier를 실행한다. base-side 구 verifier의 failure는 이 전환 동안 informational로 남는다.
5. reviewed head SHA를 `--match-head-commit`으로 고정해 병합하고 즉시 새 main push를 확인한다.
   CODEOWNER review를 활성화한 뒤 compliant canary에서 기존 두 checks와 provenance status의
   동시 충족을 두 번 확인해야만 `trusted-provenance`를 required context로 승격한다.
6. 어느 단계든 실패하면 required provenance를 켜지 않고 ruleset의 review 변경만 역패치한다.
   봇 identity·실패 SHA·승인·ruleset snapshot은 보존하고 control-plane 동결을 유지한다.

즉 PUB-017의 PR-side verifier 변경은 독립적인 사람 승인 규칙이 먼저 생긴 뒤에만 허용되는
one-shot transition이다. `source-contract`를 제거하거나 self-asserted `actor:supervisor` 라벨만으로
동결을 해제하지 않는다.

**병합과 사고 복구:** 최종 merge commit은 PR 검사 전에 존재하지 않으므로 UI 기본 병합이나
auto-merge에 맡기지 않는다. 역할에 맞는 trailer를 stdin 파일로 전달하는 통제 명령만 사용한다.

```bash
printf '%s\n' 'Actor: agent' | gh pr merge <PR> --repo <owner/repo> --merge \
  --match-head-commit '<reviewed head SHA>' --subject '<merge subject>' --body-file -
```

감독자·편집자 PR은 각각 `Actor: supervisor`, `Actor: editor`로 바꾼다. literal `\n`을 인자로
조립하지 않는다. 병합 직후 main push의 provenance run이 성공하고 merge commit의 파싱된
trailer가 PR 라벨 역할과 일치하는지 확인하기 전에는 다음 PR을 병합하지 않는다.
`--match-head-commit`에는 required checks와 리뷰를 마친 exact head SHA를 넣어 검토 뒤 push와의
경쟁을 차단한다.

main에 잘못된 integration이 이미 들어가면 단순 revert merge만으로 복구되지 않는다. sticky
검사는 잘못된 commit도 계속 보므로 다음 순서를 따른다.

1. editorial을 freeze·drain하고 invalid SHA, push event/run, main ruleset 전체 JSON을 보존한다.
2. ruleset에서 `trusted-provenance` context만 동시 변경 방지 절차로 잠시 제거한다. 기존
   `source-contract`와 `publication-build`, merge-only 규칙은 유지한다.
3. 인증된 supervisor 승인 경로의 recovery PR 하나에서 잘못된 내용을 revert하고
   `TRUSTED_THROUGH`를 해당 incident SHA로 명시적으로 전진시킨다. source-contract가 새 cutline
   이후 history와 recovery commit을 검증하게 한다.
4. 위 통제 명령으로 `Actor: supervisor` merge commit을 만든 뒤 main push 성공을 확인한다.
5. `trusted-provenance`를 integration ID까지 동일하게 복원하고 compliant canary의 test-merge
   status, 세 required checks, 새 commit 재실행을 확인한 뒤 freeze를 해제한다.

이 절차는 history를 지우는 rollback이 아니라 incident boundary를 감사 가능한 새 trust
cutline으로 승인하는 복구다. ruleset snapshot·invalid/recovery SHA·승인 근거를 work-item evidence에 남긴다.

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
source push, main 대상 batch PR 보장, trusted quality·provenance dispatch가 모두 성공한 뒤에만 붙는다.
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
해제해 이전 source push→batch PR→trusted quality·provenance dispatch 경로와 실제 ref 변경을 검증한다.
실패하면 즉시 재동결·drain한다. 성공한 경우에도 다시 동결·drain한 뒤 전용 deploy key·secret과
비활성 ruleset을 철회하고, 마지막으로 freeze를 해제해 zero-pending dispatch를 확인한다.
ruleset을 둔 채 workflow만 revert하거나, 동결 상태의 skipped run을 복귀 증거로 삼으면 rollback
완료로 판정하지 않는다.
