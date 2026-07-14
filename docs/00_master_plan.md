# 통합 교재 마스터 플랜

## 가제

**《선형대수에서 로봇 최적화까지》**  
부제: **구조, 수치계산, 행렬미분, 최적화, Lie 군의 통합적 이해**

이 교재는 다섯 개의 독립 과목을 한 줄기의 논리로 연결한다.

1. 학부 선형대수학
2. 수치선형대수학
3. 행렬미분과 자동미분
4. 수치최적화
5. Lie 군·Lie 대수와 로봇 기하학

권장 학습 순서는 다음과 같다.

$$
\boxed{
\text{선형대수}
\rightarrow \text{수치선형대수}
\rightarrow \text{행렬미분}
\rightarrow \text{최적화}
\rightarrow \text{Lie 군과 다양체 최적화}
}
$$

---

# 0. 교육 목표와 범위

## 0.1 최종 학습 목표

학습자는 과정을 마친 뒤 다음 능력을 갖추어야 한다.

- 좌표와 기하학적 대상을 구분한다.
- 행렬을 숫자표가 아닌 선형사상의 좌표 표현으로 해석한다.
- 벡터공간, 부분공간, 기저, rank, null space를 로봇 문제와 연결한다.
- 역행렬을 직접 계산하지 않고 적절한 행렬분해로 선형시스템을 푼다.
- condition number, backward error, 수치적 안정성을 분석한다.
- 벡터·행렬 함수의 Jacobian과 Hessian을 직접 유도한다.
- 자동미분 결과를 finite difference와 Taylor test로 검증한다.
- 비제약·제약·볼록·비선형 최소제곱 문제를 올바르게 모델링한다.
- $SO(3)$와 $SE(3)$ 위에서 회전·자세를 표현하고 미분한다.
- inverse kinematics, calibration, state estimation, pose graph, trajectory optimization을 구현한다.

## 0.2 핵심 범위

- 유한차원 실수·복소수 벡터공간
- 선형사상과 행렬 표현
- 고유값, 대칭행렬, SVD, 최소제곱
- 부동소수점, 조건수, 안정성, 희소 선형시스템
- 벡터·행렬 함수의 미분과 자동미분
- 비제약·제약·볼록·비선형 최적화
- $SO(2)$, $SO(3)$, $SE(2)$, $SE(3)$
- 로봇 운동학, 상태추정, 캘리브레이션, SLAM, 최적제어

## 0.3 보충 부록으로 제공할 범위

- 다변수 미적분학
- 확률, 공분산, Gaussian 분포
- 미분방정식과 상태공간 모델
- 강체 운동학
- 제어이론 기초
- Python과 과학계산 기초
- 수학적 증명 방법

## 0.4 본 과정의 중심에서 제외하는 분야

아래 주제는 필요할 때 연결 관계를 소개하되, 별도의 심화 과정으로 남긴다.

- 무한차원 함수해석학
- 일반 표현론
- 대수기하학
- 범주론과 호몰로지
- 일반 텐서해석 전체
- PDE의 함수공간 이론

단, `vec`, Kronecker product, 고차 미분 텐서처럼 행렬미분에 필요한 도구는 포함한다.

---

# 준비편: 수학과 계산의 언어

## P-01. 수학적 대상과 표기법

### P-01.1 집합과 함수

- 집합, 원소, 부분집합
- Cartesian product
- 함수, 사상, 정의역, 공역, 상
- 단사, 전사, 전단사
- 합성함수와 역사상
- 관계와 동치관계

### P-01.2 수식과 shape

- scalar, vector, matrix, tensor 표기
- 열벡터 관례와 행벡터 관례
- 첨자 표기와 합 기호
- 행렬곱의 차원 규칙
- `(n,)`, `(n, 1)`, `(1, n)`의 차이
- 물리 단위와 차원 검사의 중요성

### P-01.3 좌표와 대상

- 점과 벡터의 차이
- 기하학적 대상과 좌표 표현의 차이
- 좌표계 선택에 따라 숫자는 변하지만 대상은 유지된다는 의미

### 실습

- 모든 식에 shape를 표시하는 연습
- 유효한 행렬곱과 유효하지 않은 행렬곱 구분
- NumPy 배열 shape 실험

## P-02. 증명과 미적분의 최소 기반

