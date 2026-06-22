"""Desktop-control skill built on top of the long-running cua-driver daemon."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from browser.client import V9Client
from schemas import AgentResult, ComputerOutput, NodeSpec

from .client import (
    AppUnavailableError,
    CuaDriverClient,
    CuaDriverError,
    DriverUnavailableError,
    PermissionsRequiredError,
    permission_guidance,
)
from .perception import (
    extract_ax_candidates,
    has_too_many_candidates,
    is_opaque_electron_tree,
    summarize_state,
)
from .vision import choose_vision_action, draw_numbered_grid


ROOT = Path(__file__).resolve().parent.parent
ELECTRON_APPS = {
    "visual studio code", "vscode", "code", "cursor", "slack", "discord",
    "notion", "linear", "obsidian", "microsoft teams", "teams", "1password",
}

ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "reason"],
    "properties": {
        "action": {
            "type": "string",
            "enum": ["click", "double_click", "type_text", "press_key", "hotkey", "set_value", "wait", "done"],
        },
        "element_index": {"type": "integer"},
        "text": {"type": "string"},
        "key": {"type": "string"},
        "keys": {"type": "array", "items": {"type": "string"}},
        "modifiers": {"type": "array", "items": {"type": "string"}},
        "value": {"type": "string"},
        "x": {"type": "integer"},
        "y": {"type": "integer"},
        "success": {"type": "boolean"},
        "content": {"type": "string"},
        "reason": {"type": "string"},
    },
}


class ComputerSkill:
    NAME = "computer"

    def __init__(
        self,
        *,
        driver: CuaDriverClient | None = None,
        gateway_url: str = "http://localhost:8109",
        artifacts_root: str | Path | None = None,
        session: str | None = None,
        provider_pin: str | None = None,
        vision_provider_pin: str | None = None,
    ):
        self.driver = driver or CuaDriverClient()
        self.gateway_url = gateway_url
        self.artifacts_root = Path(artifacts_root) if artifacts_root else ROOT / "state" / "computer"
        self.session = session
        # None means "let gateway routing decide". Set COMPUTER_PROVIDER_PIN or
        # COMPUTER_VISION_PROVIDER_PIN when testing a specific local/VLM model.
        self.provider_pin = provider_pin or os.getenv("COMPUTER_PROVIDER_PIN") or None
        self.vision_provider_pin = vision_provider_pin or os.getenv("COMPUTER_VISION_PROVIDER_PIN") or None

    async def run(self, node: NodeSpec) -> AgentResult:
        t0 = time.time()
        md = node.metadata or {}
        goal = str(md.get("goal") or md.get("question") or "").strip()
        if not goal and node.inputs:
            goal = str(node.inputs[0])
        goal = goal or "complete the requested desktop task"

        app = _clean(md.get("app"))
        bundle_id = _clean(md.get("bundle_id"))
        max_steps = int(md.get("max_steps") or 12)
        run_dir = self.artifacts_root / f"computer_{int(t0)}"
        run_dir.mkdir(parents=True, exist_ok=True)
        recording_dir = run_dir / "trajectory"
        actions: list[dict[str, Any]] = []
        output = ComputerOutput(
            goal=goal, app=app, bundle_id=bundle_id, path="ax",
            actions=actions, recording_dir=str(recording_dir),
        )
        recording_started = False
        try:
            self.driver.ensure_daemon()
            self.driver.start_recording(recording_dir)
            recording_started = True
            target = self._resolve_target(md)
            output.app = target["app"]
            output.bundle_id = target["bundle_id"]
            output.pid = target["pid"]
            output.window_id = target["window_id"]
            output.path = target["path"]

            calc = _calculator_expression(goal, target.get("app"))
            if calc:
                content, final_state = self._run_calculator(target, goal, calc, actions, run_dir, max_steps)
            elif target["path"] == "page":
                content, final_state = await self._run_page_mode(target, goal, actions, run_dir)
            else:
                content, final_state = await self._run_ax_loop(target, goal, actions, run_dir, md, max_steps)

            output.actions = actions
            output.turns = len(actions)
            output.content = content
            output.final_state = summarize_state(final_state)
            return AgentResult(success=True, agent_name=self.NAME, output=output.model_dump(), elapsed_s=time.time() - t0)
        except PermissionsRequiredError as e:
            return self._pack_error(output, actions, str(e), "permissions_required", t0)
        except DriverUnavailableError as e:
            return self._pack_error(output, actions, str(e), "driver_unavailable", t0)
        except AppUnavailableError as e:
            return self._pack_error(output, actions, str(e), "app_unavailable", t0)
        except CuaDriverError as e:
            return self._pack_error(output, actions, str(e), "interaction_failed", t0)
        except Exception as e:  # noqa: BLE001
            return self._pack_error(output, actions, f"exception: {type(e).__name__}: {e}", "interaction_failed", t0)
        finally:
            if recording_started:
                try:
                    self.driver.stop_recording()
                except Exception:
                    pass

    def _pack_error(self, output: ComputerOutput, actions: list[dict[str, Any]], msg: str, code: str, started: float) -> AgentResult:
        output.actions = actions
        output.turns = len(actions)
        return AgentResult(
            success=False,
            agent_name=self.NAME,
            output=output.model_dump(),
            error=msg,
            error_code=code,  # type: ignore[arg-type]
            elapsed_s=time.time() - started,
        )

    def _resolve_target(self, md: dict[str, Any]) -> dict[str, Any]:
        app = _clean(md.get("app"))
        bundle_id = _clean(md.get("bundle_id"))
        title = _clean(md.get("window_title"))
        pid = _as_int(md.get("pid"))
        window_id = _as_int(md.get("window_id"))
        page_mode = str(md.get("force_path") or "").lower() == "page" or _is_electron(app)

        if not pid:
            rec = self._find_app(app, bundle_id)
            pid = _record_pid(rec)
        if not pid and (app or bundle_id):
            args: dict[str, Any] = {}
            if bundle_id:
                args["bundle_id"] = bundle_id
            elif app:
                args["name"] = app
            if page_mode:
                args["electron_debugging_port"] = int(md.get("electron_debugging_port") or 9222)
            try:
                launch = self.driver.call("launch_app", args)
            except CuaDriverError as e:
                if self.driver.os_name == "macos" and app and not page_mode:
                    self._open_macos_app(app, bundle_id)
                    launch = {}
                else:
                    raise AppUnavailableError(f"could not launch {app or bundle_id}: {e}") from e
            pid = _as_int(launch.get("pid")) or self._poll_for_pid(app, bundle_id)
            window_id = window_id or self._choose_window(_records(launch, "windows"), pid, title)
        if not pid:
            raise AppUnavailableError(f"could not find running app {app or bundle_id or '(unspecified)'}")
        if self.driver.os_name == "macos" and app:
            self.driver.activate_macos_app(app)
            time.sleep(0.25)
        window_id = window_id or self._select_window(pid, title)
        if not window_id:
            raise AppUnavailableError(f"could not find a visible window for pid {pid}")
        try:
            self.driver.call("bring_to_front", _with_session(self.session, {"pid": pid, "window_id": window_id}))
        except CuaDriverError:
            pass
        return {"app": app, "bundle_id": bundle_id, "pid": pid, "window_id": window_id, "path": "page" if page_mode else "ax"}

    def _find_app(self, app: str | None, bundle_id: str | None) -> dict[str, Any] | None:
        payload = self.driver.call("list_apps", {})
        app_l = (app or "").lower()
        bundle_l = (bundle_id or "").lower()
        best = None
        for rec in _records(payload, "apps", "applications"):
            if not isinstance(rec, dict):
                continue
            name_l = (_record_name(rec) or "").lower()
            bundle_rec = (_record_bundle(rec) or "").lower()
            if bundle_l and bundle_rec == bundle_l:
                return rec
            if app_l and (name_l == app_l or app_l in name_l or name_l in app_l):
                if _record_pid(rec):
                    return rec
                best = best or rec
        return best

    def _poll_for_pid(self, app: str | None, bundle_id: str | None) -> int | None:
        for _ in range(12):
            time.sleep(0.5)
            pid = _record_pid(self._find_app(app, bundle_id))
            if pid:
                return pid
        return None

    def _select_window(self, pid: int, title: str | None) -> int | None:
        for _ in range(12):
            wid = self._choose_window(_records(self.driver.call("list_windows", {}), "windows"), pid, title)
            if wid:
                return wid
            time.sleep(0.5)
        return None

    def _choose_window(self, records: list[Any], pid: int | None, title: str | None) -> int | None:
        title_l = (title or "").lower()
        scored: list[tuple[float, int]] = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            rec_pid = _as_int(rec.get("pid") or rec.get("owner_pid") or rec.get("kCGWindowOwnerPID"))
            if pid and rec_pid and rec_pid != pid:
                continue
            wid = _as_int(rec.get("window_id") or rec.get("id") or rec.get("kCGWindowNumber"))
            if not wid:
                continue
            rec_title = str(rec.get("title") or rec.get("name") or rec.get("window_title") or "").lower()
            if title_l and title_l in rec_title:
                return wid
            bounds = rec.get("bounds") if isinstance(rec.get("bounds"), dict) else {}
            width = _as_float(bounds.get("width")) or 0.0
            height = _as_float(bounds.get("height")) or 0.0
            area = width * height
            is_on_screen = rec.get("is_on_screen")
            score = min(area / 1000.0, 500.0)
            if is_on_screen is True:
                score += 1000.0
            elif is_on_screen is False:
                score -= 200.0
            if rec_title:
                score += 300.0
            if width >= 100 and height >= 100:
                score += 200.0
            if height <= 40 and width >= 500:
                score -= 600.0
            if _as_int(rec.get("layer")) == 0:
                score += 20.0
            scored.append((score, wid))
        if not scored:
            return None
        return max(scored, key=lambda item: item[0])[1]

    def _open_macos_app(self, app: str, bundle_id: str | None) -> None:
        attempts = [["open", "-a", app]]
        if bundle_id:
            attempts.insert(0, ["open", "-b", bundle_id])
        last = ""
        for cmd in attempts:
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
            if proc.returncode == 0:
                return
            last = (proc.stderr or proc.stdout or "").strip()
        raise AppUnavailableError(f"macOS open failed for {app}: {last}")

    def _run_calculator(self, target: dict[str, Any], goal: str, calc: tuple[str, str],
                        actions: list[dict[str, Any]], run_dir: Path, max_steps: int) -> tuple[str, dict[str, Any]]:
        expression, expected = calc
        final_state: dict[str, Any] = {}
        for key_action in _calculator_key_actions(expression):
            if len(actions) >= max_steps:
                raise CuaDriverError(f"Calculator task exceeded max_steps={max_steps}")
            final_state = self._scan_act_verify(
                turn=len(actions) + 1,
                target=target,
                action=key_action,
                actions=actions,
                run_dir=run_dir,
                outcome_hint="advanced",
            )
        final_state = self._scan_act_verify(
            turn=len(actions) + 1,
            target=target,
            action={"action": "press_key", "key": "return", "reason": "Evaluate the expression and show the result."},
            actions=actions,
            run_dir=run_dir,
            outcome_hint="done",
        )
        if not _calculator_display_contains(final_state, expected):
            raise CuaDriverError(f"Calculator verification failed for goal={goal!r}; expected {expected}")
        time.sleep(float(os.getenv("COMPUTER_RESULT_HOLD_SECONDS", "10")))
        return expected, final_state

    async def _run_ax_loop(self, target: dict[str, Any], goal: str, actions: list[dict[str, Any]],
                           run_dir: Path, md: dict[str, Any], max_steps: int) -> tuple[str, dict[str, Any]]:
        client = V9Client(base_url=self.gateway_url, agent="computer", session=self.session)
        allow_vision = bool(md.get("allow_vision", True))
        query = _clean(md.get("perception_query"))
        for _ in range(max_steps):
            try:
                scan, _ = self._scan(target, "ax", query, run_dir, len(actions) + 1, "scan")
            except CuaDriverError:
                if allow_vision:
                    return await self._run_vision_turn(target, goal, actions, run_dir, client)
                raise
            if is_opaque_electron_tree(scan) and _is_electron(target.get("app")):
                target["path"] = "page"
                return await self._run_page_mode(target, goal, actions, run_dir)
            decision = await self._choose_action(client, goal, scan)
            final_state = self._scan_act_verify(
                turn=len(actions) + 1,
                target=target,
                action=decision,
                actions=actions,
                run_dir=run_dir,
                pre_scanned_state=scan,
            )
            if decision.get("action") == "done" or decision.get("success"):
                return str(decision.get("content") or _best_state_text(final_state)), final_state
        raise CuaDriverError(f"desktop task did not complete within {max_steps} turns")

    async def _choose_action(self, client: V9Client, goal: str, state: dict[str, Any]) -> dict[str, Any]:
        markdown = str(state.get("tree_markdown") or "")
        summary = summarize_state(state)
        tree_text = json.dumps(summary, indent=2) if has_too_many_candidates(markdown) else markdown[:14000]
        prompt = (
            "Choose exactly one next desktop action through cua-driver. "
            "Use element_index values only from the current scan. Prefer done "
            "when the goal is already verified.\n\n"
            f"GOAL: {goal}\n\nSUMMARY:\n{json.dumps(summary, indent=2)}\n\nAX TREE:\n{tree_text}"
        )
        result = await client.chat(
            prompt,
            schema=ACTION_SCHEMA,
            schema_name="ComputerAction",
            max_tokens=700,
            provider=self.provider_pin,
        )
        decision = getattr(result, "parsed", None) or _json_from_text(getattr(result, "text", ""))
        if not isinstance(decision, dict) or not decision.get("action"):
            raise CuaDriverError("computer action model did not return a valid action")
        return decision

    async def _run_page_mode(self, target: dict[str, Any], goal: str,
                             actions: list[dict[str, Any]], run_dir: Path) -> tuple[str, dict[str, Any]]:
        turn = len(actions) + 1
        args = {"action": "get_text", "pid": target["pid"], "window_id": target["window_id"]}
        scan = self.driver.call("page", args)
        scan_ref = self._write_state(run_dir, turn, "scan_page", scan)
        verify = self.driver.call("page", args)
        verify_ref = self._write_state(run_dir, turn, "verify_page", verify)
        content = str(verify.get("text") or verify.get("content") or scan.get("text") or scan.get("content") or "")
        actions.append({
            "turn": turn,
            "phase": "scan-act-verify",
            "scan": {"tool": "page", "args": args, "summary": {"chars": len(content)}, "raw_ref": scan_ref},
            "decision": {"action": "done", "reason": "Captured Electron/page text."},
            "act": {"tool": "page", "args": {"action": "get_text"}, "result": {"chars": len(content)}},
            "verify": {"tool": "page", "args": args, "summary": {"chars": len(content)}, "raw_ref": verify_ref},
            "outcome": "done" if content else "failed",
        })
        if not content:
            raise CuaDriverError(f"page mode did not return text for goal: {goal}")
        return content, {"tree_markdown": content, "element_count": 1, "pid": target["pid"], "window_id": target["window_id"]}

    async def _run_vision_turn(self, target: dict[str, Any], goal: str,
                               actions: list[dict[str, Any]], run_dir: Path, client: V9Client) -> tuple[str, dict[str, Any]]:
        turn = len(actions) + 1
        screenshot = run_dir / f"turn_{turn:02d}_vision_raw.png"
        state, scan_args = self._scan(target, "vision", None, run_dir, turn, "scan", screenshot_path=screenshot, handle_empty=False)
        marked = run_dir / f"turn_{turn:02d}_vision_marked.png"
        marks = draw_numbered_grid(state.get("screenshot_file_path") or screenshot, marked)
        decision = await choose_vision_action(client, image_path=marked, goal=goal, marks=marks, provider=self.vision_provider_pin)
        action = {"action": decision.get("action") or "click", "x": decision["x"], "y": decision["y"], "reason": decision.get("thinking", "vision coordinate click")}
        final_state = self._scan_act_verify(turn=turn, target=target, action=action, actions=actions, run_dir=run_dir, pre_scanned_state=state, pre_scan_args=scan_args)
        return _best_state_text(final_state), final_state

    def _scan_act_verify(self, *, turn: int, target: dict[str, Any], action: dict[str, Any],
                         actions: list[dict[str, Any]], run_dir: Path, outcome_hint: str | None = None,
                         pre_scanned_state: dict[str, Any] | None = None,
                         pre_scan_args: dict[str, Any] | None = None) -> dict[str, Any]:
        scan = pre_scanned_state
        scan_args = pre_scan_args
        if scan is None or scan_args is None:
            scan, scan_args = self._scan(target, "ax", None, run_dir, turn, "scan")
        scan_ref = self._write_state(run_dir, turn, "scan", scan)
        tool, act_args = self._action_to_tool(target, action, scan)
        act_error = None
        try:
            if tool == "done":
                act_result = {"done": True}
            elif tool == "wait":
                time.sleep(float(action.get("seconds") or 0.5))
                act_result = {"waited": True}
            else:
                act_result = self.driver.call(tool, act_args)
        except Exception as e:  # noqa: BLE001
            act_error = f"{type(e).__name__}: {e}"
            act_result = {"error": act_error}
        time.sleep(0.35)
        try:
            verify, verify_args = self._scan(target, "ax", None, run_dir, turn, "verify")
        except Exception as e:  # noqa: BLE001
            verify = {"error": f"{type(e).__name__}: {e}", "pid": target["pid"], "window_id": target["window_id"], "element_count": 0}
            verify_args = {"pid": target["pid"], "window_id": target["window_id"], "capture_mode": "ax"}
        verify_ref = self._write_state(run_dir, turn, "verify", verify)
        outcome = "failed" if act_error or verify.get("error") else outcome_hint or ("done" if action.get("action") == "done" or action.get("success") else "advanced")
        actions.append({
            "turn": turn,
            "phase": "scan-act-verify",
            "scan": {"tool": "get_window_state", "args": _compact(scan_args), "summary": summarize_state(scan), "raw_ref": scan_ref},
            "decision": dict(action),
            "act": {"tool": tool, "args": _compact(act_args), "result": _compact(act_result)},
            "verify": {"tool": "get_window_state", "args": _compact(verify_args), "summary": summarize_state(verify), "raw_ref": verify_ref},
            "outcome": outcome,
        })
        if act_error:
            raise CuaDriverError(f"{tool} failed: {act_error}", tool=tool)
        if verify.get("error"):
            raise CuaDriverError(f"verify scan failed after {tool}: {verify['error']}", tool="get_window_state")
        return verify

    def _scan(self, target: dict[str, Any], capture_mode: str, query: str | None, run_dir: Path,
              turn: int, phase: str, *, screenshot_path: str | Path | None = None,
              handle_empty: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
        args: dict[str, Any] = {"pid": target["pid"], "window_id": target["window_id"], "capture_mode": capture_mode}
        if query and capture_mode != "vision":
            args["query"] = query
        if self.session:
            args["session"] = self.session
        if screenshot_path:
            args["screenshot_out_file"] = str(screenshot_path)
        elif capture_mode in {"som", "vision"}:
            args["screenshot_out_file"] = str(run_dir / f"turn_{turn:02d}_{phase}.png")
        state = self.driver.call("get_window_state", args)
        if handle_empty and capture_mode != "vision" and int(state.get("element_count") or 0) == 0:
            state = self._handle_empty_tree(target, args, state)
        return state, args

    def _handle_empty_tree(self, target: dict[str, Any], args: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        app = target.get("app") or ""
        if self.driver.os_name == "macos" and app:
            self.driver.activate_macos_app(app)
            time.sleep(0.8)
            rescanned = self.driver.call("get_window_state", args)
            if int(rescanned.get("element_count") or 0) > 0:
                return rescanned
        if self.driver.os_name == "linux" and _looks_like_qt(app):
            raise CuaDriverError("element_count=0 for a likely Qt app on Linux. Relaunch with QT_ACCESSIBILITY=1.")
        if _is_electron(app) or is_opaque_electron_tree(state):
            raise CuaDriverError("element_count=0/opaque Electron tree. Relaunch with electron_debugging_port=9222 and use page mode.")
        raise CuaDriverError(f"element_count=0 after scan. {permission_guidance(self.driver.os_name)}")

    def _action_to_tool(self, target: dict[str, Any], decision: dict[str, Any], scan: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        action = str(decision.get("action") or "").lower()
        if action in {"done", "wait"}:
            return action, {}
        base = _with_session(self.session, {"pid": target["pid"]})
        if action in {"click", "double_click"}:
            args = dict(base)
            if "element_index" in decision:
                self._validate_element_index(decision["element_index"], scan)
                args.update({"window_id": target["window_id"], "element_index": int(decision["element_index"])})
            else:
                args.update({"window_id": target["window_id"], "x": int(decision["x"]), "y": int(decision["y"])})
            return action, args
        if action == "type_text":
            args = dict(base)
            args.update({"window_id": target["window_id"], "text": str(decision.get("text") or "")})
            if "element_index" in decision:
                self._validate_element_index(decision["element_index"], scan)
                args["element_index"] = int(decision["element_index"])
            return "type_text", args
        if action == "press_key":
            args = dict(base)
            args.update({"window_id": target["window_id"], "key": str(decision.get("key") or "return")})
            if decision.get("modifiers"):
                args["modifiers"] = [str(m) for m in decision.get("modifiers") or []]
            if "element_index" in decision:
                self._validate_element_index(decision["element_index"], scan)
                args["element_index"] = int(decision["element_index"])
            return "press_key", args
        if action == "hotkey":
            return "hotkey", dict(base, window_id=target["window_id"], keys=[str(k) for k in decision.get("keys") or []])
        if action == "set_value":
            self._validate_element_index(decision.get("element_index"), scan)
            return "set_value", dict(base, window_id=target["window_id"], element_index=int(decision["element_index"]), value=str(decision.get("value") or ""))
        raise CuaDriverError(f"unsupported computer action: {action}")

    def _validate_element_index(self, idx: Any, state: dict[str, Any]) -> None:
        idx_i = int(idx)
        candidates = extract_ax_candidates(str(state.get("tree_markdown") or ""))
        if candidates and idx_i not in {c.element_index for c in candidates}:
            raise CuaDriverError(f"element_index {idx_i} was not present in the latest scan")

    def _write_state(self, run_dir: Path, turn: int, phase: str, state: dict[str, Any]) -> str:
        path = run_dir / f"turn_{turn:02d}_{phase}.json"
        path.write_text(json.dumps(state, indent=2, default=str))
        return str(path)


def _clean(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _records(payload: Any, *keys: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            val = payload.get(key)
            if isinstance(val, list):
                return val
    return []


def _record_pid(rec: Any) -> int | None:
    return _as_int(rec.get("pid") or rec.get("process_id") or rec.get("processIdentifier")) if isinstance(rec, dict) else None


def _record_name(rec: Any) -> str | None:
    return _clean(rec.get("name") or rec.get("localized_name") or rec.get("display_name")) if isinstance(rec, dict) else None


def _record_bundle(rec: Any) -> str | None:
    return _clean(rec.get("bundle_id") or rec.get("bundleIdentifier") or rec.get("bundle")) if isinstance(rec, dict) else None


def _with_session(session: str | None, args: dict[str, Any]) -> dict[str, Any]:
    if session:
        args = dict(args)
        args["session"] = session
    return args


def _compact(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return {k: ("<base64 omitted>" if "base64" in k else v) for k, v in value.items() if k != "tree_markdown"}


def _json_from_text(text: str) -> dict[str, Any]:
    start, end = (text or "").find("{"), (text or "").rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return {}
    return {}


def _calculator_expression(goal: str, app: str | None) -> tuple[str, str] | None:
    if app and "calculator" not in app.lower() and "calculator" not in goal.lower():
        return None
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*([xX*×+\-/÷])\s*(-?\d+(?:\.\d+)?)", goal)
    if not m:
        return None
    left, op, right = m.groups()
    try:
        a, b = Decimal(left), Decimal(right)
        if op in {"x", "X", "*", "×"}:
            value, expr = a * b, f"{left}*{right}"
        elif op == "+":
            value, expr = a + b, f"{left}+{right}"
        elif op == "-":
            value, expr = a - b, f"{left}-{right}"
        else:
            value, expr = a / b, f"{left}/{right}"
    except (InvalidOperation, ZeroDivisionError) as e:
        raise CuaDriverError(f"could not compute arithmetic expression in goal: {e}") from e
    return expr, _format_decimal(value)


def _format_decimal(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(value.quantize(Decimal(1)))
    return format(value.normalize(), "f")


def _calculator_display_contains(state: dict[str, Any], expected: str) -> bool:
    markdown = str(state.get("tree_markdown") or "")
    display_values = re.findall(r"AXStaticText[^\"\n]*\"([^\"]+)\"", markdown)
    display_values += re.findall(r"AXTextField[^\"\n]*\"([^\"]+)\"", markdown)
    display_values += re.findall(r"AXValue\s*=\s*\"([^\"]+)\"", markdown)
    compact_expected = _normalize_display_text(expected)
    for value in display_values:
        if _normalize_display_text(value) == compact_expected:
            return True
    return False


def _normalize_display_text(value: str) -> str:
    without_controls = "".join(ch for ch in value if unicodedata.category(ch) != "Cf")
    return re.sub(r"[\s,]", "", without_controls)


def _calculator_key_actions(expression: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for ch in expression:
        if ch.isdigit() or ch == ".":
            actions.append({"action": "press_key", "key": ch, "reason": f"Press Calculator key {ch}."})
        elif ch == "*":
            actions.append({"action": "press_key", "key": "8", "modifiers": ["shift"], "reason": "Press multiply."})
        elif ch == "+":
            actions.append({"action": "press_key", "key": "=", "modifiers": ["shift"], "reason": "Press plus."})
        elif ch == "-":
            actions.append({"action": "press_key", "key": "-", "reason": "Press minus."})
        elif ch == "/":
            actions.append({"action": "press_key", "key": "/", "reason": "Press divide."})
        else:
            raise CuaDriverError(f"unsupported Calculator key: {ch!r}")
    return actions


def _best_state_text(state: dict[str, Any]) -> str:
    markdown = str(state.get("tree_markdown") or "")
    static = re.findall(r"AXStaticText[^\"\n]*\"([^\"]+)\"", markdown)
    return " ".join(static[:12]) if static else markdown[:2000]


def _is_electron(app: str | None) -> bool:
    app_l = (app or "").lower()
    return any(name in app_l for name in ELECTRON_APPS)


def _looks_like_qt(app: str | None) -> bool:
    app_l = (app or "").lower()
    return any(token in app_l for token in ("qt", "qgis", "kdenlive", "krita", "anki"))
