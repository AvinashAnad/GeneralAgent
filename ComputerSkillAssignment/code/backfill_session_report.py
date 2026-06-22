"""Backfill a session-level Visible Browser Replay Report.

Usage:
    python backfill_session_report.py s8-98541541
    python backfill_session_report.py s8-98541541 s8-6eb853e1
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from browser.replay_report import write_session_visible_browser_report
from persistence import SessionStore


ROOT = Path(__file__).resolve().parent
SESSIONS_ROOT = ROOT / "state" / "sessions"


def backfill(session_id: str) -> int:
    store = SessionStore(session_id)
    graph = store.read_graph()
    if graph is None:
        print(f"{session_id}: no graph.json found", file=sys.stderr)
        return 2
    query = store.read_query()
    result = write_session_visible_browser_report(
        session_id=session_id,
        query=query,
        graph_nodes=graph.nodes,
        sessions_root=SESSIONS_ROOT,
        started_at=time.time(),
    )
    report = result.output["visible_browser_report"]
    analysis = result.output.get("query_analysis_report") or {}
    print(f"{session_id}: {report['html']}")
    if analysis.get("markdown"):
        print(f"{session_id}: {analysis['markdown']}")
    return 0


def main() -> int:
    sessions = sys.argv[1:]
    if not sessions:
        print("usage: python backfill_session_report.py <session-id> [...]", file=sys.stderr)
        return 2
    status = 0
    for session_id in sessions:
        status = max(status, backfill(session_id))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
