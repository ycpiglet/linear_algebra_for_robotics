# 프로젝트 안내 (세션 인수인계)

한국어 로봇수학 교재 **Robotics Math Atlas**. Quarto(.qmd) 단일 원고에서 웹·EPUB·PDF를
렌더하며, GitHub 기반 협업 교정 시스템이 가동 중이다. 최종 갱신: 2026-07-19.

## 핵심 문서

- `EDITING_SYSTEM_PLAN.md` — 교정 시스템 기획서 + 각 Phase 구현 노트(수동 설정 절차 포함)
- `EDITING_UX_RESEARCH.md`, `EDITING_UX_RESEARCH_2.md` — 근거 조사(검증 표기 규약 있음)
- `AUTHORING_MANUAL.md` — 집필 규범(원고 작업 전 필독), `future-scope.qmd` — 예정 노드 55개 계약
- `platform/editorial/README.md` — 주체 구분 규약(커밋 트레일러·라벨), 이벤트 원장 규칙

## 빌드·검증

- `make web`(독자용 _site) / `make review`(교정용 _review — **프로필 순서는 반드시 `review,web`**,
  먼저 나열된 프로필의 스칼라가 우선하므로 뒤집으면 _site를 덮어씀) / `make test` / `make lint`
- 배포: main 푸시 → `.github/workflows/publish-web.yml` → gh-pages (루트=독자용, `/review/`=교정용,
  PR은 `/preview/pr-N/`). Pages 활성화 완료, 라이브: https://ycpiglet.github.io/linear_algebra_for_robotics/

## 교정 시스템 상태 (Phase 0~3 구현 완료, 가동 중)

드래그 → [수정 제안] → `editorial` 라벨 이슈(기계가독 `editorial-anchor` JSON 동봉) →
매일 06:00 KST `editorial-digest.yml`이 수거 → `platform/scripts/editorial.py`가 평문 구간만
자동 반영(교정 1건=커밋 1개, §6 이벤트 레코드 동승) → `editorial/batch` 브랜치 → 배치 PR.

- 배치 PR은 **merge commit으로만 병합**(squash 금지), 특정 교정 기각은 해당 커밋 revert 후 병합
- 처리된 이슈는 `bridged` 라벨(재수거 방지). 라벨 5종 생성 완료(`setup-labels`)
- 2026-07-19 전체 루프 실증 완료: 이슈 #5 → 자동 반영 → 배치 PR #6 병합·이슈 확정 종결
- 남은 수동 설정: hypothes.is **비공개 그룹 생성·편집자 초대**만 남음
- 워크플로우 수동 트리거는 API 토큰 권한 밖(403) — Actions 탭에서 사람이 Run workflow 하거나 예약 실행 대기

## 품질 이력 (2026-07-19 평가·개선 완료)

- **UX 평가 → 6건 수정 병합**(PR #8): 터치 선택 지원(selectionchange), 이슈 URL 7,500자
  상한 축약, 다이얼로그 포커스 트랩, 다크 모드 팔레트, 데스크 페이지네이션(300건 수거+더 보기),
  코드 블록 안내문
- **디자인 평가 → 6건 수정 병합**(PR #9): 히어로 링크 대비 2.28→8.56:1, 웹폰트 안전망
  ('Atlas Sans KR' @font-face — 로컬 서체 없을 때만 로드), 독서 도구막대 절제(긴 본문 한정
  +기본 접힘), 리뷰 링크 충돌 해소, 다크 브레드크럼 11.17:1, 제목 2.8rem·수식 배경 제거
- 통과 확인된 회귀 기준: 링크 복사(앵커+프래그먼트), 내비 선택 제외, 중복 문단 `-2`,
  60회 반복 무누수, XSS 이스케이프, Esc·백드롭 닫기, 디자인 계약 테스트 13건
- 첫 교정 루프 실증: 이슈 #5 → 배치 PR #6 병합 → 이벤트 원장 1건 적재(2026-07-19-kalman-filter-i5)

## 원고 진행 (커리큘럼 `curriculum.qmd` A~M 대비)

- 완비: K(MC·SMC·PF, 증명 5편) · L(MCMC 대부분, 증명 4편) · G(확률 기초+MLE 플래그십)
- 플래그십 3장: 자코비안(2001줄)·MLE(1985줄)·칼만 필터(1191줄). 중형 장 14, 지원 장 5,
  경로 5, 실습 5
- 미착수: C(수치선대) · D(행렬미적분) · **E(SO(3)/SE(3) — 최대 공백)** · F(최적화) ·
  H(신호) · I2(고전제어) · J1/J3(센서·퓨전) · M(ML/RL) + `future-scope.qmd` 예정 노드 55개
- 다음 집필 우선순위 합의안: ① E축 회전·자세 표현 ② B5/B6 고유값·SVD ③ EKF(두 플래그십 교차점)
  ④ L축 마무리(Gibbs·수렴 진단)

## 작업 규약

- 개발 브랜치에서 작업 후 PR, **병합은 merge commit**. 병합된 PR 브랜치는 origin/main에서 재시작
- 에이전트 커밋은 `Actor:`/`Issue:` 트레일러, PR에 `actor:agent` 라벨
- 원고 수정은 `AUTHORING_MANUAL.md` 준수 + `make test`(30건)·`editorial.py lint` 통과 필수
- 이벤트 원장(`platform/editorial/events/`)은 append 전용 — 직접 편집 금지, `ingest` 명령 사용
