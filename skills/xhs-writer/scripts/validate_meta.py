#!/usr/bin/env python3
"""Compatibility entrypoint that validates V2 content JSON.

Legacy meta.json files are intentionally rejected because they lack account,
run, provenance, rights, and approval fields.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_meta.py CONTENT_ARTIFACT.json", file=sys.stderr)
        return 2
    artifact = Path(sys.argv[1]).resolve()
    core = Path(__file__).resolve().parents[2] / "xhs-workflow" / "scripts" / "workflow_cli.py"
    if not core.is_file():
        print(f"ERROR: 缺少 xhs-workflow 核心校验器：{core}", file=sys.stderr)
        return 2
    return subprocess.run([sys.executable, str(core), "validate", str(artifact)], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
