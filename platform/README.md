# Knowledge Atlas platform contract

The platform compiles Quarto front matter into static JSON. It never parses the
Markdown body and does not require a server or account.

## Commands

```bash
python platform/scripts/atlas.py validate
python platform/scripts/atlas.py build
python platform/scripts/atlas.py build --check
python -m unittest discover -s platform/tests -v
```

`build --check` compares generated content while ignoring only `generated_at`.
Set `SOURCE_DATE_EPOCH` for byte-for-byte reproducible timestamps.

## Concept metadata

Stable IDs are lowercase dotted slugs such as `control.pid`. A concept requires
`id`, `title`, `domain`, and `one_line`. Prerequisites vary with the requested
learning depth:

```yaml
difficulty: 4
importance: 5
importance_note: 여러 후속 장에서 같은 언어를 사용한다.
practice_frequency: 4
practice_frequency_note: 공개 구현과 로그 분석에서 자주 직접 만난다.
application_areas: [로봇공학, 제어, 상태추정]
```

`difficulty`, `importance`, and `practice_frequency` use a 1–5 scale. The two
importance/frequency notes explain the rating rather than leaving an ornamental
number, and `application_areas` drives the visible use-area chips.

```yaml
prerequisites:
  intuition:
    required:
      - concept: control.feedback
        competency: explain
        reason: 폐루프의 뜻을 사용한다.
        diagnostic: open loop와 feedback의 차이는?
    helpful: []
    not_required:
      - probability.stochastic_process
```

Depths are `intuition`, `application`, `analysis`, `implementation`,
`derivation`, `proof`, and `teaching`. Canonical competencies are `recognize`,
`explain`, `calculate`, `apply`, `derive`, `prove`, and `teach`. Depth words used
as competency shorthands are normalized to those action words.

Relation keys are `requires`, `helpful`, `derived_from`, `deepens`,
`contrasts_with`, `same_structure_as`, and `used_in`. Hyphenated authoring forms
are accepted and normalized. An unresolved required/helpful prerequisite is an
error; a planned relation target or explicitly not-required concept is a
warning. Required prerequisite cycles and proof dependency cycles are errors.

## Proof and path metadata

Proofs use `dependencies` for other proof IDs and `concepts` (or authoring alias
`proves`) for concepts proved. They may also have depth-specific concept/proof
prerequisites. Paths contain `steps` or staged `stages`; every step has a
`concept` and `depth`. A concise legacy path with `entry-concepts` and
`exit-concept` is normalized into steps.

## Generated static files

`platform/generated/concept-manifest.json` is the canonical UI input. Each
concept includes its repository `source`, root-relative `url`, deployment-safe
`site_path`, normalized prerequisites and relations, and generated backlinks.
It also includes proofs, paths, a typed graph, alias indexes, diagnostics, and a
content hash. Smaller `backlinks.json`, `knowledge-graph.json`, and `paths.json`
files expose the same build under focused contracts.

The Quarto filter injects this marker into concept HTML:

```html
<div id="concept-meta"
     data-concept-id="control.pid"
     data-concept-domain="control"
     data-manifest-url="../../platform/generated/concept-manifest.json"
     hidden></div>
```

The URL uses Quarto's project offset so nested pages and subpath deployments can
resolve the manifest without hard-coding a host.

## Local reading state

The browser stores mastery, selected depth, page favorites, section bookmarks,
and last-read positions under one versioned local key. Progress export follows
`platform/schemas/progress.schema.json`; its optional `ui_state` contains the
depth map and reading UI records. Imports preserve this state, and a storage
failure never hides the static chapter content. EPUB bookmarks and reflowed page
positions remain the responsibility of the EPUB reader rather than this web UI.
