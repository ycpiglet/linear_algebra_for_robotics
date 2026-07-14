# 시각화 및 소프트웨어 도구 계획

## 1. 순수 선형대수도 시각화할 수 있는가?

가능하다. 선형대수는 오히려 수학 분야 중 시각화와 상호작용 실험이 매우 강력한 분야다.

다만 차원에 따라 시각화 방법이 달라진다.

- 1～3차원: 공간 자체를 직접 그린다.
- 4차원 이상: projection, 단면, spectrum, heatmap, sparsity pattern, 반복 과정, 오차 곡선을 그린다.
- 추상공간: 좌표 표현의 변화와 invariant를 비교한다.
- Lie 군: 군 전체를 단순한 3D 물체로 그리기보다 좌표 frame, tangent perturbation, exp/log 경로를 그린다.

시각화는 다음 목적으로 사용한다.

1. 정의를 받아들이기 전에 직관을 형성한다.
2. 정리의 결론을 작은 차원에서 예측한다.
3. 알고리즘의 반복 과정을 관찰한다.
4. 수치적 실패를 재현한다.
5. 좌표·frame convention 오류를 발견한다.

그림은 증명을 대신하지 않는다. 모든 시각화 뒤에는 엄밀한 정의와 일반 $n$차원 논의를 둔다.

---

# 2. 파트별 시각화 대상

| 파트 | 주요 시각화 |
|---|---|
| 선형대수 | 벡터 합, span, 기저변환, 격자 변형, 투영, 고유방향, SVD, quadratic form |
| 수치선형대수 | 반올림 오차, condition ellipse, pivoting, sparsity, fill-in, 반복법 convergence |
| 행렬미분 | scalar field, gradient, Hessian curvature, Jacobian의 국소 변형, 계산 그래프 |
| 최적화 | 등고선 위 반복경로, line search, trust region, feasible set, KKT geometry |
| Lie 군 | 회전 좌표계, exp/log, quaternion interpolation, screw motion, pose uncertainty, pose graph |

---

# 3. 대표 시각화 실험

## 3.1 선형변환

$$
y=Ax
$$

단위원, 정사각형, 격자에 $A$를 적용한다.

- scaling
- reflection
- rotation
- shear
- projection
- rank collapse

관찰 질문:

- 열벡터는 표준기저가 어디로 이동한 결과인가?
- determinant의 부호와 크기는 그림에서 어떻게 보이는가?
- rank가 감소할 때 어떤 차원이 사라지는가?

## 3.2 기저변환

하나의 기하학적 벡터를 두 좌표계에 동시에 표시한다.

- 좌표축은 변한다.
- 숫자 성분은 변한다.
- 기하학적 벡터 자체는 변하지 않는다.

active transformation과 passive coordinate change를 서로 다른 애니메이션으로 구분한다.

## 3.3 투영과 최소제곱

- column space
- 관측벡터 $b$
- projection $\hat b$
- residual $r=b-\hat b$

을 한 그림에 표시한다. $A^\top r=0$을 그림과 수식으로 동시에 확인한다.

## 3.4 고유값과 동역학

일반 벡터와 고유벡터에 $A$를 반복 적용한다.

$$
x_{k+1}=Ax_k
$$

- dominant eigenvector
- 안정·불안정 mode
- complex eigenvalue에 의한 회전·진동
- defective matrix의 거동

## 3.5 SVD

단위원이 타원으로 변하는 과정을 세 단계로 나눈다.

$$
V^\top \rightarrow \Sigma \rightarrow U
$$

- 입력공간의 principal direction
- 축척량인 singular value
- 출력공간의 direction
- rank deficiency와 납작해지는 축

## 3.6 Conditioning

단위원 또는 작은 입력 오차 집합이 역문제를 통과하며 크게 확대되는 모습을 그린다.

- singular value ratio
- elongated ellipse
- solution sensitivity
- residual과 solution error의 차이

## 3.7 희소행렬

- `spy` plot
- graph adjacency
- elimination 전후 fill-in
- ordering별 nonzero pattern
- block sparse pose graph

## 3.8 Gradient와 Hessian

2D scalar function $f(x,y)$에 대해 다음을 함께 표시한다.

- surface
- contour
- gradient vector field
- Hessian eigenvector
- local quadratic model

## 3.9 최적화 경로

등고선 위에 iteration을 표시한다.

- gradient descent의 zig-zag
- Newton step
- BFGS 경로
- line-search step acceptance
- trust-region radius
- constrained feasible path

## 3.10 $SO(3)$와 $SE(3)$

