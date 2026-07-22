"""Pre-cutover URL and saved-reader-state compatibility contracts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS_JS = ROOT / "assets/js/atlas.js"

NODE_HARNESS = r"""
const fs = require('node:fs');
const vm = require('node:vm');

const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const storageKey = 'robotics-math-atlas.progress.v1';
const storage = new Map([[storageKey, JSON.stringify(payload.state)]]);
let hooks = null;
const page = new URL(payload.siteRoot + 'content/concepts/robotics/jacobian.html');
const context = {
  console,
  URL,
  URLSearchParams,
  CustomEvent: function CustomEvent() {},
  localStorage: {
    getItem: (key) => storage.has(key) ? storage.get(key) : null,
    setItem: (key, value) => storage.set(key, String(value)),
  },
  document: {
    baseURI: page.href,
    readyState: 'loading',
    documentElement: { dataset: {} },
    addEventListener: () => {},
  },
  window: {
    __ROBOTICS_MATH_ATLAS_ROOT__: payload.siteRoot,
    __ATLAS_TEST_HOOK__: (value) => { hooks = value; },
    location: page,
  },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context, {
  filename: process.argv[1],
});
if (!hooks) throw new Error('Atlas URL compatibility test hook was not installed.');

const direct = JSON.parse(JSON.stringify(payload.state));
const changed = hooks.migrateProgressPaths(direct, payload.siteRoot, page.origin);
const secondChanged = hooks.migrateProgressPaths(direct, payload.siteRoot, page.origin);
process.stdout.write(JSON.stringify({
  automatic: JSON.parse(storage.get(storageKey)),
  direct,
  changed,
  secondChanged,
  unsafeExternal: hooks.safeSavedUrl('https://example.com/keep.html'),
  unsafeMalformed: hooks.safeSavedUrl('http://['),
}));
"""


def run_migration(state: dict[str, object], site_root: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "-e", NODE_HARNESS, str(ATLAS_JS)],
        input=json.dumps({"state": state, "siteRoot": site_root}),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def legacy_state() -> dict[str, object]:
    return {
        "version": 1,
        "concepts": {"robot.jacobian": 3},
        "depth": {"robot.jacobian": "derivation"},
        "favorites": {
            "/linear_algebra_for_robotics/content/legacy.html": {
                "url": "/linear_algebra_for_robotics/content/legacy.html",
                "title": "legacy",
                "updatedAt": "2026-07-20T00:00:00Z",
            },
            "/robotics-math-atlas/content/legacy.html": {
                "url": "/robotics-math-atlas/content/legacy.html",
                "title": "newer canonical copy",
                "updatedAt": "2026-07-21T00:00:00Z",
            },
            "/linear_algebra_for_robotics/content/absolute.html": {
                "url": (
                    "https://ycpiglet.github.io/linear_algebra_for_robotics/"
                    "content/absolute.html?mode=deep#proof"
                ),
                "title": "absolute",
                "updatedAt": "2026-07-20T01:00:00Z",
            },
            "external": {
                "url": "https://example.com/linear_algebra_for_robotics/keep.html",
                "title": "external",
                "updatedAt": "2026-07-20T02:00:00Z",
            },
        },
        "bookmarks": {
            "/linear_algebra_for_robotics/review/content/legacy.html#derivation": {
                "url": (
                    "/linear_algebra_for_robotics/review/content/legacy.html"
                    "#derivation"
                ),
                "sectionId": "derivation",
                "updatedAt": "2026-07-20T03:00:00Z",
            }
        },
        "lastRead": {
            "/linear_algebra_for_robotics/content/legacy.html": {
                "url": (
                    "https://ycpiglet.github.io/linear_algebra_for_robotics/"
                    "content/legacy.html#derivation"
                ),
                "ratio": 0.42,
                "updatedAt": "2026-07-20T04:00:00Z",
            }
        },
        "updatedAt": "2026-07-20T05:00:00Z",
    }


def assert_prefix_neutral_migration(result: dict[str, object]) -> None:
    migrated = result["direct"]

    assert result["changed"] is True
    assert result["secondChanged"] is False
    assert result["automatic"] == migrated
    assert result["unsafeExternal"] == "#"
    assert result["unsafeMalformed"] == "#"
    assert migrated["version"] == 1
    assert migrated["concepts"] == {"robot.jacobian": 3}
    assert migrated["depth"] == {"robot.jacobian": "derivation"}
    assert migrated["updatedAt"] == "2026-07-20T05:00:00Z"

    favorites = migrated["favorites"]
    assert "/linear_algebra_for_robotics/content/legacy.html" not in favorites
    assert "/robotics-math-atlas/content/legacy.html" not in favorites
    assert favorites["content/legacy.html"]["title"] == (
        "newer canonical copy"
    )
    assert favorites["content/absolute.html"]["url"] == (
        "content/absolute.html?mode=deep#proof"
    )
    assert favorites["external"]["url"] == (
        "https://example.com/linear_algebra_for_robotics/keep.html"
    )
    assert list(migrated["bookmarks"]) == ["review/content/legacy.html#derivation"]
    assert list(migrated["lastRead"]) == ["content/legacy.html"]
    assert migrated["migrations"] == {"savedPathsV1": True}


def test_old_and_new_pages_roots_produce_the_same_prefix_neutral_state() -> None:
    old_result = run_migration(
        legacy_state(), "https://ycpiglet.github.io/linear_algebra_for_robotics/"
    )
    new_result = run_migration(
        legacy_state(), "https://ycpiglet.github.io/robotics-math-atlas/"
    )

    assert_prefix_neutral_migration(old_result)
    assert_prefix_neutral_migration(new_result)
    assert old_result["direct"] == new_result["direct"]


def test_already_migrated_state_is_idempotent() -> None:
    first = run_migration(
        legacy_state(), "https://ycpiglet.github.io/linear_algebra_for_robotics/"
    )["direct"]
    second = run_migration(
        first, "https://ycpiglet.github.io/robotics-math-atlas/"
    )

    assert second["changed"] is False
    assert second["secondChanged"] is False
    assert second["direct"] == first
    assert second["automatic"] == first


def test_import_and_initial_load_share_the_same_idempotent_migration() -> None:
    script = ATLAS_JS.read_text(encoding="utf-8")

    assert "const STORAGE_KEY = 'robotics-math-atlas.progress.v1';" in script
    assert script.count("migrateProgressPaths(progress)") == 2
    assert "schema_version: '1.0.0'" in script
    assert "last_read: progress.lastRead" in script
