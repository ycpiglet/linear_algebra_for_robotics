# Asset contract

`assets/`는 Robotics Math Atlas의 시각 언어와 런타임 자원을 위한 단일 기준점이다.

| 경로 | 책임 |
|---|---|
| `styles/_tokens.scss` | 웹의 색, 글꼴, 간격, radius, shadow, motion token |
| `styles/_content-blocks.scss` | 장문 타이포그래피, 학습 카드, glossary, 수식, motion |
| `styles/theme.scss` | Quarto/Bootstrap 연결과 사이트 컴포넌트의 유일한 SCSS entry point |
| `styles/epub.css` | JavaScript와 최신 CSS에 의존하지 않는 EPUB 전용 subset |
| `js/atlas.js` | 선수지식·깊이·진도·glossary·reading progress progressive enhancement |
| `includes/atlas-scripts.html` | 어느 출력 깊이에서도 site root를 찾는 loader |
| `icons/` | 재사용 SVG와 아이콘 작성 규칙 |
| `cover.svg`, `favicon.svg` | 책 표지와 사이트 식별 자산 |
| `artifact-manifest.yml` | `assets/figures/`의 source·generator·output·consumer·license·stable ID 계약 |

## 변경 원칙

1. 새 색·간격·그림자 값을 컴포넌트에 직접 쓰기 전에 token으로 승격할지 판단한다.
2. 같은 의미의 블록을 새 class로 복제하지 않는다. `design-system.qmd`의 semantic block을 재사용한다.
3. 색과 아이콘만으로 뜻을 전달하지 않는다. 항상 보이는 한글 label이나 heading을 둔다.
4. JavaScript가 실패해도 본문과 용어 정의를 읽을 수 있어야 한다.
5. EPUB에서는 animation, fixed UI, tooltip에 핵심 정보를 맡기지 않는다.
6. light, dark, 320 px reflow, print, EPUB을 함께 검증한다.

## 그림 artifact inventory

`assets/artifact-manifest.yml`은 저장소가 소유한 `assets/figures/` 그림의 단일 inventory다.
생성 가능한 그림은 `production: generated`와 실제 Python generator·`uv.lock`·정규화 규칙을
기록하고, 수동 SVG는 `production: manual`, `generator: null`로 기록한다. 수동 SVG에 재현할 수
없는 generator를 붙이거나 생성 결과를 새로운 수동 원본처럼 편집하지 않는다.

새 그림을 추가할 때는 다음을 한 변경에서 함께 처리한다.

1. 공개 output path와 `figure.*` stable ID를 정한다.
2. 수동 그림은 SVG 자체를 source로, 생성 그림은 실제 generator source와 lockfile을 기록한다.
3. 소비 원고에 결론을 말하는 caption, `fig-alt`, `#fig-*` ID를 모두 둔다.
4. 저장소 라이선스 근거와 모든 consumer를 manifest에 기록한다.
5. 아래 check와, 생성 그림이면 temp-root regeneration을 통과시킨다.

```bash
make artifact-audit
.tools/uv/uv run --locked python platform/scripts/artifact_inventory.py report
.tools/uv/uv run --locked python platform/scripts/artifact_inventory.py trace figure.jacobian-2r-geometry
```

`make artifact-audit`는 `make sync`로 `uv.lock`과 일치하는 환경을 먼저 만든 뒤 check와 임시
디렉터리 재생성을 실행한다. system Python으로 직접 재생성하면 잠금된 Matplotlib·NumPy를
사용한다는 보장이 없으므로 재현성 증거로 인정하지 않는다.

`legacy_baseline`은 2026-07-23에 이미 존재하던 누락만 식별자 단위로 고정한다. 새 그림이나 새
consumer의 ID·caption·alt·provenance 누락은 실패하며, 기존 누락을 고쳤다면 같은 변경에서
baseline 항목도 제거해야 한다. baseline에 새 예외를 추가하는 것은 자동 면제가 아니라 별도
검토가 필요한 계약 변경이다.