### P-02.1 논리와 증명

- 명제와 조건
- 필요조건과 충분조건
- 직접증명, 대우증명, 귀류법
- 수학적 귀납법
- 반례가 갖는 역할

### P-02.2 극한과 미분

- 수열과 극한
- 연속성
- 편미분과 방향미분
- 전미분
- 다변수 연쇄법칙
- Taylor 전개
- $O(\cdot)$, $o(\cdot)$ 표기

## P-03. 과학계산과 재현 가능한 실험

- Python 함수와 모듈
- NumPy 배열과 broadcasting
- dtype와 부동소수점
- copy와 view
- 난수 seed
- 절대오차와 상대오차
- assertion과 단위 테스트
- Jupyter notebook 작성 원칙
- 직접 구현과 검증용 라이브러리의 역할 분리

---

# 제1권: 선형대수학의 구조와 기하

## LA-01. 스칼라, 벡터, 점, 공간

### LA-01.1 수와 체

- 자연수, 정수, 유리수, 실수, 복소수
- scalar의 의미와 어원
- field가 필요한 이유
- 실수 벡터공간과 복소수 벡터공간

### LA-01.2 벡터의 여러 해석

- 화살표로서의 벡터
- 숫자 목록으로서의 벡터
- 함수와 다항식도 벡터가 될 수 있다는 관점
- 추상 벡터공간의 원소
- 위치벡터, 자유벡터, 변위벡터
- 상태벡터, 특징벡터, 제어입력 벡터

### LA-01.3 좌표와 기저의 예고

- 좌표계와 성분
- 같은 벡터의 서로 다른 좌표
- 물리 단위가 다른 성분을 가진 상태벡터

### 시각화

- 2D·3D 벡터
- 벡터 합과 스칼라배
- 좌표축 변화에 따른 성분 변화

## LA-02. 선형결합, span, affine structure

### LA-02.1 선형결합

- 선형결합의 정의
- 계수의 역할
- 생성집합
- span
- 직선과 평면의 매개변수 표현

### LA-02.2 affine 개념

- affine combination
- convex combination
- affine set와 linear subspace의 차이
- 원점을 지나는 공간과 지나지 않는 공간
- 점과 벡터를 혼동하면 생기는 오류

### 로봇 연결

- 위치와 방향의 표현
- 좌표계 원점 이동
- homogeneous coordinate가 필요한 이유의 예고

## LA-03. 선형연립방정식과 Gaussian elimination

### LA-03.1 세 가지 관점

- 방정식의 집합
- 평면과 초평면의 교점
- 열벡터의 선형결합

### LA-03.2 $Ax=b$

- coefficient matrix
- unknown vector와 measurement vector
- augmented matrix
- homogeneous system
- particular solution과 null-space solution

### LA-03.3 소거법

- elementary row operation
- echelon form과 reduced echelon form
- pivot과 free variable
- 해 없음, 유일해, 무한히 많은 해
- Gaussian elimination의 역사와 알고리즘 구조

### 실전 사례

- 센서 오프셋 캘리브레이션
- 정역학 평형방정식
- 전기회로 해석
- 로봇 링크의 미지 힘 계산

## LA-04. 행렬은 선형사상의 좌표 표현이다

### LA-04.1 선형성

- additivity
- homogeneity
- 선형사상의 정의
- affine transformation과의 차이

### LA-04.2 행렬의 의미

- 행렬의 각 열은 표준기저의 상
- 행렬-벡터 곱의 열 조합 해석
- 행렬-행렬 곱과 사상의 합성
- 항등행렬과 역행렬

### LA-04.3 대표 변환

- scaling
- reflection
- rotation
- shear
- projection
- permutation
- active transformation과 passive transformation

### 시각화

- 격자, 원, 정사각형의 변형
- determinant 0일 때 차원이 붕괴하는 모습

## LA-05. 부분공간, 선형독립, 기저

### LA-05.1 부분공간

- 부분공간 판정법
- column space
- null space
- row space
- left null space

### LA-05.2 독립성과 redundancy

- 선형종속과 선형독립
- 중복 정보
- minimal generating set

### LA-05.3 기저와 좌표

- 기저의 정의
- 좌표벡터
- 표준기저와 비표준기저
- 기저의 비유일성
- 직교기저의 장점

