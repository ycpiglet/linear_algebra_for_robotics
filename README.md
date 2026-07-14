# Linear Algebra for Robotics

선형대수학을 단순한 행렬 계산이 아니라 **로봇공학의 기하·수치계산·미분·최적화를 연결하는 공통 언어**로 학습하기 위한 교재 및 실습 저장소입니다.

이 프로젝트는 다음 다섯 영역을 하나의 흐름으로 통합합니다.

1. 선형대수학의 구조와 기하
2. 수치선형대수학
3. 행렬미분과 자동미분
4. 최적화
5. Lie 군·Lie 대수와 로봇 기하학

## 학습 순서

```text
선형대수
  → 수치선형대수
  → 행렬미분·자동미분
  → 최적화
  → Lie 군과 다양체 최적화
  → 로봇 운동학·상태추정·SLAM·궤적 최적화
```

최종적으로 다음과 같은 실제 로봇 문제를 수식의 의미부터 유도, 구현, 검증까지 수행하는 것을 목표로 합니다.

$$
\min_{T_1,\ldots,T_n\in SE(3)}
\sum_{(i,j)}
\left\|
\log\left(Z_{ij}^{-1}T_i^{-1}T_j\right)
\right\|_{\Omega_{ij}}^2
$$

이 식에는 선형대수, 희소 수치해법, Jacobian, 비선형 최소제곱, $SE(3)$, exponential/logarithm map이 모두 들어 있습니다.

## 문서 구성

| 문서 | 내용 |
|---|---|
| [`docs/00_master_plan.md`](docs/00_master_plan.md) | 전체 교재의 권·장·절 수준 상세 목차 |
| [`docs/01_course_syllabus.md`](docs/01_course_syllabus.md) | 76주 강의계획, 수업 방식, 평가, 프로젝트 |
| [`docs/02_chapter_authoring_template.md`](docs/02_chapter_authoring_template.md) | 각 단원의 공통 집필·강의·문제풀이 형식 |
| [`docs/03_visualization_and_tools.md`](docs/03_visualization_and_tools.md) | 수학 시각화 방법과 파트별 Python 도구 |
| [`notebooks/README.md`](notebooks/README.md) | 향후 실습 notebook 구성 원칙 |

## 권장 기본 환경

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

핵심 도구는 Python, JupyterLab, NumPy, SciPy, SymPy, Matplotlib, Plotly, ipywidgets, pytest입니다. 자동미분·볼록최적화·최적제어·Lie 군 파트의 추가 도구는 해당 시점에 별도 설치합니다.

## 학습 원칙

각 개념은 다음 순서로 다룹니다.

```text
문제 제기 → 역사·어원 → 기하학적 직관 → 엄밀한 정의
→ 유도·증명 → 예제·반례 → 알고리즘 → Python 실험
→ 수치오차 분석 → 로봇 실무 사례 → 연습문제
```

공식을 암기하는 것이 아니라 다음을 설명할 수 있는 수준을 목표로 합니다.

- 왜 그 식이 나오는가
- 어떤 가정에서 성립하는가
- 각 벡터·행렬의 공간과 차원은 무엇인가
- 수치적으로 어떻게 안정하게 계산하는가
- 구현이 맞는지 어떻게 검증하는가
- 실제 로봇 시스템의 어디에 사용되는가

## 현재 상태

- [x] 전체 교재·강의 아키텍처 설계
- [x] 시각화 및 소프트웨어 스택 설계
- [ ] 준비편 집필
- [ ] 제1권 선형대수학 집필
- [ ] 실습 notebook 및 테스트 추가
- [ ] 수치선형대수·행렬미분·최적화·Lie 군 순차 확장

첫 학습 단원은 **“행렬은 숫자표가 아니라 선형사상의 좌표 표현이다”**에서 시작합니다.
