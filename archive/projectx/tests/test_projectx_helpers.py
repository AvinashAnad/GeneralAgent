from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from browser_report import normalize_browser_path, visible_actions_count
from project_registry import ProjectSkillRegistry
from schemas import AgentResult


def test_gateway_blocked_normalizes_to_blocked() -> None:
    result = AgentResult(
        success=False,
        agent_name="browser",
        output={"path": "extract"},
        error_code="gateway_blocked",
    )
    assert normalize_browser_path(result) == "blocked"


def test_visible_actions_count_excludes_wait_and_done() -> None:
    turns = [
        {"turn": 1, "actions": [{"type": "type"}, {"type": "key"}]},
        {"turn": 2, "actions": [{"type": "wait"}, {"type": "click"}]},
        {"turn": 3, "actions": [{"type": "done", "success": True}]},
    ]
    assert visible_actions_count(turns) == 3


def test_project_registry_exposes_browser_and_researcher() -> None:
    registry = ProjectSkillRegistry()
    assert "browser" in registry.names()
    assert "researcher" in registry.names()
    assert "Browser successors" in registry.get("researcher").prompt_template()
