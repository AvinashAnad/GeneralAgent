from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
S9_CODE_ROOT = WORKSPACE_ROOT / "S9SharedCode" / "code"
S9_SESSIONS_ROOT = S9_CODE_ROOT / "state" / "sessions"
REPORTS_ROOT = PROJECT_ROOT / "reports"


def ensure_s9_path() -> None:
    p = str(S9_CODE_ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)
