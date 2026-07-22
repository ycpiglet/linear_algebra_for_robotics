from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "platform" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import artifact_inventory  # noqa: E402

FIXTURE_CONSUMER = "content/concepts/testing/example.qmd"
FIXTURE_OUTPUT = "assets/figures/example.svg"
FIXTURE_DEBT_IDENTITY = f"{FIXTURE_CONSUMER}::{FIXTURE_OUTPUT}"
FIXTURE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" role="img" '
    'aria-labelledby="title description">'
    '<title id="title">Example</title><desc id="description">Example figure</desc>'
    '<path d="M 0 0 L 1 1"/></svg>\n'
)


def write_project(
    tmp_path: Path,
    *,
    reference: str | None = None,
    baseline: dict[str, list[str]] | None = None,
    production: str = "manual",
    generated_svg: str = FIXTURE_SVG,
) -> tuple[Path, dict]:
    root = tmp_path / "repository"
    schema_path = root / artifact_inventory.SCHEMA_PATH
    schema_path.parent.mkdir(parents=True)
    shutil.copy2(ROOT / artifact_inventory.SCHEMA_PATH, schema_path)

    output_path = root / FIXTURE_OUTPUT
    output_path.parent.mkdir(parents=True)
    output_path.write_text(FIXTURE_SVG, encoding="utf-8")
    consumer_path = root / FIXTURE_CONSUMER
    consumer_path.parent.mkdir(parents=True)
    consumer_path.write_text(
        reference
        or "![설명하는 캡션](../../../assets/figures/example.svg)"
        '{#fig-example fig-alt="충분한 대체 텍스트"}\n',
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project]\nlicense = { text = "CC-BY-NC-SA-4.0" }\n',
        encoding="utf-8",
    )

    generator = None
    sources = [FIXTURE_OUTPUT]
    if production == "generated":
        generator_path = root / "scripts/generate_example.py"
        generator_path.parent.mkdir(parents=True)
        generator_path.write_text(
            "from pathlib import Path\n"
            "output = Path(__file__).resolve().parents[1] / "
            "'assets/figures/example.svg'\n"
            f"output.write_text({generated_svg!r}, encoding='utf-8')\n",
            encoding="utf-8",
        )
        (root / "uv.lock").write_text("fixture lock\n", encoding="utf-8")
        sources = ["scripts/generate_example.py"]
        generator = {
            "command": ["python", "scripts/generate_example.py"],
            "lockfile": "uv.lock",
            "normalizer": "svg-v1",
        }

    debt = {key: [] for key in artifact_inventory.DEBT_KEYS}
    if baseline:
        debt.update(baseline)
    manifest = {
        "schema_version": 1,
        "scope": {
            "inventory_roots": list(artifact_inventory.EXPECTED_INVENTORY_ROOTS),
            "consumer_globs": list(artifact_inventory.EXPECTED_CONSUMER_GLOBS),
        },
        "legacy_baseline": {
            "id": "legacy-test",
            "captured_on": "2026-07-23",
            "debt": debt,
        },
        "artifacts": [
            {
                "id": "figure.example",
                "production": production,
                "sources": sources,
                "generator": generator,
                "output": FIXTURE_OUTPUT,
                "consumers": [FIXTURE_CONSUMER],
                "license": {
                    "spdx": "CC-BY-NC-SA-4.0",
                    "basis": "pyproject.toml",
                },
            }
        ],
    }
    manifest_path = root / artifact_inventory.MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return root, manifest


def write_manifest(root: Path, manifest: dict) -> None:
    (root / artifact_inventory.MANIFEST_PATH).write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def diagnostic_codes(result: artifact_inventory.AuditResult) -> set[str]:
    return {diagnostic.code for diagnostic in result.diagnostics}


def test_repository_inventory_and_legacy_baseline_are_exact() -> None:
    audit = artifact_inventory.audit_repository(ROOT)

    assert audit.diagnostics == ()
    assert {key: len(audit.debt[key]) for key in artifact_inventory.DEBT_KEYS} == {
        "missing_figure_id": 4,
        "missing_caption": 0,
        "missing_alt": 0,
        "missing_provenance": 0,
    }
    report = artifact_inventory.build_report(ROOT, audit)
    assert report["summary"] == {
        "artifacts": 12,
        "generated": 4,
        "manual": 8,
        "references": 12,
        "consumer_files": 3,
        "debt": {
            "missing_figure_id": 4,
            "missing_caption": 0,
            "missing_alt": 0,
            "missing_provenance": 0,
        },
    }


def test_representative_trace_spans_source_output_consumer_and_license() -> None:
    trace = artifact_inventory.trace_artifact("figure.jacobian-2r-geometry", ROOT)

    assert trace["production"] == "generated"
    assert trace["sources"] == [
        "scripts/generate_jacobian_2r_geometry_figure.py",
        "scripts/atlas_matplotlib_fonts.py",
        "scripts/build_atlas_native_fonts.py",
        "assets/fonts/AtlasSansKR-Regular.otf",
        "assets/fonts/AtlasSansKR-Bold.otf",
    ]
    assert trace["generator"] == {
        "command": ["python", "scripts/generate_jacobian_2r_geometry_figure.py"],
        "lockfile": "uv.lock",
        "normalizer": "svg-v1",
    }
    assert trace["output"] == "assets/figures/jacobian-2r-geometry.svg"
    assert trace["consumers"] == [
        {
            "path": "content/concepts/robotics/jacobian.qmd",
            "figure_id": "fig-jacobian-2r-geometry",
            "caption_present": True,
            "alt_present": True,
        }
    ]
    assert trace["license"] == {
        "spdx": "CC-BY-NC-SA-4.0",
        "basis": "pyproject.toml",
    }


