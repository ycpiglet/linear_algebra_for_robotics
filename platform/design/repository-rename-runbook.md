# Repository rename compatibility and cutover runbook

이 문서는 `PUB-004`의 사전 호환 계약과 `PUB-005`에서만 실행할 실제 cutover 절차를 분리한다.
현재 이름은 `ycpiglet/linear_algebra_for_robotics`, 승인된 목표 이름은
`ycpiglet/robotics-math-atlas`다. 이 문서를 병합해도 repository·Pages·외부 설정은 바뀌지 않는다.

## 이미 배포할 수 있는 호환 계약

- 브라우저 저장 키는 `robotics-math-atlas.progress.v1`, export schema는 `1.0.0`으로 유지한다.
- `favorites`, `bookmarks`, `lastRead`의 key와 `url`만 project-prefix 없는 상대 경로로
  정규화한다. 예: 두 Pages prefix의 `/…/content/a.html`은 모두 `content/a.html`이 된다.
- old/new/이미 정규화된 항목이 충돌하면 `updatedAt`이 최신인 항목, 시간이 같으면 이미
  정규화된 항목을 유지한다. 외부 origin·malformed 값은 삭제하지 않고 링크만 비활성화한다.
- 내부 marker `migrations.savedPathsV1`은 export하지 않는다. 변환은 멱등이고 import 직후에도
  다시 적용되므로 old site를 거치지 않은 사용자의 new site 첫 방문도 처리한다.
- 각 HTML 문서는 source path 기반의 URL 독립
  `DC.identifier`(`urn:robotics-math-atlas:document:v1:…`)를 정확히 하나 가진다. reader,
  review, preview에서 같은 QMD는 같은 ID를 사용한다.
- `platform/scripts/editorial.py`는 선행 URL segment를 점진적으로 제거하므로 수정하지 않는다.
  old/new Pages fixture가 같은 QMD로 매핑되는지만 회귀 테스트한다.

## hard-coded identity inventory

실제 rename과 같은 `PUB-005` 변경에서 아래 runtime 값을 한 번에 바꾼다.

| 파일 | 현재 값의 역할 |
|---|---|
| `_quarto-web.yml` | repository source/issue action과 navbar GitHub 링크 |
| `assets/includes/review-scripts.html` | issue prefill, GitHub.dev, commit/history 링크의 `REPO` |
| `editorial-desk.qmd` | Issues·PR API 조회의 `REPO` |
| `CLAUDE.md` | 공개 Pages 안내 URL |
| `platform/tests/test_editorial.py` | cutover 뒤 canonical fixture |

다음 값은 바꾸지 않는다.

- 완료 work item의 과거 run·artifact·live URL은 감사 증거다.
- `platform/schemas/*.json`의 `https://linear-algebra-for-robotics.local/schemas/*` `$id`는
  JSON Schema resource identity다.
- Python distribution/import 이름 `robotics-math-atlas` / `robotics_math_atlas`, content ID,
  progress key와 export format은 repository URL과 독립이다.
- workflow의 `${{ github.repository }}`와 provenance의 `GITHUB_REPOSITORY`는 현재 identity를
  런타임에서 읽으므로 source 치환 대상이 아니다. rename 후 실제 실행은 반드시 smoke한다.

외부 inventory는 cutover 직전에 다시 수집한다.

- 모든 clone/worktree remote와 외부 문서·프로필·pinned link
- Pages source/environment, main·`gh-pages` SHA와 source/deploy run
- ruleset, required integration, Actions variables/secrets 이름(값은 기록하지 않음)
- deploy key, webhook 및 수신측 `repository.full_name` allowlist
- GitHub App installation/repository selection과 aliimbot 등 알림 연동
- Hypothesis group/export, 사용자 bookmark 안내

2026-07-23의 사전 관찰값은 repository ID `1300261697`, Pages source `gh-pages:/`, custom
domain 없음, HTTPS 강제, webhook 0개, deploy key `editorial-batch-actions-only` 1개, active
ruleset 3개, 열린 PR 0개다. 이는 cutover 기준선이 아니며 실행 직전에 새 snapshot으로 대체한다.
설치된 `ycpiglet-robotics-math-agent`의 현재 permission은 owner 확인 전까지 미확인 residual
risk이며 이 cutover에서 사용하지 않는다.

## PUB-005 시작 조건

다음 조건을 모두 만족하고 사용자가 실제 외부 변경을 별도로 확인해야 시작한다.