## LA-06. 차원, rank, 네 가지 기본 부분공간

### LA-06.1 차원

- basis cardinality
- finite dimension
- basis extension

### LA-06.2 rank와 nullity

- rank의 여러 동치 정의
- nullity
- rank-nullity theorem
- row rank와 column rank

### LA-06.3 Fundamental theorem of linear algebra

- $\operatorname{Col}(A)$
- $\operatorname{Null}(A)$
- $\operatorname{Row}(A)$
- $\operatorname{Null}(A^\top)$
- orthogonal complement 관계

### 로봇 Jacobian 연결

- column space: 생성 가능한 end-effector velocity
- null space: end-effector를 움직이지 않는 관절운동
- left null space: 생성할 수 없는 wrench 방향

## LA-07. 좌표변환, 닮음변환, 블록행렬

### LA-07.1 기저변환

- transition matrix
- 좌표변환
- 같은 사상의 서로 다른 행렬 표현

### LA-07.2 similarity

- $P^{-1}AP$
- invariant quantity
- eigenvalue가 기저와 무관한 이유

### LA-07.3 블록 구조

- block multiplication
- block triangular matrix
- block inverse
- permutation과 reordering
- Kronecker product 입문
- vectorization 입문

### 실전 사례

- world frame과 body frame 사이의 좌표변환
- 상태공간 모델의 modal coordinate
- 다관절 로봇의 block Jacobian

## LA-08. determinant, 부피, 방향성

### LA-08.1 정의의 여러 관점

- multilinearity와 alternating property
- $2\times2$, $3\times3$ 공식
- permutation expansion
- cofactor expansion

### LA-08.2 기하학

- 길이·면적·부피 확대율
- orientation
- reflection과 부호
- 가역성과 determinant

### LA-08.3 계산과 주의점

- elimination을 통한 determinant
- product rule
- matrix determinant lemma
- Jacobian determinant와 변수변환
- determinant로 수치적 가역성을 판정하면 안 되는 이유

## LA-09. 내적, 노름, dual space, adjoint

### LA-09.1 내적과 기하

- dot product
- 일반 내적
- weighted inner product
- 길이, 각도, 직교성
- Cauchy–Schwarz inequality
- triangle inequality

### LA-09.2 노름

- $1$-norm, $2$-norm, $\infty$-norm
- Frobenius norm
- induced matrix norm
- norm equivalence의 유한차원 의미

### LA-09.3 dual과 adjoint

- linear functional
- covector
- dual space
- Riesz representation의 유한차원 형태
- transpose와 adjoint
- 복소공간의 conjugate transpose

### 실전 연결

$$
\|e\|_W^2=e^\top We
$$

- weighted error
- covariance와 information matrix
- 물리 단위와 metric

## LA-10. 직교성, 투영, 최소제곱

### LA-10.1 직교기저

- orthogonal set
- orthonormal basis
- Gram–Schmidt
- modified Gram–Schmidt의 예고

### LA-10.2 투영

- 한 벡터로의 projection
- 부분공간으로의 projection
- projection matrix
- orthogonal complement

### LA-10.3 최소제곱

- overdetermined system
- residual
- residual의 column space에 대한 직교성
- normal equation
- weighted least squares
- recursive least squares의 출발점

### 실전 사례

- 직선·평면 fitting
- 카메라 파라미터 추정
- 관절 센서 보정
- 시스템 식별
- 다중 센서 측정 결합

## LA-11. 고유값, 고유벡터, 불변부분공간

### LA-11.1 고유구조

- $Av=\lambda v$
- eigendirection의 기하학
- characteristic polynomial
- eigenspace
- algebraic multiplicity와 geometric multiplicity

### LA-11.2 대각화와 결함

- diagonalization
- invariant subspace
- repeated eigenvalue
- defective matrix
- Jordan form의 의미
- minimal polynomial
- Cayley–Hamilton theorem

### LA-11.3 동역학

- 반복 행렬곱 $A^k x$
- 선형 미분방정식
- 안정·불안정·진동 mode
- spectral radius

## LA-12. 대칭행렬, spectral theorem, quadratic form

### LA-12.1 특수 행렬

- symmetric
- Hermitian
- orthogonal
- unitary
- normal

### LA-12.2 Spectral theorem

