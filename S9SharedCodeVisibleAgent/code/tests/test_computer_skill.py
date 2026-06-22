from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from computer.client import CuaDriverClient, CuaDriverError
from computer.perception import extract_ax_candidates
from computer.skill import ComputerSkill, _calculator_display_contains
from recovery import plan_recovery
from schemas import NodeSpec
from skills import SkillRegistry, _desktop_fallback_plan, _looks_like_desktop_query


class FakeDriver:
    def __init__(self, *, states: list[dict] | None = None, launch_error: bool = False):
        self.os_name = "macos"
        self.states = states or _calculator_states()
        self.launch_error = launch_error
        self.opened_by_macos = False
        self.calls: list[tuple[str, dict]] = []
        self.recording_started = False
        self.recording_stopped = False
        self.activated: list[str] = []
        self.fail_tool: str | None = None

    def ensure_daemon(self) -> None:
        self.calls.append(("ensure_daemon", {}))

    def start_recording(self, output_dir) -> dict:
        self.recording_started = True
        self.calls.append(("start_recording", {"output_dir": str(output_dir)}))
        return {"ok": True}

    def stop_recording(self) -> dict:
        self.recording_stopped = True
        self.calls.append(("stop_recording", {}))
        return {"ok": True}

    def activate_macos_app(self, app_name: str) -> None:
        self.activated.append(app_name)

    def call(self, tool: str, args: dict | None = None) -> dict:
        args = args or {}
        self.calls.append((tool, dict(args)))
        if tool == self.fail_tool:
            raise CuaDriverError(f"forced failure in {tool}", tool=tool)
        if tool == "list_apps":
            pid = 123 if self.opened_by_macos else None
            return {"apps": [{"name": "Calculator", "bundle_id": "com.apple.calculator", "pid": pid}]}
        if tool == "launch_app":
            if self.launch_error:
                raise CuaDriverError("NSWorkspace launch failed", tool="launch_app")
            return {"pid": 123, "name": "Calculator", "bundle_id": "com.apple.calculator", "windows": [{"window_id": 456, "pid": 123, "title": "Calculator"}]}
        if tool == "list_windows":
            return {"windows": [{"window_id": 456, "pid": 123, "title": "Calculator"}]}
        if tool == "bring_to_front":
            return {"ok": True}
        if tool == "get_window_state":
            if len(self.states) > 1:
                return self.states.pop(0)
            return self.states[0]
        if tool in {"press_key", "type_text", "click", "double_click", "hotkey", "set_value"}:
            return {"ok": True, "tool": tool}
        raise AssertionError(f"unexpected tool: {tool}")


def _calculator_states() -> list[dict]:
    buttons = '[element_index 1] AXButton "1"\n[element_index 2] AXButton "="'
    return [
        {"pid": 123, "window_id": 456, "title": "Calculator", "element_count": 2, "tree_markdown": buttons},
        {"pid": 123, "window_id": 456, "title": "Calculator", "element_count": 3, "tree_markdown": buttons + '\nAXStaticText "121"'},
    ]


def _node() -> NodeSpec:
    return NodeSpec(
        skill="computer",
        inputs=[],
        metadata={
            "goal": "Use the local Mac Calculator app to compute 11 * 11, verify the result, and answer with only the number.",
            "app": "Calculator",
            "bundle_id": "com.apple.calculator",
            "max_steps": 12,
        },
    )


