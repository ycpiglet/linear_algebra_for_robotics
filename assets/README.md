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

## 변경 원칙

1. 새 색·간격·그림자 값을 컴포넌트에 직접 쓰기 전에 token으로 승격할지 판단한다.
2. 같은 의미의 블록을 새 class로 복제하지 않는다. `design-system.qmd`의 semantic block을 재사용한다.
3. 색과 아이콘만으로 뜻을 전달하지 않는다. 항상 보이는 한글 label이나 heading을 둔다.
4. JavaScript가 실패해도 본문과 용어 정의를 읽을 수 있어야 한다.
5. EPUB에서는 animation, fixed UI, tooltip에 핵심 정보를 맡기지 않는다.
6. light, dark, 320 px reflow, print, EPUB을 함께 검증한다.