- 직교·unitary 대각화
- 실수 고유값
- 고유벡터의 직교성
- Rayleigh quotient

### LA-12.3 Quadratic form

- positive definite
- positive semidefinite
- negative definite
- indefinite
- level set와 ellipsoid
- principal axes
- covariance ellipse
- Hessian과 곡률의 예고
- Schur complement의 기하학적 의미

## LA-13. SVD, pseudoinverse, 저차원 구조

### LA-13.1 SVD

- singular value
- right singular vector
- left singular vector
- $A=U\Sigma V^\top$
- 회전–축척–회전 해석
- compact SVD

### LA-13.2 해와 rank

- rank와 0이 아닌 singular value
- Moore–Penrose pseudoinverse
- minimum-norm solution
- rank-deficient least squares
- condition number

### LA-13.3 저차원 근사

- low-rank approximation
- Eckart–Young 관점
- PCA
- 데이터 압축과 잡음 제거

### 로봇 응용

- Jacobian singularity
- manipulability ellipsoid
- pseudoinverse inverse kinematics
- damped least squares
- null-space control

## LA-14. 행렬함수와 선형대수 종합

- 행렬 다항식
- 행렬 거듭제곱
- matrix exponential
- matrix logarithm
- matrix square root
- spectral definition
- $e^{At}$와 선형 미분방정식
- continuous-time과 discrete-time
- 복소 고유값과 실수 시스템
- 회전 생성자
- 상태공간 모델

### 제1권 프로젝트

**2자유도 또는 6자유도 로봇 팔의 Jacobian과 singularity 분석**

1. forward kinematics 구현
2. Jacobian 유도 및 구현
3. column space와 null space 분석
4. SVD 계산
5. manipulability ellipse/ellipsoid 시각화
6. pseudoinverse inverse kinematics 구현
7. singularity 근처의 수치오차 분석

---

# 제2권: 수치선형대수학

## NLA-01. 부동소수점과 오차

- 실수와 컴퓨터 수의 차이
- binary floating-point
- machine epsilon
- rounding
- overflow와 underflow
- catastrophic cancellation
- absolute error와 relative error
- forward error와 backward error
- 연산 순서와 재현성
- float32와 float64

## NLA-02. conditioning과 stability

- 문제의 민감도
- 알고리즘의 안정성
- well-conditioned와 ill-conditioned
- condition number
- perturbation analysis
- residual과 실제 해 오차의 차이
- backward stable algorithm
- scaling과 equilibration

> **Conditioning**은 문제가 본질적으로 어려운지를, **stability**는 알고리즘이 불필요한 오차를 추가하는지를 설명한다.

## NLA-03. Gaussian elimination, LU, pivoting

- elimination matrix
- $PA=LU$
- forward substitution
- backward substitution
- partial pivoting
- complete pivoting
- pivot growth
- 여러 right-hand side
- determinant와 LU
- inverse 계산을 피해야 하는 이유
- banded system
- block LU

## NLA-04. Cholesky, $LDL^\top$, Schur complement

- symmetric positive definite matrix
- $A=LL^\top$
- $LDL^\top$
- symmetric indefinite system
- block elimination
- Schur complement
- covariance와 information matrix
- Kalman filter 연결
- marginalization
- KKT system 연결

## NLA-05. QR 분해

- orthogonal transformation
- classical Gram–Schmidt
- modified Gram–Schmidt
- Householder reflection
- Givens rotation
- full QR와 reduced QR
- QR least squares
- orthogonality loss
- streaming update
- rank-revealing QR

## NLA-06. 최소제곱과 regularization

- normal equation의 조건수 제곱 문제
- QR least squares
- SVD least squares
- rank-deficient problem
- Tikhonov regularization
- ridge regression
- truncated SVD
- damping
- bias–variance 관점
- inverse problem

## NLA-07. 고유값 수치 알고리즘

- power iteration
- inverse iteration
- shifted inverse iteration
- Rayleigh quotient iteration
- Hessenberg reduction
- QR iteration
- symmetric eigenproblem
- deflation
- eigenvalue sensitivity
- pseudospectrum 입문
- generalized eigenvalue problem

## NLA-08. SVD 계산과 저차원 근사

- bidiagonalization
- SVD 계산의 전체 흐름
- 작은 singular value의 민감도
- truncated SVD
- incremental SVD
- low-rank update
- PCA 구현
- randomized SVD 입문

