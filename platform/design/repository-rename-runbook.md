# Repository rename compatibility and cutover runbook

이 문서는 `PUB-004`의 사전 호환 계약과 `PUB-005`에서 실행한 실제 cutover 절차를 분리한다.
2026-07-23에 canonical repository를 `ycpiglet/robotics-math-atlas`로 변경했다. 이전
`ycpiglet/linear_algebra_for_robotics` Git·web URL은 redirect 호환 경계로만 남기며 이전
이름을 재사용하지 않는다.

## 배포된 호환 계약

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

실제 rename과 같은 `PUB-005` 변경에서 아래 runtime 값을 한 번에 바꿨다.

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

실행 직전 `2026-07-23T13:39:12+09:00` 기준선은 repository ID `1300261697`, main
`84739ad38bcf5806d6cc32cb601e11c478de09ba`, `gh-pages`
`a6c88967fef0b9a8a0996c289922f12f3b1472b6`, Pages source `gh-pages:/`, custom domain 없음,
HTTPS 강제, webhook 0개, deploy key `editorial-batch-actions-only` 1개, active ruleset 3개였다.
PUB-007 draft PR #34는 branch를 보존한 채 종결했고 exact-head transition PR #38만 열어 두었다.
`EDITORIAL_FREEZE=true`, pending editorial issue와 active Actions run은 0, 목표 slug는 비어
있었다. 설치된 `ycpiglet-robotics-math-agent`의 permission은 현재 owner OAuth로 검증할 수
없어 미확인 residual risk로 남겼고 이 cutover에서 사용하지 않았다.

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

## 2026-07-23 실행 결과

- repository 이름은 한 번만 변경했고 ID `1300261697`과 node ID `R_kgDOTYBrQQ`가 유지됐다.
  old/new SSH URL은 같은 refs를 반환했으며 각각 shallow clone, `gh-pages` fetch, transition
  branch dry-run push에 성공했다. 이전 GitHub web URL은 새 repository로 HTTP 301 redirect한다.
- transition PR #38의 exact head
  `e3a5583b20704c9e38597069bc19e2449487bfc7`를 merge commit
  `48bacfe3b65736e1f56d147b861c8440d944b17a`로 병합했다. 새 `gh-pages`는
  `401affe625e4541b951f205e6ff2c46afbb292d2`다.
- main source run `29980163596`의 첫 attempt는 rename 전 절대경로가 박힌 main `.venv`
  cache ID `5853684331` 때문에 `pytest`를 spawn하지 못했다. source·workflow를 바꾸지 않고
  해당 ref의 cache ID 하나만 삭제해 새 workspace용 cache ID `5979470309`를 만들었고 같은
  run의 두 번째 attempt에서 source-contract와 publication-build가 성공했다. trusted deploy
  `29980481374`와 Pages build `29980522110`도 성공했다.
- canonical root와 `/review/`, reader/review Jacobian 표본은 HTTP 200이고
  `source-commit.txt`는 `48bacfe3b65736e1f56d147b861c8440d944b17a`다. old project Pages
  root와 `/review/`는 redirect 없이 HTTP 404다.
- 실제 브라우저에서 navbar·source·issue·GitHub.dev·editorial desk·history 링크가 새
  repository를 가리키고 Hypothesis client가 로드됨을 확인했다. old Pages prefix를 가진
  favorite, bookmark, last-read는 새 site 첫 load에서 prefix-neutral path로 변환됐고
  `migrations.savedPathsV1=true`가 기록됐다.
- old site에 먼저 배포한 root·Jacobian의 `DC.relation.ispartof`와 `DC.identifier` 쌍은
  new reader/review의 값과 byte-equal하다. 공개 Hypothesis API의 old URL, new URL,
  `urn:x-dc:` 조회 결과는 모두 annotation ID 0건이었다. private group export와 canary는
  존재하지 않아 그 계정 범위 보존을 증명하지 않았으며, 이 빈 shared corpus에서는
  deterministic fingerprint test, metadata equality, 실제 client load를 대체 증거로 사용했다.
- Pages source/environment, ruleset ID 3개, deploy key ID `157811443`, webhook 0개,
  Actions secret·variable 이름, branch 32개와 profile pin의 repository object가 rename 뒤에도
  보존됐다. freeze를 `false`로 해제한 뒤 editorial digest `29980668816`이 zero-pending으로
  성공했고 열린 editorial issue·PR·active Actions run은 모두 0이었다.

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

## 재현 가능한 현재 snapshot 명령

아래 명령은 읽기 전용이다. 결과의 secret 값은 수집하지 않는다.

```bash
gh api repos/ycpiglet/robotics-math-atlas \
  --jq '{id,full_name,default_branch,html_url,visibility,has_pages}'
gh api repos/ycpiglet/robotics-math-atlas/pages \
  --jq '{status,cname,html_url,build_type,source,https_enforced}'
gh api repos/ycpiglet/robotics-math-atlas/hooks \
  --jq 'map({id,name,active,events})'
gh api repos/ycpiglet/robotics-math-atlas/keys \
  --jq 'map({id,title,read_only,verified,created_at})'
gh api repos/ycpiglet/robotics-math-atlas/rulesets \
  --jq 'map({id,name,target,enforcement})'
gh pr list --repo ycpiglet/robotics-math-atlas --state open \
  --json number,headRefName,headRefOid,isDraft,url
git ls-remote origin refs/heads/main refs/heads/gh-pages
```
