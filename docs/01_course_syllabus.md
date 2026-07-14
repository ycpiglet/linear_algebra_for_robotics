# 강의계획서

## 1. 과정 개요

### 과목명

**Linear Algebra for Robotics: Geometry, Computation, Differentiation, Optimization, and Lie Groups**

### 과정 성격

이 과정은 한 학기짜리 입문 선형대수 강좌가 아니다. 선형대수학을 출발점으로 수치선형대수, 행렬미분, 최적화, Lie 군까지 연결하는 **연구자형 장기 과정**이다.

### 전체 기간

| 과정 | 기간 |
|---|---:|
| 준비편 | 4주 |
| 제1권 선형대수학 | 16주 |
| 제2권 수치선형대수학 | 14주 |
| 제3권 행렬미분·자동미분 | 10주 |
| 제4권 최적화 | 16주 |
| 제5권 Lie 군·로봇 기하학 | 16주 |
| **합계** | **76주** |

### 주당 권장 학습량

- 이론 강의 A: 90분
- 이론 강의 B: 90분
- Python 실습: 120분
- 복습·과제·증명: 3～4시간
- 총 권장 시간: 주당 7～9시간

---

# 2. 선수지식

## 필수

- 고등학교 수준의 대수와 함수
- 기본적인 미분
- Python의 변수, 함수, 반복문에 대한 최소 경험

## 과정 안에서 보충

- 다변수 미적분
- 증명 기법
- 복소수
- 확률과 공분산
- 미분방정식
- 로봇 좌표계와 강체운동

## 선수지식 진단 기준

다음 질문에 완벽히 답하지 못해도 수강할 수 있지만, 준비편에서 반드시 보완한다.

1. 함수의 정의역과 공역을 구분할 수 있는가?
2. 벡터와 점의 차이를 설명할 수 있는가?
3. 행렬곱의 shape를 계산할 수 있는가?
4. 편미분과 방향미분의 차이를 아는가?
5. Python에서 `(n,)`와 `(n, 1)` 배열을 구분하는가?

---

# 3. 학습성과

과정을 마치면 학습자는 다음을 수행할 수 있어야 한다.

## 이론

- 핵심 정의와 정리를 자신의 언어로 설명한다.
- 공식을 필요한 가정에서부터 유도한다.
- 정리의 증명과 반례를 이해하고 재구성한다.
- 좌표에 의존하는 표현과 좌표에 독립적인 대상을 구분한다.

## 계산

- 작은 문제를 손으로 계산한다.
- 대규모 문제에는 적절한 분해와 반복해법을 선택한다.
- condition number, residual, backward error를 분석한다.
- 희소성과 block structure를 이용한다.

## 구현

- NumPy/SciPy를 사용하기 전에 핵심 알고리즘을 직접 구현한다.
- 분석적 Jacobian을 자동미분과 finite difference로 검증한다.
- 실행시간, 메모리, 정확도를 비교한다.
- 테스트 가능한 재현성 있는 notebook과 Python 모듈을 작성한다.

## 로봇 응용

- Jacobian singularity와 manipulability를 분석한다.
- constrained inverse kinematics를 구현한다.
- $SO(3)$, $SE(3)$의 exponential/logarithm map을 구현한다.
- pose graph 또는 캘리브레이션 문제를 manifold 위에서 최적화한다.

---

# 4. 주차별 강의 일정

## 준비편 — 1～4주

| 주차 | 이론 주제 | 실습 | 주간 산출물 |
|---:|---|---|---|
| 1 | 집합, 함수, scalar/vector/matrix, shape, 점과 벡터 | NumPy shape 실험, 유효한 행렬곱 검사 | 표기법·shape 문제 세트 |
| 2 | 명제, 필요·충분조건, 증명, 반례, Taylor 전개 | 수치 Taylor 근사 시각화 | 짧은 증명 5개와 반례 3개 |
| 3 | Python 과학계산, dtype, broadcasting, 테스트 | Jupyter 환경과 pytest 구성 | 재현 가능한 첫 notebook |
| 4 | 전체 과정의 연결도, 선형대수 기반 진단 | 작은 robot Jacobian 예고 실험 | 진단시험 및 개인 보충계획 |

## 제1권 — 선형대수학의 구조와 기하, 5～20주

