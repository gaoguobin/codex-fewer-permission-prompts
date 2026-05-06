#!/usr/bin/env python3
"""Skill-local wrapper for the packaged CLI."""

from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


try:
    from codex_fewer_permission_prompts.cli import main
except ModuleNotFoundError:
    sys.path.insert(0, str(_repo_root() / "src"))
    from codex_fewer_permission_prompts.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