def test_report_is_deterministic() -> None:
    first = json.dumps(
        artifact_inventory.build_report(ROOT),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    second = json.dumps(
        artifact_inventory.build_report(ROOT),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    assert first == second


def test_generated_assets_match_temporary_regeneration() -> None:
    outputs = {
        artifact["output"]
        for artifact in artifact_inventory.audit_repository(ROOT).manifest["artifacts"]
        if artifact["production"] == "generated"
    }
    before = {output: (ROOT / output).read_bytes() for output in outputs}

    regenerated, diagnostics = artifact_inventory.regenerate_repository(ROOT)

    assert diagnostics == ()
    assert {item.output for item in regenerated} == outputs
    assert {output: (ROOT / output).read_bytes() for output in outputs} == before


@pytest.mark.parametrize(
    ("reference", "debt_key"),
    [
        (
            '![캡션](../../../assets/figures/example.svg){fig-alt="대체 텍스트"}\n',
            "missing_figure_id",
        ),
        (
            '![](../../../assets/figures/example.svg){#fig-example fig-alt="대체 텍스트"}\n',
            "missing_caption",
        ),
        (
            "![캡션](../../../assets/figures/example.svg){#fig-example}\n",
            "missing_alt",
        ),
    ],
)
def test_new_id_caption_or_alt_debt_is_rejected(
    tmp_path: Path,
    reference: str,
    debt_key: str,
) -> None:
    root, _ = write_project(tmp_path, reference=reference)

    result = artifact_inventory.audit_repository(root)

    assert "debt.regression" in diagnostic_codes(result)
    assert result.debt[debt_key] == (FIXTURE_DEBT_IDENTITY,)


def test_reference_without_an_attribute_block_cannot_evade_the_gate(tmp_path: Path) -> None:
    root, _ = write_project(
        tmp_path,
        reference="![캡션](../../../assets/figures/example.svg)\n",
    )

    result = artifact_inventory.audit_repository(root)

    assert "debt.regression" in diagnostic_codes(result)
    assert result.debt["missing_figure_id"] == (FIXTURE_DEBT_IDENTITY,)
    assert result.debt["missing_alt"] == (FIXTURE_DEBT_IDENTITY,)


def test_unmanifested_output_is_new_missing_provenance_debt(tmp_path: Path) -> None:
    root, _ = write_project(tmp_path)
    (root / "assets/figures/untracked.svg").write_text(FIXTURE_SVG, encoding="utf-8")

    result = artifact_inventory.audit_repository(root)

    assert {"inventory.unmanifested", "debt.regression"}.issubset(diagnostic_codes(result))
    assert result.debt["missing_provenance"] == ("assets/figures/untracked.svg",)


def test_resolved_legacy_debt_requires_an_explicit_baseline_update(tmp_path: Path) -> None:
    root, _ = write_project(
        tmp_path,
        baseline={"missing_figure_id": [FIXTURE_DEBT_IDENTITY]},
    )

    result = artifact_inventory.audit_repository(root)

    assert "baseline.stale" in diagnostic_codes(result)


def test_manual_artifact_cannot_claim_a_generator(tmp_path: Path) -> None:
    root, manifest = write_project(tmp_path)
    manifest["artifacts"][0]["generator"] = {
        "command": ["python", "scripts/generate_example.py"],
        "lockfile": "uv.lock",
        "normalizer": "svg-v1",
    }
    write_manifest(root, manifest)

    result = artifact_inventory.audit_repository(root)

    assert "schema.invalid" in diagnostic_codes(result)


def test_invalid_stable_artifact_id_is_rejected(tmp_path: Path) -> None:
    root, manifest = write_project(tmp_path)
    manifest["artifacts"][0]["id"] = "unstable ID"
    write_manifest(root, manifest)

    result = artifact_inventory.audit_repository(root)

    assert "schema.invalid" in diagnostic_codes(result)


def test_schema_cannot_be_weakened_with_the_manifest(tmp_path: Path) -> None:
    root, _ = write_project(tmp_path)
    schema_path = root / artifact_inventory.SCHEMA_PATH
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["$defs"]["artifact"]["required"].remove("sources")
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    result = artifact_inventory.audit_repository(root)

    assert "schema.unavailable" in diagnostic_codes(result)


def test_fenced_example_is_not_treated_as_a_consumer(tmp_path: Path) -> None:
    root, _ = write_project(tmp_path)
    consumer = root / FIXTURE_CONSUMER
    consumer.write_text(
        consumer.read_text(encoding="utf-8")
        + "```markdown\n"
        + '![예시](../../../assets/figures/not-real.svg){fig-alt="예시"}\n'
        + "```\n",
        encoding="utf-8",
    )

    result = artifact_inventory.audit_repository(root)

    assert result.diagnostics == ()


def test_regeneration_detects_structural_drift(tmp_path: Path) -> None:
    changed_svg = FIXTURE_SVG.replace("Example figure", "Changed figure")
    root, _ = write_project(
        tmp_path,
        production="generated",
        generated_svg=changed_svg,
    )

    regenerated, diagnostics = artifact_inventory.regenerate_repository(root)

    assert regenerated == ()
    assert {diagnostic.code for diagnostic in diagnostics} == {"regeneration.drift"}
