#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON_BIN=${PYTHON:-python3}
EXPECTED_RUNNER_SHA256='c92c57aa987418fa735daccbd49fca5953af84feafe25fdab433fbb36daf8c00'
EXPECTED_MANIFEST_SHA256='c01f9870c97867b7bb65a903205252c509e19a191b6b9a11250ac59206356316'

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "error: Python 3 is required; install Python 3.12 and try again" >&2
  exit 1
fi

"$PYTHON_BIN" - "$ROOT" "$EXPECTED_RUNNER_SHA256" "$EXPECTED_MANIFEST_SHA256" <<'PY'
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
expected = {
    root / "scripts/dev.py": sys.argv[2],
    root / "scripts/toolchain.json": sys.argv[3],
}
for path, expected_hash in expected.items():
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise SystemExit(f"error: {path.relative_to(root)} does not match this reviewed wrapper")
PY

if [ "$#" -eq 0 ]; then
  set -- bootstrap
fi
exec "$PYTHON_BIN" "$ROOT/scripts/dev.py" "$@"