1. PUB-004가 old Pages에 배포되고 Web/review output verifier가 모두 통과한다.
2. Hypothesis group을 JSON export해 annotation ID와 page별 수를 보존한다.
3. old review page의 `DC.identifier`를 확인하고 canary annotation을 만든다.
4. 기존 annotation ID 집합과 URN 조회 결과를 비교한다. 메타 추가가 URL-only annotation을
   소급 결박한다고 가정하지 않으며 불일치하면 rename을 중단한다.
5. `EDITORIAL_FREEZE=true`, editorial digest의 queued/in-progress run 0, 열린 batch PR과
   pending editorial issue 수를 기록한다.
6. main 대상 열린 PR을 병합·종결하고 exact-head PUB-005 transition PR 하나만 예외로 둔다.
7. main·`gh-pages` SHA, source/deploy run, Pages 설정, ruleset, hooks, keys, App installation,
   remote 목록을 timestamp와 함께 저장한다.
8. 별도 사용자 확인 직전에 queue·ref·PR snapshot을 다시 읽어 drift가 없음을 확인한다.

## cutover 실행 순서

1. GitHub에서 repository 이름을 `robotics-math-atlas`로 한 번 변경하고 repository ID
   `1300261697`이 유지되는지 확인한다.
2. local/automation remote를 새 Git URL로 갱신한다. old URL과 new URL에서 clone/fetch를
   각각 smoke하고 push 권한은 `--dry-run`으로 먼저 확인한다.
3. 준비한 PUB-005 exact head를 merge commit으로 병합한다.
4. 새 main source build와 `gh-pages` deploy가 성공하고 Pages build가 `built`가 될 때까지
   기다린다.
5. 새 root·`/review/`, source, issue prefill, GitHub.dev, editorial desk, history 링크,
   저장한 favorite/bookmark/last-read를 smoke한다.
6. old Git repository/clone URL redirect의 실제 동작을 기록한다. old project Pages URL은
   redirect를 기대하지 않고 HTTP 결과만 기록한다.
7. old/new fixture의 `DC.identifier` byte equality와 Hypothesis annotation ID 집합을 다시
   비교한다.
8. 성공 후에만 freeze를 해제하고 새 repository 대상으로 editorial digest dispatch를 한 번
   실행해 zero-pending 또는 정상 batch 처리를 확인한다.

## 중단과 rollback

- rename 전 gate가 하나라도 실패하면 외부 상태를 바꾸지 않고 중단한다.
- repository 접근, main deploy, 새 root/review, source/issue link, saved path 또는 Hypothesis
  equivalence가 실패하면 freeze를 유지하고 snapshot을 보존한다.
- 공개 전이라도 이름 왕복은 자동 rollback이 아니다. GitHub의 Git URL redirect는 이전 이름을
  재사용하면 깨질 수 있고 project Pages redirect는 보장되지 않는다.
- rename 후에는 새 이름에서 last-known-good 산출물을 재배포하고 source를 forward-fix한다.
  원인 merge commit revert가 필요하면 같은 pipeline으로 새 site에 재배포한다.
- 성공 evidence는 main SHA, `gh-pages` SHA, source/deploy/Page build URL, smoke 결과,
  Hypothesis ID 비교, queue/freeze 결과를 포함한다. secret·token·private key 값은 남기지 않는다.

## 재현 가능한 snapshot 명령

아래 명령은 읽기 전용이다. 결과의 secret 값은 수집하지 않는다.

```bash
gh api repos/ycpiglet/linear_algebra_for_robotics \
  --jq '{id,full_name,default_branch,html_url,visibility,has_pages}'
gh api repos/ycpiglet/linear_algebra_for_robotics/pages \
  --jq '{status,cname,html_url,build_type,source,https_enforced}'
gh api repos/ycpiglet/linear_algebra_for_robotics/hooks \
  --jq 'map({id,name,active,events})'
gh api repos/ycpiglet/linear_algebra_for_robotics/keys \
  --jq 'map({id,title,read_only,verified,created_at})'
gh api repos/ycpiglet/linear_algebra_for_robotics/rulesets \
  --jq 'map({id,name,target,enforcement})'
gh pr list --repo ycpiglet/linear_algebra_for_robotics --state open \
  --json number,headRefName,headRefOid,isDraft,url
git ls-remote origin refs/heads/main refs/heads/gh-pages
```