## NLA-09. 희소행렬

- dense와 sparse
- sparsity pattern
- COO, CSR, CSC
- banded matrix
- graph와 matrix의 대응
- fill-in
- elimination ordering
- sparse LU와 sparse Cholesky
- block sparse matrix
- factor graph와 희소성

## NLA-10. 반복법과 Krylov 부분공간

- Jacobi
- Gauss–Seidel
- stationary iteration
- spectral radius
- steepest descent
- conjugate gradient
- MINRES
- GMRES
- BiCGSTAB
- Krylov subspace
- Arnoldi와 Lanczos
- residual convergence와 stopping criterion

## NLA-11. 전처리와 matrix-free 계산

- preconditioner의 목적
- Jacobi preconditioner
- incomplete Cholesky
- incomplete LU
- block preconditioner
- Schur complement preconditioner
- matrix-vector product만 사용하는 알고리즘
- `LinearOperator`
- Jacobian-free와 Hessian-vector product
- 대규모 최적화와 연결

## NLA-12. 성능, 검증, 로봇 응용

- FLOP과 실제 실행시간
- 메모리 접근 비용
- vectorization
- BLAS·LAPACK 관점
- batch operation
- CPU와 GPU 계산 구조
- benchmark 설계
- residual 검증
- tolerance 설정
- adversarial numerical test

### 제2권 프로젝트

**희소 pose-estimation 선형시스템**

1. block sparse normal matrix 구성
2. dense solver와 sparse solver 비교
3. Cholesky와 CG 비교
4. ordering에 따른 fill-in 비교
5. condition number와 convergence 분석
6. preconditioner 효과 시각화

---

# 제3권: 행렬미분과 자동미분

## MC-01. 미분은 최적의 국소 선형근사다

- 1변수 미분의 재해석
- directional derivative
- Gâteaux derivative
- Fréchet derivative
- 미분가능성과 방향미분 가능성의 차이
- differential $df$
- derivative와 gradient의 차이
- 내적에 따라 gradient가 달라지는 이유

## MC-02. 표기법, differential, trace, vec

- numerator-layout와 denominator-layout
- shape-first notation
- differential notation
- trace trick
- trace의 cyclic property
- Frobenius inner product
- `vec`
- Kronecker product
- commutation matrix
- component 방식과 coordinate-free 방식

## MC-03. 스칼라 함수의 gradient

- $f:\mathbb R^n\rightarrow\mathbb R$
- gradient의 정의
- 방향미분과 gradient
- 선형함수
- quadratic function
- weighted norm
- least-squares objective
- bilinear form
- trace objective
- regularization

대표 공식을 처음부터 유도한다.

$$
\nabla_x(a^\top x),\qquad
\nabla_x(x^\top Ax),\qquad
\nabla_x\frac12\|Ax-b\|^2
$$

## MC-04. 벡터·행렬 함수와 Jacobian

- $f:\mathbb R^n\rightarrow\mathbb R^m$
- Jacobian의 정의
- 각 행과 열의 의미
- pushforward
- local linearization
- 좌표변환의 Jacobian
- residual Jacobian
- geometric Jacobian과 analytic Jacobian
- block sparse Jacobian
- Jacobian-vector product

## MC-05. Hessian과 2차 미분

- second differential
- Hessian
- mixed partial derivative
- symmetry 조건
- curvature
- positive definite Hessian
- saddle point
- local quadratic model
- Hessian-vector product
- Gauss–Newton approximation
- Fisher information 연결

## MC-06. 주요 행렬함수의 미분

- $d(A^{-1})$
- $d(Ax)$
- linear solve의 미분
- $d\det A$
- $d\log\det A$
- trace function
- matrix norm
- Cholesky factor의 미분
- 고유값·고유벡터의 민감도
- singular value와 SVD의 미분
- degeneracy
- matrix exponential의 Fréchet derivative

## MC-07. 연쇄법칙과 계산 그래프

- scalar chain rule
- multivariable chain rule
- Jacobian product
- computational graph
- local derivative
- forward accumulation
- reverse accumulation
- JVP와 VJP
- adjoint variable
- backpropagation
- 메모리와 연산량 trade-off

## MC-08. 자동미분과 암시적 미분

