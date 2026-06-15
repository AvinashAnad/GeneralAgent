from __future__ import annotations

from typing import Any

from paths import ensure_s9_path

ensure_s9_path()

from schemas import AgentResult  # noqa: E402


def normalize_browser_path(result: AgentResult | dict[str, Any]) -> str:
    """Surface gateway-blocks as the report-facing Browser path `blocked`."""
    if isinstance(result, AgentResult):
        if result.error_code == "gateway_blocked":
            return "blocked"
        output = result.output or {}
    else:
        if result.get("error_code") == "gateway_blocked":
            return "blocked"
        output = result.get("output") or result
    path = output.get("path") if isinstance(output, dict) else None
    return str(path or "unknown")


def visible_actions_count(action_turns: list[dict[str, Any]]) -> int:
    """Count user-visible actions; passive waits and terminal done are logs."""
    count = 0
    for turn in action_turns or []:
        for action in turn.get("actions") or []:
            if action.get("type") not in {"wait", "done"}:
                count += 1
    return count