@pytest.mark.asyncio
async def test_calculator_records_scan_act_verify_without_initial_clear(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("COMPUTER_RESULT_HOLD_SECONDS", "0")
    driver = FakeDriver()
    result = await ComputerSkill(driver=driver, artifacts_root=tmp_path, session="s-test").run(_node())
    assert result.success is True
    assert result.output["content"] == "121"
    assert driver.recording_started is True
    assert driver.recording_stopped is True
    tools = [name for name, _ in driver.calls]
    assert "type_text" not in tools
    assert "press_key" in tools
    pressed = [args.get("key") for name, args in driver.calls if name == "press_key"]
    assert pressed == ["1", "1", "8", "1", "1", "return"]
    last = result.output["actions"][-1]
    assert last["phase"] == "scan-act-verify"
    assert last["act"]["tool"] == "press_key"
    assert last["verify"]["tool"] == "get_window_state"


@pytest.mark.asyncio
async def test_recording_stops_when_action_fails_and_ledger_records_failed_turn(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("COMPUTER_RESULT_HOLD_SECONDS", "0")
    driver = FakeDriver()
    driver.fail_tool = "press_key"
    result = await ComputerSkill(driver=driver, artifacts_root=tmp_path).run(_node())
    assert result.success is False
    assert result.error_code == "interaction_failed"
    assert driver.recording_started is True
    assert driver.recording_stopped is True
    assert result.output["actions"][-1]["act"]["tool"] == "press_key"
    assert result.output["actions"][-1]["outcome"] == "failed"


@pytest.mark.asyncio
async def test_macos_open_fallback_when_launch_app_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("COMPUTER_RESULT_HOLD_SECONDS", "0")
    driver = FakeDriver(launch_error=True)

    def fake_run(cmd, text, capture_output, timeout):
        if cmd[:2] == ["open", "-b"]:
            return subprocess.CompletedProcess(cmd, 1, "", "bundle not found")
        if cmd[:2] == ["open", "-a"]:
            driver.opened_by_macos = True
            return subprocess.CompletedProcess(cmd, 0, "", "")
        raise AssertionError(cmd)

    monkeypatch.setattr("computer.skill.subprocess.run", fake_run)
    result = await ComputerSkill(driver=driver, artifacts_root=tmp_path).run(_node())
    assert result.success is True
    assert driver.opened_by_macos is True


def test_cua_client_accepts_non_json_action_ack(monkeypatch) -> None:
    def fake_run(cmd, text, capture_output, timeout):
        assert cmd[:3] == ["/tmp/cua-driver", "call", "press_key"]
        return subprocess.CompletedProcess(cmd, 0, "✅ \n", "")

    monkeypatch.setattr("computer.client.subprocess.run", fake_run)
    result = CuaDriverClient(binary="/tmp/cua-driver").call("press_key", {"pid": 1, "key": "escape"})
    assert result == {"ok": True, "raw": "✅"}


def test_calculator_verification_ignores_element_index_false_positive() -> None:
    state = {"tree_markdown": '- [121] AXMenuItem "Decimal Places"'}
    hidden_mark = chr(0x200E)
    assert _calculator_display_contains(state, "121") is False
    assert _calculator_display_contains({"tree_markdown": 'AXStaticText "121"'}, "121") is True
    assert _calculator_display_contains({"tree_markdown": f'AXStaticText = "{hidden_mark}121"'}, "121") is True


def test_choose_window_prefers_visible_app_window_over_menu_bar(tmp_path: Path) -> None:
    skill = ComputerSkill(driver=FakeDriver(), artifacts_root=tmp_path)
    records = [
        {
            "window_id": 549,
            "pid": 123,
            "title": "",
            "is_on_screen": False,
            "layer": 0,
            "bounds": {"width": 1920, "height": 30},
        },
        {
            "window_id": 537,
            "pid": 123,
            "title": "Calculator",
            "is_on_screen": True,
            "layer": 0,
            "bounds": {"width": 230, "height": 408},
        },
    ]
    assert skill._choose_window(records, pid=123, title=None) == 537


def test_ax_candidate_extraction_dedupes_rows() -> None:
    rows = extract_ax_candidates(
        '[element_index 4] AXButton "OK"\n[element_index 5] AXButton "OK"\n- [9] AXTextField "Search"'
    )
    assert [(r.element_index, r.role, r.label) for r in rows] == [
        (4, "AXButton", "OK"),
        (9, "AXTextField", "Search"),
    ]


def test_registry_and_planner_prompt_include_computer() -> None:
    root = Path(__file__).resolve().parent.parent
    assert "computer" in SkillRegistry().names()
    planner = (root / "prompts" / "planner.md").read_text()
    assert "desktop" in planner
    assert '"skill":"computer"' in planner


def test_empty_planner_desktop_fallback_routes_to_computer() -> None:
    query = "Use the local Mac Calculator app to compute 11 * 11"
    assert _looks_like_desktop_query(query) is True
    plan = _desktop_fallback_plan(query)
    assert [node["skill"] for node in plan["nodes"]] == ["computer", "formatter"]
    assert plan["nodes"][0]["metadata"]["app"] == "Calculator"
    assert plan["nodes"][1]["inputs"] == ["USER_QUERY", "n:desktop"]


def test_formatter_failure_skips_recovery_to_avoid_rerunning_desktop_actions() -> None:
    decision = plan_recovery(
        failed_skill="formatter",
        error_text="model returned invalid JSON",
        failed_node_id="n:9",
    )
    assert decision.action == "skip"
    assert "do not re-run upstream" in decision.note