$SO(3)$ 전체를 평범한 Euclidean 3D 공간과 동일시하지 않는다. 대신 다음을 그린다.

- 회전하는 body frame
- axis-angle vector
- quaternion SLERP
- tangent perturbation
- exponential curve
- body/spatial angular velocity
- $SE(3)$ screw motion
- pose covariance ellipsoid
- pose graph residual

---

# 4. 기본 소프트웨어 스택

## 4.1 항상 사용하는 도구

| 도구 | 역할 |
|---|---|
| Python | 전체 구현 언어 |
| JupyterLab | 수식, 설명, 코드, 시각화가 결합된 강의노트 |
| NumPy | dense array와 기본 선형대수 |
| SciPy | 행렬분해, sparse solver, 최적화, 회전 표현 |
| SymPy | 기호계산, 정확한 소규모 계산, 공식 검증 |
| Matplotlib | 정적 2D·3D 시각화 |
| Plotly | 회전·확대 가능한 interactive 3D |
| ipywidgets | slider, checkbox, parameter interaction |
| pytest | 단위 테스트와 regression test |
| NetworkX | graph와 sparse matrix 구조 설명 |

## 4.2 선택 도구

| 도구 | 사용 시점 |
|---|---|
| Manim | 정교한 수학 애니메이션 제작 |
| JAX | JVP, VJP, Jacobian, Hessian, 자동미분 |
| PyTorch | reverse-mode autodiff와 계산 그래프 비교 |
| CVXPY | 볼록최적화 모델링 |
| CasADi | 비선형최적화, optimal control, MPC |
| pytransform3d | 좌표 frame, $SO(3)$, $SE(3)$ 시각화 |
| Pinocchio | 실제 articulated robot 운동학·동역학과 미분 |
| GTSAM | factor graph, smoothing, mapping, pose graph |

---

# 5. 파트별 도구 구성

## 5.1 준비편과 제1권

### 필수

- NumPy
- SymPy
- Matplotlib
- Plotly
- ipywidgets
- NetworkX

### 구현 대상

- 벡터·행렬 기본 연산
- Gaussian elimination
- basis와 coordinate transform
- Gram–Schmidt
- projection
- eigen decomposition 실험
- SVD와 pseudoinverse
- manipulability ellipse

### 선택

- Manim: 격자변환, SVD, 기저변환 애니메이션

## 5.2 제2권 수치선형대수

### 필수

- `numpy.linalg`
- `scipy.linalg`
- `scipy.sparse`
- `scipy.sparse.linalg`
- Matplotlib

### 분석 도구

- `time`와 `timeit`
- Python 표준 `tracemalloc`
- sparsity plot
- convergence history
- residual plot
- benchmark table

### 구현 대상

- LU와 pivoting
- Cholesky
- Householder QR
- power iteration
- CG와 GMRES의 교육용 버전
- preconditioned iteration
- matrix-free `LinearOperator`

## 5.3 제3권 행렬미분

### 필수

- SymPy
- JAX
- NumPy
- Matplotlib

### 선택

- PyTorch autograd

### 구현 대상

- differential 기반 손 유도
- finite difference
- complex-step derivative
- JVP와 VJP
- Jacobian과 Hessian
- 작은 automatic differentiation engine
- implicit differentiation

## 5.4 제4권 최적화

### 기본 solver 비교

- `scipy.optimize`

### 볼록최적화

- CVXPY
- 설치된 solver 중 문제에 적합한 backend

### 비선형최적화·최적제어

- CasADi

### 구현 대상

- gradient descent
- line search
- Newton와 trust region
- BFGS와 L-BFGS
- Gauss–Newton과 LM
- IRLS
- equality-constrained KKT solve
- proximal gradient와 ADMM
- constrained IK
- trajectory optimization

## 5.5 제5권 Lie 군

### 기본

- `scipy.spatial.transform.Rotation`
- pytransform3d
- Matplotlib
- Plotly

### 심화

- Pinocchio
- GTSAM
- 필요 시 CasADi 또는 JAX

### 구현 대상

- hat/vee
- $SO(3)$ exp/log
- quaternion conversion
- $SE(3)$ exp/log
- Adjoint
- left/right Jacobian
- pose composition
- covariance propagation
- product of exponentials
- body/space Jacobian
- manifold Gauss–Newton

---

# 6. 단계별 환경 설치

모든 패키지를 처음부터 한 환경에 넣지 않는다. 학습 단계에 맞추어 확장한다.

## 6.1 기본 환경