| 주차 | 이론 주제 | 실습 | 주간 산출물 |
|---:|---|---|---|
| 5 | scalar, vector, point, coordinate | 2D·3D 벡터와 좌표축 시각화 | 개념 에세이: 벡터란 무엇인가 |
| 6 | 선형결합, span, affine set, convex combination | span과 affine plane slider | 손 계산 및 시각화 notebook |
| 7 | $Ax=b$, 해집합, Gaussian elimination | 소거법 직접 구현 | solver v0와 테스트 |
| 8 | 선형사상, 행렬-벡터 곱, 합성 | 격자·원·정사각형 변환 | 선형변환 애니메이션 |
| 9 | 부분공간, 독립성, column/null space | 부분공간 basis 계산 | 독립성 판정 문제 세트 |
| 10 | 기저, 좌표, 차원, rank-nullity | 비표준기저 좌표변환 | 기저변환 구현 |
| 11 | 네 가지 기본 부분공간 | robot Jacobian의 네 공간 분석 | Jacobian 공간 보고서 |
| 12 | 좌표변환, similarity, block matrix | 좌표 frame 변환과 block 연산 | block algebra 문제 세트 |
| 13 | determinant, 부피, orientation | 단위 정사각형·구의 부피 변형 | determinant 시각화 notebook |
| 14 | 내적, 노름, dual, adjoint | weighted norm과 ellipse | metric 비교 실험 |
| 15 | 직교기저, Gram–Schmidt, projection | classical·modified GS 비교 | orthogonality 오차 보고서 |
| 16 | least squares, normal equation, weighted LS | 직선·평면 fitting | calibration mini-project |
| 17 | eigenvalue, eigenspace, diagonalization | 반복변환과 mode 시각화 | 동역학 mode 분석 |
| 18 | symmetric matrix, spectral theorem, quadratic form | covariance ellipse와 Rayleigh quotient | SPD 판정 및 시각화 |
| 19 | SVD, pseudoinverse, low rank | 단위원의 SVD 변형, PCA | SVD 실험 보고서 |
| 20 | matrix exponential과 종합 | 2-DOF/6-DOF Jacobian 프로젝트 | **제1권 프로젝트 제출** |

## 제2권 — 수치선형대수학, 21～34주

| 주차 | 이론 주제 | 실습 | 주간 산출물 |
|---:|---|---|---|
| 21 | floating-point, machine epsilon, cancellation | float32/64 오류 실험 | floating-point failure catalog |
| 22 | conditioning, perturbation, stability | Hilbert matrix와 오차 증폭 | conditioning 보고서 |
| 23 | LU, triangular solve, 계산복잡도 | LU 직접 구현 | LU solver와 residual test |
| 24 | pivoting, growth factor, block LU | pivoting 유무 비교 | 불안정 사례 재현 |
| 25 | Cholesky, $LDL^\top$, Schur complement | SPD 시스템과 marginalization | Schur complement notebook |
| 26 | QR: GS, Householder, Givens | 세 QR 알고리즘 비교 | 정확도·속도 benchmark |
| 27 | 안정적인 least squares와 regularization | QR/SVD/normal equation 비교 | regularization 실험 |
| 28 | power, inverse, QR eigen algorithms | 고유값 반복법 구현 | convergence 분석 |
| 29 | SVD 알고리즘, PCA, randomized method | noisy low-rank data 복원 | low-rank 프로젝트 |
| 30 | sparse matrix format와 graph | COO/CSR/CSC 변환 | sparse 자료구조 실습 |
| 31 | fill-in, ordering, sparse factorization | ordering별 sparsity pattern | fill-in 분석 보고서 |
| 32 | Jacobi, CG, GMRES, Krylov space | iterative solver 직접 구현 | residual history 비교 |
| 33 | preconditioning, matrix-free, JVP/HVP | `LinearOperator`와 preconditioned CG | matrix-free notebook |
| 34 | 성능·메모리·검증 종합 | 희소 pose-estimation 시스템 | **제2권 프로젝트 제출** |

## 제3권 — 행렬미분과 자동미분, 35～44주

| 주차 | 이론 주제 | 실습 | 주간 산출물 |
|---:|---|---|---|
| 35 | 미분을 선형사상으로 보기, Fréchet derivative | 국소 선형근사 시각화 | 정의 중심 문제 세트 |
| 36 | differential, trace trick, vec, Kronecker | SymPy로 항등식 확인 | matrix differential 노트 |
| 37 | scalar objective의 gradient | quadratic·least-squares gradient 구현 | 손 유도 10문제 |
| 38 | vector function과 Jacobian | deformation field와 residual Jacobian | analytic Jacobian notebook |
| 39 | Hessian, curvature, Taylor model | 2D objective의 Hessian 시각화 | 곡률 분석 보고서 |
| 40 | inverse, determinant, logdet, solve, SVD의 미분 | matrix function gradient check | 행렬함수 미분 문제 세트 |
| 41 | 연쇄법칙, 계산 그래프, JVP, VJP | 작은 autodiff engine 설계 | 계산 그래프 보고서 |
| 42 | forward/reverse automatic differentiation | JAX 결과와 손 유도 비교 | AD 비교 notebook |
| 43 | implicit differentiation와 KKT differentiation | linear solve를 통과하는 미분 | implicit diff mini-project |
| 44 | finite difference, complex step, Taylor test | 캘리브레이션 Jacobian 검증 | **제3권 프로젝트 제출** |

