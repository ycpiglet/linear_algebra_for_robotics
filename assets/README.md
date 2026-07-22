# Asset contract

`assets/`는 Robotics Math Atlas의 시각 언어와 런타임 자원을 위한 단일 기준점이다.

| 경로 | 책임 |
|---|---|
| `styles/_tokens.scss` | 웹의 색, 글꼴, 간격, radius, shadow, motion token |
| `styles/_content-blocks.scss` | 장문 타이포그래피, 학습 카드, glossary, 수식, motion |
| `styles/theme.scss` | Quarto/Bootstrap 연결과 사이트 컴포넌트의 유일한 SCSS entry point |
| `styles/epub.css` | JavaScript와 최신 CSS에 의존하지 않는 EPUB 전용 subset |
| `styles/typst-fonts.typ` | orange-book Typst 출력에 번들 native font를 적용하는 PDF adapter |
| `js/atlas.js` | 선수지식·깊이·진도·glossary·reading progress progressive enhancement |
| `includes/atlas-scripts.html` | 어느 출력 깊이에서도 site root를 찾는 loader |
| `icons/` | 재사용 SVG와 아이콘 작성 규칙 |
| `cover.svg`, `favicon.svg` | 책 표지와 사이트 식별 자산 |

## 글꼴·token 배포 계약

`styles/_tokens.scss`가 type role과 색·간격의 canonical source다. Web SCSS는 이를 직접
소비하고, EPUB CSS와 Matplotlib adapter는 각 출력 제약 때문에 native 값을 유지하되
contract test로 parity를 검사한다. PDF는 같은 upstream family를 Typst가 직접 embed한다.

| 역할/출력 | family와 실제 weight | 배포·대체 규칙 |
|---|---|---|
| Web body·heading·caption·label | `Atlas Sans KR` 400/700 | 번들 WOFF2를 첫 family로 두고 `font-display: swap`; 합성 weight/style 금지 |
| EPUB body·heading·caption·label | `Atlas Sans KR` 400/700 | WOFF2와 `OFL.txt`를 package manifest에 포함; reader의 사용자 글꼴 override를 막지 않음 |
| PDF | `Atlas Sans KR` 400/700 | 번들 OTF를 Typst `font-paths`와 orange-book용 `assets/styles/typst-fonts.typ` adapter로 embed; code는 `Noto Sans Mono CJK KR`, math는 Typst math font |
| plot | `Atlas Sans KR` 400/700 | 저장소 내부용 `robotics_math_atlas.plot_style`가 번들 OTF를 `font_manager.addfont`로 등록하고 semantic plot role을 적용; SVG text는 편집 가능하게 유지 |
| code·math | mono stack 400 / math renderer 400 | Atlas Sans KR에 없는 mono·math glyph를 합성하지 않고 전용 stack에 위임 |

번들 파일은 Noto Sans CJK KR 2.004(빌드 기준 Debian `fonts-noto-cjk`
`20220127+repack1-1`)의 KR face를 같은 glyph subset의 CFF OTF와 WOFF2로 만든 derivative다.
family 이름은 OFL의 derivative naming 요구와 원본 전체 글꼴과의 혼동 방지를 위해
`Atlas Sans KR`로 바꾼다.

| 파일 | 용도 | weight | 크기 | SHA-256 |
|---|---|---:|---:|---|
| `fonts/AtlasSansKR-Regular.otf` | PDF·plot native | 400 | 1,793,040 bytes | `105537d3976ffb40686e020bfbe6c95a466701ff24cb1a581d83c424c61fab02` |
| `fonts/AtlasSansKR-Bold.otf` | PDF·plot native | 700 | 1,896,260 bytes | `f7991701f029074bbe2f76394c9c6c4f111cfad2320aed816215270e225cd4b6` |
| `fonts/AtlasSansKR-Regular.woff2` | Web·EPUB | 400 | 1,067,920 bytes | `28afdc16f0161a4092f700a5a58afc9bf44c61a6cf88c8a2e942f89b32e478df` |
| `fonts/AtlasSansKR-Bold.woff2` | Web·EPUB | 700 | 1,153,620 bytes | `eb99fdcbcc1810ea326ee5881a9121180c46bee8e3be6214800c389140081634` |

네 파일은 완성형 한글, 기본 Latin, Greek, 숫자·문장부호, 화살표와 일반 수학 연산자를
포함한다. 같은 weight의 OTF와 WOFF2는 name table·glyph set·fixed timestamp가 같고,
실제 format·weight·대표 glyph와 위 hash는 contract test가 확인한다.
라이선스와 derivative 설명은 `fonts/OFL.txt`가 단일 배포 사본이다.
italic face는 번들하지 않는다. `font-synthesis: none`을 유지하고 `em`은 Web·EPUB에서
색과 밑줄, PDF에서 색과 밑줄을 사용해 기울임 합성 없이도 의미가 남게 한다. PDF의
고정폭 code family는 현재 빌드 호스트의 `Noto Sans Mono CJK KR`를 요구하며, 번들 전까지
이 시스템 의존성은 출력 verifier가 아니라 Typst build 자체가 fail-closed로 검사한다.

재생성은 Noto CJK source가 설치된 clean environment에서 실행한다.
builder는 Debian `fonts-noto-cjk` `20220127+repack1-1`의 Regular/Bold TTC SHA-256과
TTC index 1의 `Noto Sans CJK KR` family를 먼저 검증하며, 다른 원본으로 조용히
다른 글꼴을 만들지 않는다.

```bash
.tools/uv/uv run --locked python scripts/build_epub_fonts.py
```

재생성 뒤 font contract test와 Web/PDF/EPUB build를 통과시키고 hash 표를 함께 갱신한다.

## 변경 원칙

1. 새 색·간격·그림자 값을 컴포넌트에 직접 쓰기 전에 token으로 승격할지 판단한다.
2. 같은 의미의 블록을 새 class로 복제하지 않는다. `design-system.qmd`의 semantic block을 재사용한다.
3. 색과 아이콘만으로 뜻을 전달하지 않는다. 항상 보이는 한글 label이나 heading을 둔다.
4. JavaScript가 실패해도 본문과 용어 정의를 읽을 수 있어야 한다.
5. EPUB에서는 animation, fixed UI, tooltip에 핵심 정보를 맡기지 않는다.
6. light, dark, 320 px reflow, print, EPUB을 함께 검증한다.
7. body·heading·caption·label은 400/700 이외의 합성 weight를 요청하지 않는다.
8. EPUB/PDF/plot adapter의 native 값은 `_tokens.scss`와 parity test 없이 바꾸지 않는다.
