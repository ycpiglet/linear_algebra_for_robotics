# Robotics Math Atlas

로봇공학에 필요한 선형대수, 확률, 신호와 시스템, 제어, 추정, 최적화,
Lie 이론을 **개념 그래프**로 연결하는 한국어 교재 프로젝트입니다.

이 프로젝트는 한 방향으로만 읽는 책과 다릅니다. 각 개념은 안정적인 ID와
깊이별 선수지식(`직관`, `적용`, `유도`, `증명`)을 가지며, 웹에서는 검색,
backlink, 주변 지식 그래프, 학습 진도와 복습 큐를 제공합니다. 같은 원고에서
HTML, PDF, EPUB, 별도 증명권을 생성합니다.

현재 대표 원고에는 자코비안(Jacobian)·최대우도추정(MLE)·칼만 필터(Kalman filter)의
직관·유도·제품 사례·시각화·장별 참고문헌이 포함됩니다. 또한 PID·최소제곱 학습 경로,
몬테카를로→중요도표집(IS)→순차중요도표집(SIS)→재표집→부트스트랩 입자 필터,
마르코프 연쇄→상세균형→메트로폴리스–헤이스팅스의 개념·유도·증명 경로가 있습니다. 전체 장기 범위는
[`curriculum.qmd`](curriculum.qmd), 파트별 프로그램은 [`software.qmd`](software.qmd)에
정리되어 있습니다.

## 빠른 시작

개발 환경의 기준 진입점은 Windows의 `dev.ps1`, macOS·Linux의 `dev`입니다.
처음 한 번만 Git과 Python 3.9 이상(Python 3.12 권장)이 필요하며, Quarto·Typst·uv·
Node와 검사 도구는 검증된 SHA-256으로 저장소 안의 `.tools/`에 자동 설치됩니다.

Windows PowerShell:

```powershell
pwsh -NoProfile -File .\dev.ps1 test
pwsh -NoProfile -File .\dev.ps1 lint
pwsh -NoProfile -File .\dev.ps1 web
```

Python이 없다면 먼저 다음 명령으로 설치합니다.

```powershell
winget install Python.Python.3.12
```

macOS·Linux:

```bash
./dev test
./dev lint
./dev web
```

각 명령은 필요한 bootstrap·동기화·검증을 의존 순서대로 한 번만 실행하므로
`bootstrap`과 `sync`를 따로 먼저 실행할 필요가 없습니다. macOS·Linux의 기존
`make test`, `make lint`, `make web`도 같은 공통 runner에 위임되는 호환 명령입니다.

웹 미리보기는 Windows에서 `pwsh -NoProfile -File .\dev.ps1 preview`,
macOS·Linux에서 `./dev preview`로 실행합니다.

로컬 도구와 Python 환경은 저장소 안의 `.tools/`, `.venv/`에 격리되며 Git에
올라가지 않습니다. 운영체제나 checkout 경로가 달라지면 `.venv/`는 자동으로
다시 만들어집니다. 다른 PC로 이 폴더들을 복사하지 말고, Git으로 같은 branch를
clone/fetch한 뒤 해당 OS의 진입점을 실행하면 됩니다.

환경과 설치 경로를 확인하려면 다음 명령을 사용합니다.

```powershell
pwsh -NoProfile -File .\dev.ps1 doctor
```

## 주요 명령

- `validate`: 개념·증명 메타데이터·링크·선수 그래프와 한영 용어 원본을 검사하고 중앙 용어집 재생성
- `test`: 플랫폼 및 수학 코드 테스트
- `web`: 위키형 HTML 지식 아틀라스 생성
- `book`: 선형 독서용 PDF/EPUB 교재 생성
- `proof`: Particle Filter·MCMC 증명권 생성
- `all`: 검사와 모든 출력 생성

출력은 각각 `_site/`, `_book/`, `_proof/`에 만들어집니다. `book`은 HTML, PDF,
EPUB을 같은 원고에서 생성합니다. 위 target 이름은 `dev.ps1`, `dev`, `make`에서
동일합니다.

## 저장소 구조

- `content/concepts/`: 안정 ID와 깊이별 선수를 가진 개념 원고
- `content/paths/`: 내용을 복제하지 않는 목표별 학습 경로
- `content/proofs/`: 가정·의존 정리·증명 수준을 명시한 proof graph
- `content/stories/`: 출처를 붙인 역사·비하인드 읽을거리
- `courseware/labs/`: 실행 가능한 Quarto/Python 실험
- `courseware/src/`: 테스트 가능한 수치실험 함수
- `platform/`: JSON Schema, validator, backlink/graph compiler, Quarto filter
- `assets/`: 반응형 테마, 접근 가능한 그래프와 로컬 진도 UI
- `assets/styles/_tokens.scss`: 색·타이포그래피·간격·모션의 단일 token 원본
- `assets/styles/_content-blocks.scss`: 핵심·수식·가정·오해·역사 등 재사용 학습 블록
- `platform/glossary/glossary.yml`: 한글·영어·약어·정의·연관 개념의 단일 용어 원본
- `platform/templates/concept-template.qmd`: 결론 우선형 새 장 저작 템플릿

## 저작·디자인 기준

사용자 요구·현재 집필 범위·근거 정책·완료 기준은 최상위
[`AUTHORING_MANUAL.md`](AUTHORING_MANUAL.md)를 먼저 따릅니다. 새 장은
[`platform/templates/concept-template.qmd`](platform/templates/concept-template.qmd)에서
시작합니다. 실제 렌더링 표본과 사용 규칙은 [`design-system.qmd`](design-system.qmd), 공식
근거와 선택 이유는 [`ui-ux-research.qmd`](ui-ux-research.qmd), 자산 책임은
[`assets/README.md`](assets/README.md)에 정리되어 있습니다. 현재 대표 원고는
[`자코비안`](content/concepts/robotics/jacobian.qmd),
[`최대우도추정`](content/concepts/statistics/maximum-likelihood-estimation.qmd),
[`칼만 필터`](content/concepts/estimation/kalman-filter.qmd) 세 장입니다.

용어를 추가할 때는 `platform/glossary/glossary.yml`만 수정한 뒤 `make validate`를 실행합니다.
생성 파일을 직접 고치지 않습니다. 본문 안의 짧은 용어 정의는 `.atlas-term`으로 표시하면
웹에서 focus/hover 주석과 페이지별 용어집으로 점진적으로 확장됩니다.

## 콘텐츠 원칙

각 페이지는 결론과 공학적 의미를 먼저 제시한 뒤 직관, 정의, 가정, 유도,
엄밀한 설명, 증명, 반례, 응용 순으로 깊어집니다. 역사·인물·공학 실패 사례는
출처를 붙인 짧은 읽을거리로 제공합니다. 수치실험은 증명을 대신하지 않으며,
모든 알고리즘은 적용 가정과 실패 조건을 함께 설명합니다.