- symbolic differentiation
- finite difference
- automatic differentiation
- dual number
- forward-mode AD
- reverse-mode AD
- higher-order AD
- custom derivative
- implicit function theorem
- $x^\star(\theta)$의 미분
- linear solve through differentiation
- KKT differentiation
- differentiable optimization

## MC-09. 미분 검증과 로봇 응용

- forward finite difference
- central finite difference
- complex-step differentiation
- directional derivative test
- Taylor remainder test
- gradient check
- Jacobian check
- step size와 수치오차
- frame convention 오류 탐지
- 단위와 scale 검증

### 제3권 프로젝트

**카메라 또는 로봇 캘리브레이션 residual의 Jacobian**

1. residual 정의
2. analytic Jacobian 유도
3. SymPy 검증
4. 자동미분 결과 비교
5. finite-difference 및 Taylor test
6. 잘못된 Jacobian이 convergence에 미치는 영향 분석

---

# 제4권: 최적화

## OPT-01. 최적화 문제를 만드는 법

- decision variable
- parameter
- objective
- residual과 cost
- constraint
- feasible set
- 단위와 scaling
- regularization
- hard constraint와 soft constraint
- penalty와 slack variable
- 실제 문제를 수식으로 번역하는 절차

## OPT-02. 해의 존재성과 최적성 조건

- local minimum과 global minimum
- strict minimum
- stationary point
- saddle point
- Taylor model
- first-order necessary condition
- second-order necessary condition
- second-order sufficient condition
- coercivity
- compactness와 해의 존재
- non-unique solution

## OPT-03. 볼록집합과 볼록함수

- convex set
- affine set
- convex hull
- convex cone
- epigraph
- convex function
- strictly convex
- strongly convex
- smoothness
- Lipschitz gradient
- Jensen inequality
- sublevel set
- PSD Hessian 판정

## OPT-04. Gradient descent와 line search

- steepest descent
- gradient 방향의 의미
- fixed step
- exact line search
- backtracking
- Armijo condition
- Wolfe condition
- convergence
- condition number와 zig-zag
- 변수 scaling
- stopping criterion

## OPT-05. 가속법, 좌표법, 사전조건화

- momentum
- Nesterov acceleration
- coordinate descent
- block coordinate descent
- preconditioned gradient
- diagonal scaling
- variable transformation
- steepest direction이 norm에 의존하는 이유

## OPT-06. Newton method와 trust region

- local quadratic model
- Newton direction
- Hessian linear solve
- descent direction이 아닐 수 있는 경우
- modified Newton
- damping
- trust-region subproblem
- Cauchy point
- dogleg
- local quadratic convergence
- truncated Newton

## OPT-07. Quasi-Newton

- secant condition
- rank-one update
- BFGS
- DFP
- SR1
- positive definiteness 유지
- line search와 BFGS
- L-BFGS
- 제한된 메모리 구현

## OPT-08. 비선형 최소제곱

$$
\min_x \frac12\|r(x)\|^2
$$

- residual 구조
- exact Hessian
- Gauss–Newton approximation
- Gauss–Newton method
- Levenberg–Marquardt
- damping과 trust-region 해석
- rank deficiency
- gauge freedom
- sparse block structure

## OPT-09. Robust estimation

- outlier
- M-estimator
- Huber, Cauchy, Tukey loss
- influence function
- iteratively reweighted least squares
- scale estimation
- RANSAC과 연속 최적화의 역할 구분
- robust sensor fusion과 SLAM

## OPT-10. 등식제약 최적화

- equality constraint
- feasible direction
- tangent space
- Lagrange multiplier
- Lagrangian
- first-order condition
- constraint qualification
- KKT matrix
- null-space method
- range-space method
- reduced Hessian

## OPT-11. 부등식제약과 KKT 조건

- inequality constraint
- active·inactive constraint
- complementary slackness
- primal feasibility
- dual feasibility
- KKT conditions
- LICQ
- second-order conditions
- active-set method
- projected gradient
- barrier와 penalty의 차이

## OPT-12. Duality와 민감도

- Lagrange dual function
- weak duality
- strong duality
- duality gap
- Slater-type 조건의 의미
- convex conjugate
- support function
- sensitivity
- shadow price
- multiplier와 parameter variation

## OPT-13. LP, QP, SOCP, SDP

