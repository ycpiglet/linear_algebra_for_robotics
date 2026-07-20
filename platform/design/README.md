# 디자인·출판 운영 백로그

이 디렉터리는 디자인 시스템, 설명 아티팩트, 저장소 식별자 이전, 품질 CI의 **미완료
작업 상태와 실행 순서**만 관리한다. 새로운 콘텐츠·디자인 규범을 만들지 않는다.

문서 간 우선순위의 단일 원본은 `AUTHORING_MANUAL.md` §0.1이다. 이 README는 별도의
권위 순서를 만들지 않는다. 관심사별 실행 근거는 다음 소유 문서에서 찾는다.

| 관심사 | 소유 문서 |
|---|---|
| 사용자 요구·콘텐츠·근거·완료 기준 | `AUTHORING_MANUAL.md` |
| 승인된 시각·접근성 계약과 렌더 표본 | `design-system.qmd` |
| 자산 책임과 변경 원칙 | `assets/README.md` |
| 교정 이슈·이벤트·규칙 승격 운영 | `EDITING_SYSTEM_PLAN.md` |

백로그 제안이 기존 계약과 다르면 작업을 중단하고 결정 항목으로 되돌린다. 승인된 규칙은
해당 권위 문서와 저장소 소유 test·script·CI로 승격한다.

## 파일 구조

```text
platform/design/
├── README.md
└── work-items/
    ├── PUB-001.yml
    ├── PUB-002.yml
    └── ...
```

각 작업은 별도 YAML 파일이다. 여러 에이전트가 하나의 큰 Markdown 표에서 상태 셀을 동시에
고치는 충돌을 피하기 위해 중앙 상태표를 두지 않는다. 현재 목록은 다음 명령으로 생성한다.

```bash
.tools/uv/uv run python platform/scripts/design_backlog.py list
.tools/uv/uv run python platform/scripts/design_backlog.py check
```

`make validate`도 같은 검사를 실행한다. 스키마는
`platform/schemas/design-work-item.schema.json`이 소유한다.

## 역할과 스킬 라우팅

| 역할 | 책임 |
|---|---|
| `publishing-ops-steward` | 백로그, 권위 충돌, merge train, 독점 잠금 |
| `release-engineer` | 저장소명·CI·Pages·배포와 rollback |
| `design-system-steward` | 폰트·토큰·컴포넌트·출력 adapter |
| `artifact-editor` | 표·그림·코드·알고리즘 migration |
| `math-domain-reviewer` | 데이터·수식·단위·알고리즘 의미 독립 검증 |
| `render-qa` | Web/PDF/EPUB·접근성·시각 독립 검증 |

- 공통 폰트·토큰·컴포넌트·출력·CI 계약은 `$govern-publishing-design-system`을 사용한다.
- 개별 표·차트·코드·알고리즘·그림은 `$polish-explanatory-artifacts`를 사용한다.
- 스킬은 CI 의존성이 아니다. 승인된 기계 판정 규칙만 저장소 script·test로 옮긴다.
- 에이전트 이름이나 기억은 운영 자산이 아니다. 결과는 work item evidence, PR, test로 남긴다.

## 상태 전이

```text
planned → ready → in_progress → in_review → done
                 ↘ blocked
decision → in_review → done | cancelled
planned/ready → cancelled | superseded
done → rolled_back
```

- `decision`: 감독자 결정이나 외부 상태 확인 전에는 구현하지 않는다. 결정 기록을 검토·병합한
  뒤 `done`으로 닫아야 이를 의존하는 구현 항목을 `ready`로 바꿀 수 있다.
- `ready`: 의존 작업이 `done`이고 범위·잠금·검증·rollback·완료 기준이 채워졌다.
- `in_progress`: 담당 역할과 브랜치가 정해지고 독점 잠금을 획득했다.
- `in_review`: source 검사는 통과했으며 PR과 독립 검증을 기다린다.
- `done`: main 병합뿐 아니라 요구된 post-merge·배포 검증까지 통과했다.
- `blocked`: blocker와 재검토 조건을 기록하며 독점 잠금은 계속 보유한다.
- `cancelled`: `status_reason`에 취소 근거를 남긴다.
- `superseded`: `status_reason`과 `superseded_by`에 대체 근거를 남긴다.
- `rolled_back`: `evidence.revert_ref`, `evidence.follow_up`, 사후 검증을 남긴다.