```bash
python -m venv .venv
```

macOS·Linux:

```bash
source .venv/bin/activate
```

Windows:

```bash
.venv\Scripts\activate
```

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 6.2 행렬미분 단계

```bash
python -m pip install jax
```

PyTorch 비교가 필요할 때만 별도 설치한다.

## 6.3 최적화 단계

```bash
python -m pip install cvxpy casadi
```

## 6.4 Lie 군 단계

```bash
python -m pip install pytransform3d
```

Pinocchio와 GTSAM은 운영체제 및 Python 버전에 따라 설치 방식이 달라질 수 있으므로, 해당 프로젝트 시점에 독립 환경을 만드는 것을 원칙으로 한다.

---

# 7. 권장 저장소 구조

```text
linear_algebra_for_robotics/
├── README.md
├── requirements.txt
├── docs/
│   ├── 00_master_plan.md
│   ├── 01_course_syllabus.md
│   ├── 02_chapter_authoring_template.md
│   └── 03_visualization_and_tools.md
├── notebooks/
│   ├── 00_prerequisites/
│   ├── 01_linear_algebra/
│   ├── 02_numerical_linear_algebra/
│   ├── 03_matrix_calculus/
│   ├── 04_optimization/
│   └── 05_lie_groups/
├── src/
│   └── linear_algebra_for_robotics/
├── tests/
├── figures/
└── projects/
```

## 역할 분리

- `docs/`: 설명, 정의, 증명, 강의계획
- `notebooks/`: 탐구와 시각화
- `src/`: 재사용 가능한 구현
- `tests/`: 수학적 성질과 edge case 검증
- `figures/`: 문서에서 사용하는 결과 이미지
- `projects/`: 파트별 종합 프로젝트

---

# 8. Notebook 작성 규칙

## 파일명

```text
01_vectors_and_coordinates.ipynb
02_linear_combinations_and_span.ipynb
03_gaussian_elimination.ipynb
```

## 각 notebook의 구조

1. 학습 목표
2. 선수개념
3. 수학적 정의
4. 손 계산 예제
5. 직접 구현
6. 라이브러리 구현
7. 시각화
8. 수치오차 분석
9. 로봇 응용
10. 연습문제
11. 테스트
12. 요약

## 코드 원칙

- 모든 함수에 입력과 출력 shape를 docstring으로 명시한다.
- 가능한 경우 type hint를 사용한다.
- random seed를 고정한다.
- plot만 보고 결론을 내리지 않고 수치 metric을 함께 출력한다.
- `np.linalg.inv(A) @ b` 대신 `np.linalg.solve(A, b)`를 기본으로 한다.
- 허용오차의 근거를 설명한다.

---

# 9. 시각화 품질 기준

- 축 이름과 물리 단위를 표시한다.
- 좌표 frame 이름을 표시한다.
- 3D 축의 aspect ratio 왜곡을 점검한다.
- 원본과 변환 결과를 구분한다.
- 반복 알고리즘은 iteration 번호를 표시한다.
- singularity·ill-conditioning은 정상 사례와 나란히 비교한다.
- 색에만 의존하지 않고 marker, line style, annotation도 사용한다.
- 정적 그림과 interactive 그림의 목적을 구분한다.

---

# 10. 검증 전략

## 선형대수

- reconstruction error
- orthogonality error
- rank
- projection idempotence

## 수치선형대수

- backward error
- residual history
- condition estimate
- factorization reconstruction

## 행렬미분

- finite difference
- complex step
- directional derivative
- Taylor remainder rate

## 최적화

- objective history
- gradient norm
- constraint violation
- KKT residual
- step acceptance

## Lie 군

- $R^\top R=I$
- $\det R=1$
- `Exp(Log(R))` reconstruction
- perturbation Jacobian check
- frame-invariance test
- composition·inverse identity test

---

# 11. 첫 번째 시각화 묶음

준비편과 첫 선형대수 단원에서 다음 notebook을 우선 제작한다.

1. `vectors_points_and_coordinates.ipynb`
2. `linear_combinations_and_span.ipynb`
3. `matrices_as_linear_maps.ipynb`
4. `basis_change_active_vs_passive.ipynb`
5. `projection_and_least_squares.ipynb`
6. `eigenvectors_and_dynamics.ipynb`
7. `svd_unit_circle_to_ellipse.ipynb`
8. `robot_jacobian_manipulability.ipynb`

각 notebook은 손 계산, 직접 구현, interactive visualization, 수치검증, 로봇 사례를 모두 포함한다.