## 제4권 — 최적화, 45～60주

| 주차 | 이론 주제 | 실습 | 주간 산출물 |
|---:|---|---|---|
| 45 | variable, objective, residual, constraint 모델링 | 실제 문제를 수식으로 번역 | 모델링 문서 3개 |
| 46 | local/global optimum, 1·2차 조건 | stationary point 분류 | 최적성 조건 문제 세트 |
| 47 | convex set/function, strong convexity | convexity 시각화와 수치 판정 | convexity 보고서 |
| 48 | gradient descent, line search, Armijo/Wolfe | 등고선 위 반복경로 | gradient solver v1 |
| 49 | momentum, coordinate descent, preconditioning | ill-conditioned quadratic 비교 | convergence benchmark |
| 50 | Newton, damping, trust region | Newton/dogleg 구현 | 2차법 실험 보고서 |
| 51 | BFGS, SR1, L-BFGS | quasi-Newton 직접 구현 | solver 비교 |
| 52 | nonlinear least squares, Gauss–Newton, LM | 비선형 curve fitting | NLLS solver v1 |
| 53 | robust loss, influence, IRLS | 이상치가 있는 fitting | robust estimation notebook |
| 54 | equality constraint, Lagrangian, KKT | null-space/range-space 비교 | constrained solve 보고서 |
| 55 | inequality, active set, complementary slackness | 작은 QP 직접 풀이 | KKT 문제 세트 |
| 56 | duality, sensitivity, shadow price | primal-dual 결과 비교 | 민감도 분석 |
| 57 | LP와 QP | control allocation QP | CVXPY model v1 |
| 58 | SOCP, SDP, conic formulation | norm 및 PSD constraint | conic modeling notebook |
| 59 | subgradient, proximal, ADMM, stochastic method | $L_1$ sparse recovery | nonsmooth mini-project |
| 60 | SQP, interior point, trajectory optimization | constrained inverse kinematics | **제4권 프로젝트 제출** |

## 제5권 — Lie 군과 로봇 기하학, 61～76주

| 주차 | 이론 주제 | 실습 | 주간 산출물 |
|---:|---|---|---|
| 61 | orientation이 Euclidean vector가 아닌 이유 | Euler angle 특이점 재현 | 회전표현 비교 에세이 |
| 62 | group, group action, manifold, chart | 원·구면 위 local coordinate | 군·다양체 개념 문제 |
| 63 | matrix Lie group, Lie algebra, bracket | $SO(2)$와 $SO(3)$ 연산 구현 | hat/vee 테스트 |
| 64 | tangent space, left/right translation, trivialization | body/spatial velocity 비교 | frame convention 문서 |
| 65 | exp, log, BCH | 작은 회전 합성 오차 분석 | exp/log notebook |
| 66 | $SO(2)$, $SO(3)$, Rodrigues formula | 회전 좌표축 애니메이션 | SO(3) 구현 v1 |
| 67 | Euler, axis-angle, quaternion, SLERP | 표현 간 변환과 보간 | rotation conversion tests |
| 68 | $SE(2)$, $SE(3)$, homogeneous transform | coordinate-frame tree 시각화 | SE(3) 구현 v1 |
| 69 | twist, screw, Adjoint, wrench | screw motion 애니메이션 | Adjoint 검증 notebook |
| 70 | left/right Jacobian, perturbation convention | analytic/numeric Jacobian 비교 | perturbation guide |
| 71 | manifold uncertainty와 covariance | pose covariance ellipsoid | uncertainty report |
| 72 | 회전·자세의 적분과 보간 | angular velocity integration | integration benchmark |
| 73 | product of exponentials와 forward kinematics | serial manipulator 모델 | POE kinematics 구현 |
| 74 | body/space Jacobian, singularity, IK | manifold inverse kinematics | robot Jacobian project |
| 75 | error-state estimation, factor graph, gauge | 작은 pose graph 구성 | factor graph notebook |
| 76 | manifold Gauss–Newton/LM, pose graph | 최종 시스템 통합 및 발표 | **최종 통합 프로젝트** |

---

# 5. 한 주의 수업 구성

## 이론 강의 A — 개념과 구조, 90분

