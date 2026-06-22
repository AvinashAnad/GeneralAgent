"""Small subprocess client for the local cua-driver CLI."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


ACK_TEXT_TOOLS = {
    "bring_to_front",
    "click",
    "double_click",
    "drag",
    "hotkey",
    "move_cursor",
    "press_key",
    "right_click",
    "scroll",
    "set_agent_cursor_enabled",
    "set_agent_cursor_motion",
    "set_agent_cursor_style",
    "set_value",
    "start_recording",
    "stop_recording",
    "type_text",
}


class CuaDriverError(RuntimeError):
    def __init__(self, message: str, *, tool: str | None = None):
        super().__init__(message)
        self.tool = tool


class DriverUnavailableError(CuaDriverError):
    pass


class PermissionsRequiredError(CuaDriverError):
    pass


class AppUnavailableError(CuaDriverError):
    pass


def permission_guidance(os_name: str | None = None) -> str:
    os_l = (os_name or "").lower()
    if os_l in {"macos", "darwin"}:
        return (
            "cua-driver needs macOS Accessibility and Screen Recording grants. "
            "Run `~/.local/bin/cua-driver permissions grant`, then confirm with "
            "`~/.local/bin/cua-driver diagnose`."
        )
    if os_l == "linux":
        return (
            "cua-driver could not inspect the app. Check AT-SPI accessibility, "
            "X11/Wayland portal support, and toolkit accessibility settings."
        )
    if os_l == "windows":
        return (
            "cua-driver could not inspect the app. Check UI Automation access; "
            "elevated/admin apps may require launching the agent elevated too."
        )
    return "cua-driver could not inspect the app. Check OS accessibility and screen-recording permissions."


class CuaDriverClient:
    """Thin wrapper around `cua-driver call <tool> <json>`."""

    def __init__(self, binary: str | None = None):
        self.binary = (
            binary
            or os.getenv("CUA_DRIVER_BIN")
            or os.getenv("CUA_DRIVER")
            or str(Path.home() / ".local/bin/cua-driver")
        )
        self.os_name = self._detect_os()

    @staticmethod
    def _detect_os() -> str:
        import platform

        system = platform.system().lower()
        return "macos" if system == "darwin" else system

    def ensure_daemon(self) -> None:
        if not Path(self.binary).exists():
            raise DriverUnavailableError(f"cua-driver binary not found at {self.binary}")
        proc = subprocess.run([self.binary, "status"], text=True, capture_output=True, timeout=15)
        if self._status_is_running(proc):
            return
        try:
            subprocess.Popen(
                [self.binary, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:  # noqa: BLE001
            raise DriverUnavailableError(f"could not start cua-driver serve: {e}") from e
        deadline = time.time() + 8.0
        while time.time() < deadline:
            time.sleep(0.4)
            proc = subprocess.run([self.binary, "status"], text=True, capture_output=True, timeout=15)
            if self._status_is_running(proc):
                return
        diag = subprocess.run([self.binary, "diagnose"], text=True, capture_output=True, timeout=30)
        text = "\n".join([proc.stdout, proc.stderr, diag.stdout, diag.stderr]).strip()
        if any(s in text.lower() for s in ("permission", "screen recording", "accessibility")):
            raise PermissionsRequiredError(permission_guidance(self.os_name))
        raise DriverUnavailableError(text or "cua-driver daemon is not running")

    @staticmethod
    def _status_is_running(proc: subprocess.CompletedProcess) -> bool:
        text = f"{proc.stdout}\n{proc.stderr}".lower()
        return proc.returncode == 0 and ("running" in text or "ok" in text)

    def call(self, tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = json.dumps(args or {})
        try:
            proc = subprocess.run(
                [self.binary, "call", tool, payload],
                text=True,
                capture_output=True,
                timeout=120,
            )
        except FileNotFoundError as e:
            raise DriverUnavailableError(f"cua-driver binary not found at {self.binary}") from e
        except subprocess.TimeoutExpired as e:
            raise CuaDriverError(f"cua-driver call timed out: {tool}", tool=tool) from e

        text = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        if proc.returncode != 0:
            msg = err or text or f"cua-driver call failed: {tool}"
            if any(s in msg.lower() for s in ("permission", "screen recording", "accessibility")):
                raise PermissionsRequiredError(permission_guidance(self.os_name))
            raise CuaDriverError(msg, tool=tool)
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            for line in reversed(text.splitlines()):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        if tool in ACK_TEXT_TOOLS:
            return {"ok": True, "raw": text}
        raise CuaDriverError(f"cua-driver returned non-JSON for {tool}: {text[:500]}", tool=tool)

    def start_recording(self, output_dir: str | Path) -> dict[str, Any]:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return self.call("start_recording", {"output_dir": str(output_dir)})

    def stop_recording(self) -> dict[str, Any]:
        return self.call("stop_recording", {})

    def activate_macos_app(self, app_name: str) -> None:
        subprocess.run(
            ["osascript", "-e", f'tell application "{app_name}" to activate'],
            text=True,
            capture_output=True,
            timeout=15,
        )
