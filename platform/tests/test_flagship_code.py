"""Execute the copy-and-paste Python examples in the three flagship chapters."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHAPTERS = (
    ROOT / "content/concepts/robotics/jacobian.qmd",
    ROOT / "content/concepts/statistics/maximum-likelihood-estimation.qmd",
    ROOT / "content/concepts/estimation/kalman-filter.qmd",
)
PYTHON_BLOCK = re.compile(r"^```python\s*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)


def test_flagship_python_examples_compile_and_run_in_reading_order() -> None:
    optional_blocks = 0

    for chapter in CHAPTERS:
        blocks = PYTHON_BLOCK.findall(chapter.read_text(encoding="utf-8"))
        assert blocks, f"No Python examples found in {chapter.relative_to(ROOT)}"
        namespace: dict[str, object] = {"__name__": "__atlas_example__"}

        for index, source in enumerate(blocks, start=1):
            label = f"{chapter.relative_to(ROOT)}#python-{index}"
            ast.parse(source, filename=label)
            if re.search(r"^import jax(?:\s|$)", source, flags=re.MULTILINE):
                # JAX is intentionally an optional `ad-opt` dependency. Syntax is still
                # checked here; the dependency-specific smoke test runs separately.
                optional_blocks += 1
                continue
            exec(compile(source, label, "exec"), namespace)

    assert optional_blocks == 1
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'ad-opt = [' in project and '"jax>=0.5"' in project