`ready` 이후의 `change_paths.read/write/generated` 값은 설명문이 아니라 공백 없는 저장소 상대
경로 또는 glob이어야 한다. 후보 소비자나 미정 범위는 `planned`에서만 허용하며, 시작 전에
구체적인 경로로 바꾼다. `in_review`는 PR·CI·last-known-good 증거가 필요하고, 렌더 계약이
있다면 검토할 산출물도 연결한다. `done`은 post-merge 증거까지 있어야 의존 작업을 해제한다.

ID는 재사용하거나 삭제하지 않는다. 취소·대체·원복된 항목도 이력으로 보존한다.

## 브랜치·worktree·잠금 규칙

1. `main`에서 직접 편집하지 않고 최신 `origin/main`에서 작업 브랜치를 만든다.
2. 의존 PR이 병합되기 전에 그 PR 브랜치에서 다음 브랜치를 파생하지 않는다.
3. 이 환경의 에이전트는 기본 작업 디렉터리를 공유하므로 보조 에이전트는 기본적으로 읽기 전용이다.
4. 병렬 구현은 에이전트마다 별도 `git worktree`와 명시적인 `workdir`을 배정한다.
5. 같은 worktree에서 두 에이전트가 checkout, formatter, generator, source edit를 함께 실행하지 않는다.
6. 같은 `exclusive_locks` 값을 가진 `in_progress`/`in_review`/`blocked` 항목은 동시에 존재할 수 없다.
7. 병렬 PR의 경로가 겹치면 후속 PR은 최신 main에서 다시 적용하고 전체 required gate를 재실행한다.
8. 활성 `branch`는 `main`이나 `refs/heads/`가 아닌 유효한 짧은 Git branch 이름으로 기록한다.
9. PR은 merge commit으로 병합하고 한 PR에는 공통 계약 하나 또는 migration batch 하나만 둔다.

주요 독점 잠금은 다음과 같다.

| 잠금 | 대표 경로 |
|---|---|
| `ci-control-plane` | `Makefile`, `.github/workflows/**`, output verifier, tool config |
| `design-foundations` | tokens, theme, fonts, `design-system.qmd`, 출력 adapter |
| `identity-cutover` | Quarto URL, review/editorial UI, saved path migration, 운영 문서 |
| `artifact-contract` | inventory·manifest·공통 plotting/ID 계약 |
| `backlog-registry` | 이 README, schema, checker, 공통 상태 규칙 |

`_site/`, `_review/`, `_book/`, `_proof/`, `_freeze/`, `.quarto/`, `platform/generated/`는
생성·검증 대상이며 source로 직접 편집하지 않는다.

## merge train

```text
PUB-001 → PUB-002 ─┬─ PUB-004 → PUB-005
PUB-003 (decision) ┘
PUB-002 → PUB-006 ─────────────────────────┐
PUB-005 → PUB-007 → PUB-008 ─────────────┼─ PUB-009
                                         │
PUB-009 ───────────┬─ PUB-010             │
                   ├─ PUB-011             │  별도 worktree에서 병렬 가능
                   ├─ PUB-012             │
                   └─ PUB-013             │
PUB-010 + PUB-011 + PUB-012 + PUB-013 → PUB-014 → PUB-015
```

- `PUB-002`의 read-only 안전망 전에는 외부 rename이나 foundation migration을 시작하지 않는다.
- `PUB-006`은 저장소 소유 inventory·manifest 기반만 만들므로 `PUB-004`와 병렬 준비할 수 있다.
- 저장소 개명을 먼저 끝내야 새 URL에서 typography visual baseline을 한 번만 만든다.
- 공통 디자인 계약과 rendered gate가 병합되기 전에는 대량 consumer migration을 시작하지 않는다.