- linear programming
- quadratic programming
- convex QP
- least squares as QP
- constrained control allocation
- second-order cone
- norm constraint
- semidefinite constraint
- conic standard form
- modeling language와 solver의 구분

## OPT-14. 비매끄러운 최적화

- subgradient
- subdifferential
- $L_1$ norm
- sparsity
- proximal operator
- soft thresholding
- projected proximal gradient
- proximal gradient
- FISTA
- operator splitting
- ADMM

## OPT-15. 비볼록·확률적 최적화

- local minimum과 global minimum
- initialization
- basin of attraction
- saddle point
- stochastic gradient
- mini-batch
- noise와 variance
- online optimization
- continuation
- multi-start
- 로봇 문제의 비볼록성

## OPT-16. 일반 비선형계획과 로봇 최적화

- sequential quadratic programming
- interior-point method
- augmented Lagrangian
- direct shooting
- multiple shooting
- direct collocation
- trajectory optimization
- inverse kinematics as optimization
- model predictive control
- 입력 제한
- 충돌·거리 제약
- manifold optimization으로의 연결

### 제4권 프로젝트

**6자유도 로봇의 제약조건이 있는 inverse kinematics**

1. pose residual 정의
2. joint limit
3. workspace 또는 collision constraint
4. Gauss–Newton과 LM 구현
5. SQP 또는 constrained solver 사용
6. analytic Jacobian과 자동미분 비교
7. 초기값에 따른 local minimum 분석
8. singularity와 regularization 분석

---

# 제5권: Lie 군과 로봇 기하학

## LIE-01. 왜 회전을 벡터처럼 다루면 안 되는가

- orientation과 position의 차이
- 회전의 자유도
- 회전행렬의 제약식
- Euler angle 특이점
- 회전 덧셈의 문제
- 비가환성
- 전역 좌표 하나의 한계
- manifold가 필요한 이유
- active와 passive rotation

## LIE-02. 군, 군작용, 다양체

- group
- identity와 inverse
- associativity
- commutative와 noncommutative
- subgroup
- group action
- orbit와 stabilizer의 직관
- topology의 최소 개념
- chart
- manifold
- local coordinate
- tangent space

## LIE-03. Matrix Lie group과 Lie algebra

- $GL(n)$
- $O(n)$
- $SO(n)$
- $SE(n)$
- matrix group
- smooth group operation
- identity 근처의 미소운동
- Lie algebra
- skew-symmetric matrix
- tangent space at identity
- hat와 vee
- commutator와 Lie bracket

## LIE-04. Tangent space와 trivialization

- tangent vector와 tangent curve
- $T_X\mathcal M$
- left translation과 right translation
- left trivialization과 right trivialization
- body velocity와 spatial velocity
- cotangent space
- differential과 pullback
- metric과 gradient

## LIE-05. Exponential map, logarithm map, BCH

- matrix exponential
- one-parameter subgroup
- algebra에서 group으로의 mapping
- logarithm map
- local inverse
- exponential coordinate
- Baker–Campbell–Hausdorff formula
- commutator correction
- 작은 운동의 합성
- exp와 log의 특이점
- 안정적인 수치 구현

## LIE-06. $SO(2)$와 $SO(3)$

- 2D rotation group
- $SO(2)$ exponential
- 3D rotation matrix
- orthogonality와 determinant $+1$
- $\mathfrak{so}(3)$
- cross-product matrix
- Rodrigues formula
- axis-angle
- rotation vector
- geodesic distance
- trace와 rotation angle

## LIE-07. 회전 표현과 quaternion

- rotation matrix
- Euler angle과 Tait–Bryan angle
- axis-angle
- Rodrigues parameter
- unit quaternion
- quaternion multiplication
- double covering
- sign ambiguity
- SLERP
- normalization
- gimbal lock
- 표현 간 변환
- 저장·계산·최적화 표현의 선택

## LIE-08. $SE(2)$와 $SE(3)$

- rigid-body transformation
- homogeneous matrix
- translation과 rotation
- $SE(2)$와 $SE(3)$
- $\mathfrak{se}(2)$와 $\mathfrak{se}(3)$
- transformation composition
- inverse transformation
- point와 vector의 transformation
- frame notation
- camera extrinsic
- world, base, tool frame

