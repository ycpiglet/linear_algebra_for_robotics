# Notebook 계획

이 디렉터리는 수식, 코드, 시각화, 수치검증을 결합한 실습 자료를 저장한다.

## 예정 구조

```text
notebooks/
├── 00_prerequisites/
├── 01_linear_algebra/
├── 02_numerical_linear_algebra/
├── 03_matrix_calculus/
├── 04_optimization/
└── 05_lie_groups/
```

## 공통 구성

각 notebook은 다음 순서로 작성한다.

1. 학습 목표와 핵심 질문
2. 선수개념
3. 역사·어원 요약
4. 엄밀한 정의
5. 손 계산 예제
6. 핵심 알고리즘 직접 구현
7. NumPy/SciPy/JAX 등의 기준 구현
8. 2D·3D 또는 interactive 시각화
9. parameter 변화 실험
10. 오차·조건수·성능 분석
11. 로봇공학 적용 사례
12. pytest로 옮길 검증 항목
13. 연습문제와 요약

## 첫 번째 제작 순서

| 순서 | Notebook | 핵심 내용 |
|---:|---|---|
| 1 | `vectors_points_and_coordinates.ipynb` | 점, 벡터, 좌표, 기저의 구분 |
| 2 | `linear_combinations_and_span.ipynb` | span과 affine structure |
| 3 | `matrices_as_linear_maps.ipynb` | 격자와 도형의 선형변환 |
| 4 | `basis_change_active_vs_passive.ipynb` | 능동변환과 수동 좌표변환 |
| 5 | `projection_and_least_squares.ipynb` | projection, residual, normal equation |
| 6 | `eigenvectors_and_dynamics.ipynb` | 고유방향과 반복 동역학 |
| 7 | `svd_unit_circle_to_ellipse.ipynb` | SVD의 회전–축척–회전 해석 |
| 8 | `robot_jacobian_manipulability.ipynb` | Jacobian, SVD, singularity |

## 검증 원칙

- notebook은 커널을 재시작한 뒤 위에서 아래로 실행되어야 한다.
- random seed를 고정한다.
- 모든 벡터·행렬의 shape를 설명한다.
- 그림과 함께 수치 metric을 출력한다.
- 작은 직접 구현과 검증용 라이브러리 구현을 구분한다.
- edge case, singular case, ill-conditioned case를 포함한다.
- `inv(A) @ b`보다 `solve(A, b)`를 우선한다.

## 결과 저장

재사용할 그림은 `figures/`에 저장하고, 일반적인 생성물·임시 데이터는 Git에 포함하지 않는다. 핵심 결과는 notebook 내부에도 남겨 문맥을 보존한다.