| 시간 | 내용 |
|---:|---|
| 0～10분 | 실제 문제와 역사적 배경 |
| 10～30분 | 기하학적 직관과 시각화 |
| 30～55분 | 엄밀한 정의와 정리 |
| 55～75분 | 유도 또는 증명 |
| 75～90분 | 기본 예제와 점검 문제 |

## 이론 강의 B — 계산과 응용, 90분

| 시간 | 내용 |
|---:|---|
| 0～20분 | retrieval practice와 복습 |
| 20～45분 | 알고리즘 도출 |
| 45～65분 | 손 계산 예제 |
| 65～80분 | 수치적 실패와 반례 |
| 80～90분 | 로봇 실무 사례 |

## 실습 — 120분

| 시간 | 내용 |
|---:|---|
| 0～20분 | 손 계산과 예상 결과 작성 |
| 20～50분 | 핵심 알고리즘 직접 구현 |
| 50～75분 | 라이브러리 결과와 비교 |
| 75～100분 | 시각화와 parameter sweep |
| 100～120분 | 오차 분석, 테스트, 짧은 보고서 |

---

# 6. 평가 방식

| 평가 | 비중 |
|---|---:|
| 개념 확인 퀴즈 | 10% |
| 손 계산·증명 과제 | 20% |
| Python 실습 | 25% |
| 중간 종합 문제 | 15% |
| 파트별 프로젝트 | 10% |
| 최종 통합 프로젝트 | 20% |

## 평가 기준

- 정의를 정확히 사용하는가?
- 입력·출력 공간과 shape를 명시하는가?
- 가정과 결론을 구분하는가?
- 유도가 논리적으로 이어지는가?
- 직접 구현과 라이브러리 사용을 구분하는가?
- residual과 수치오차를 검증하는가?
- edge case와 singularity를 테스트하는가?
- 코드와 수학 표기가 일치하는가?
- 실무 문제의 물리 단위와 frame convention을 명시하는가?

---

# 7. 연습문제 체계

| 수준 | 목적 | 예시 |
|---|---|---|
| A | 정의와 개념 확인 | 부분공간 조건을 설명하라 |
| B | 손 계산 | $3\times3$ 행렬의 QR을 계산하라 |
| C | 유도와 증명 | projection matrix의 대칭성과 멱등성을 증명하라 |
| D | 구현과 검증 | CG를 구현하고 residual history를 그려라 |
| E | 실무·연구형 | singularity 근처 IK의 안정화 방법을 비교하라 |

모든 문제 해설에는 다음을 포함한다.

1. 정답
2. 핵심 아이디어
3. 단계별 풀이
4. 다른 풀이
5. 자주 발생하는 오답
6. 계산 검산법
7. 관련 실무 사례

---

# 8. 프로젝트 체계

## 프로젝트 1 — Jacobian과 singularity

- forward kinematics
- analytic Jacobian
- SVD와 pseudoinverse
- manipulability
- damped least squares

## 프로젝트 2 — 희소 선형시스템

- block sparse matrix
- Cholesky와 iterative solver
- ordering과 fill-in
- preconditioner

## 프로젝트 3 — Jacobian 검증

- 손 유도
- symbolic differentiation
- automatic differentiation
- finite difference
- Taylor test

## 프로젝트 4 — 제약 inverse kinematics

- nonlinear least squares
- joint limit
- regularization
- SQP 또는 interior-point solver
- 초기값과 local minimum

## 최종 프로젝트 — $SE(3)$ pose graph 또는 calibration

- Lie-group state
- residual in tangent space
- left/right perturbation convention
- analytic Jacobian
- sparse Gauss–Newton 또는 LM
- robust loss
- gauge fixing
- uncertainty analysis
- 3D visualization
- 기술 보고서

---

# 9. 완료 판정

다음 질문에 설명과 코드로 답할 수 있을 때 과정을 완료한 것으로 본다.

1. 행렬은 왜 선형사상 자체가 아니라 좌표 표현인가?
2. rank와 singular value는 어떻게 연결되는가?
3. normal equation 대신 QR/SVD를 써야 하는 경우는 언제인가?
4. residual이 작아도 해 오차가 클 수 있는 이유는 무엇인가?
5. gradient가 내적에 의존한다는 것은 무슨 뜻인가?
6. Gauss–Newton Hessian 근사는 어디서 나오는가?
7. KKT system의 block 구조를 어떻게 안정적으로 푸는가?
8. 회전행렬의 자유도는 3인데 성분이 9개인 이유는 무엇인가?
9. left perturbation과 right perturbation은 Jacobian을 어떻게 바꾸는가?
10. pose graph의 gauge freedom을 어떻게 처리하는가?