## LIE-09. Twist, screw theory, Adjoint

- angular velocity와 linear velocity
- twist
- screw axis와 pitch
- body twist와 spatial twist
- wrench
- Adjoint map
- $\operatorname{Ad}_T$
- $\operatorname{ad}_\xi$
- coadjoint와 wrench transformation
- power invariance

## LIE-10. Left·right Jacobian과 perturbation

- left perturbation과 right perturbation
- local coordinate
- box-plus와 box-minus
- $SO(3)$ left Jacobian
- $SO(3)$ inverse Jacobian
- $SE(3)$ Jacobian
- exponential과 logarithm의 미분
- small-angle approximation
- frame에 따른 Jacobian 변화
- 논문과 라이브러리의 convention 차이

## LIE-11. 불확실성, 보간, 적분

- manifold 위의 noise
- tangent-space Gaussian
- covariance의 frame 의존성
- covariance propagation
- pose composition uncertainty
- geodesic interpolation
- quaternion interpolation
- angular velocity integration
- discrete integration
- retraction
- normalization과 projection

## LIE-12. 로봇 운동학과 Jacobian

- rigid-body chain
- product of exponentials
- space formulation과 body formulation
- forward kinematics
- space Jacobian과 body Jacobian
- Adjoint를 통한 Jacobian 변환
- singularity
- manipulability
- differential inverse kinematics
- null-space motion
- closed-chain constraint의 기초

## LIE-13. Lie 군 위의 상태추정과 factor graph

- manifold state
- local error
- retraction 기반 EKF
- error-state filter
- invariant error의 개념
- pose measurement residual
- IMU orientation integration의 기초
- factor와 variable node
- factor graph
- linearization point
- marginalization
- gauge freedom
- pose graph와 SLAM residual

## LIE-14. Lie 군 위의 최적화

- Euclidean gradient와 Riemannian gradient
- tangent-space update
- exponential update와 retraction
- manifold Gauss–Newton
- manifold Levenberg–Marquardt
- trust region on manifold
- pose averaging
- hand–eye calibration
- pose graph optimization
- bundle adjustment
- sparse block Hessian
- perturbation convention 검증

### 최종 통합 프로젝트

**$SE(3)$ pose-graph 최적화 또는 로봇 외부 파라미터 캘리브레이션**

1. 상태를 $SE(3)$ 원소로 정의
2. 측정 residual을 Lie algebra에서 정의
3. analytic Jacobian 유도
4. finite difference와 자동미분으로 검증
5. Gauss–Newton 및 LM 구현
6. sparse linear system 구성
7. gauge freedom 처리
8. robust loss 적용
9. covariance 또는 information matrix 분석
10. 3D trajectory와 coordinate frame 시각화
11. dense·sparse solver 성능 비교
12. 기술 보고서 작성

---

# 최종 도달 기준

다음 공식을 단순히 사용하는 것이 아니라, 가정부터 유도하고 안정적으로 구현하며 검증할 수 있어야 한다.

## Damped inverse kinematics

$$
\Delta q
=
J^\top\left(JJ^\top+\lambda^2I\right)^{-1}e
$$

## Gauss–Newton

$$
\left(J^\top WJ\right)\Delta x=-J^\top Wr
$$

## Kalman update의 선형대수 구조

$$
K=PH^\top\left(HPH^\top+R\right)^{-1}
$$

## $SO(3)$ exponential

$$
\operatorname{Exp}(\phi)
=I+
\frac{\sin\theta}{\theta}\phi^\wedge+
\frac{1-\cos\theta}{\theta^2}(\phi^\wedge)^2
$$

## $SE(3)$ perturbation update

$$
T_{k+1}=\operatorname{Exp}(\delta\xi^\wedge)T_k
$$

각 식에 대해 다음 질문에 답할 수 있어야 한다.

- 왜 이 식이 나오는가?
- 어떤 가정이 필요한가?
- 각 행렬의 shape와 공간은 무엇인가?
- 역행렬 대신 어떤 분해 또는 선형해법을 사용해야 하는가?
- singularity와 ill-conditioning에서는 무슨 일이 생기는가?
- 좌·우 perturbation에 따라 무엇이 달라지는가?
- 구현을 수치적으로 어떻게 검증하는가?
- 실제 로봇 시스템에서 어디에 사용되는가?