열린 PR, branch ruleset, editorial queue, main·배포 SHA처럼 시간에 따라 바뀌는 기준선은
README에 고정하지 않는다. 해당 work item의 날짜 있는 evidence에 기록하고 cutover 직전에
다시 확인한다. 저장소 cutover 전에는 모든 열린 PR을 병합·종결하거나 carry-over 결정을
기록한다.

## 전환·기반 변경 동결 창

- 저장소 개명 cutover 중에는 다른 PR merge와 배포를 중단한다.
- cutover 전에 editorial digest 대기 항목과 `editorial/batch` PR을 확인하고 필요한 경우 중지한다.
- 폰트·token 수직 조각이 진행되는 동안 다른 foundation PR을 열지 않는다.
- 아티팩트 batch 대상 `.qmd`는 일반 원고 편집·자동 교정과 동시에 수정하지 않는다.
- visual baseline은 명시적 update PR에서만 바꾸며 CI가 자동 승인하지 않는다.
- 동결 전에 last-known-good main SHA, workflow run, `gh-pages` SHA를 evidence에 기록한다.
- rollback은 배포 산출물 직접 수정이 아니라 원인 merge commit revert와 동일 파이프라인 재배포가 원칙이다.

## 검증 계층

| 단계 | 내용 |
|---|---|
| T0 · 모든 PR | `make test`, `make lint`, `git diff --check` |
| T1 · 영향 출력 | web/review/book/proof, asset generation, accessibility/visual 중 관련 항목 |
| T2 · 단계 종료 | `make all`, 대표 Web/PDF/EPUB 수동 검수, last-known-good 기록 |

| 변경 | T1 필수 |
|---|---|
| Python·schema·metadata·glossary | reader output이 달라질 때 `make web` |
| 개념·경로·story·lab QMD | `make web`; book/proof 수록 시 해당 출력 |
| 공통 SCSS·token·JS | `make web`; review runtime이면 `make review`; cross-format이면 `make book` |
| EPUB CSS·fonts·book/Typst 설정 | `make book`; 공통 web 영향 시 `make web` |
| proof 전용 원고·설정 | `make proof`; 공통 탐색에 노출되면 `make web` |
| review script·editorial desk·repo URL | `make review`; cutover이면 web와 외부 smoke |
| 수치 함수·lab plot | 관련 pytest, `make web`; 수록 출력 추가 |
| workflow | Actions 문법 검사와 draft PR에서 quality/deploy 분리 확인 |

## PR 증거 계약

각 PR은 다음을 기록한다.

- work item ID, 의존 PR, 독점 잠금, 실제 변경 파일
- 독자 문제 또는 시스템 불일치와 canonical source
- 바꾸지 않는 데이터·수식·알고리즘·reading order
- affected consumers, compatibility/version 분류, migration·rollback
- 실행한 T0/T1/T2와 실제 렌더 출력
- intended visual diff와 baseline 승인
- 예외의 owner, 제거 조건·검토일
- 도메인 검증과 렌더 QA 결과

`looks cleaner`만으로는 공통 계약 변경의 근거가 되지 않는다.

## 임시 감사 기준선

아래 수치는 `PUB-002`와 `PUB-006`에서 저장소 소유 검사로 재생성하기 전까지 CI의 고정
임계값으로 사용하지 않는다.

| 항목 | 2026-07-20 감사 결과 |
|---|---:|
| Markdown 표 / 안정 표 ID | 108 / 0 |
| 알고리즘 카드 / 안정 ID | 10 / 0 |
| SVG / figure ID | 12 / 8 |
| Mermaid / label | 3 / 1 |
| SVG / 확인된 생성기 | 12 / 4 |
| lab plot cell | 6 |
| canonical CSS token / 미정의 local token | 56 / 0 |
| raw literal 후보 | 208 |

legacy를 즉시 전부 실패시키지 않는다. 새 위반을 막는 no-new-debt gate를 먼저 적용하고,
검증된 batch마다 기준선을 낮춘다. raw literal은 token 대상과 허용 geometry·media-query 값을
분류하며 무조건 0을 목표로 삼지 않는다.
