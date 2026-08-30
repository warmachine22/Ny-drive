#!/usr/bin/env python3
"""Backward-compatible Roach metadata check.

Deprecated since 0.5; scheduled for removal in 0.7. Use:

    python scripts/roach.py check
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
result = subprocess.run([sys.executable, str(ROOT / "scripts/roach.py"), "check"], cwd=ROOT)
raise SystemExit(result.returncode)
