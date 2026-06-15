"""Browser session/profile support for the S9 assignment.

The shipped Session 9 browser skill intentionally stopped at public pages.
Assignment work extends the precondition layer with explicit session state:
callers can load cookies/localStorage from a Playwright storage-state file,
save the post-run state, or use a persistent user-data directory.

No credentials live here. This module only decides where Playwright should
load/save browser state when the caller supplies metadata.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CODE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_ROOT = CODE_ROOT / "state" / "browser_profiles"


def _as_bool(value: Any, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def safe_profile_name(name: str) -> str:
    """Return a filesystem-safe profile name, preserving readability."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "default"


def resolve_assignment_path(value: str | Path, *, base: Path = CODE_ROOT) -> Path:
    """Resolve metadata paths relative to the assignment code directory."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path


@dataclass(frozen=True)
class BrowserSessionConfig:
    """Resolved browser-state settings for one Browser skill invocation."""

    profile: str | None = None
    storage_state: Path | None = None
    save_storage_state: Path | None = None
    user_data_dir: Path | None = None
    headless: bool = True

    @classmethod
    def from_metadata(
        cls,
        metadata: dict[str, Any],
        *,
        profile_root: Path = DEFAULT_PROFILE_ROOT,
    ) -> "BrowserSessionConfig":
        profile_name = metadata.get("browser_profile") or metadata.get("profile")
        safe_name = safe_profile_name(str(profile_name)) if profile_name else None

        storage_state = metadata.get("storage_state") or metadata.get("auth_storage_state")
        save_storage_state = metadata.get("save_storage_state")
        user_data_dir = metadata.get("user_data_dir")

        if safe_name:
            profile_root.mkdir(parents=True, exist_ok=True)
            default_state = profile_root / f"{safe_name}.json"
            storage_path = (
                resolve_assignment_path(storage_state)
                if storage_state else default_state
            )
            save_path = (
                resolve_assignment_path(save_storage_state)
                if save_storage_state else default_state
            )
        else:
            storage_path = resolve_assignment_path(storage_state) if storage_state else None
            save_path = (
                resolve_assignment_path(save_storage_state)
                if save_storage_state else None
            )

        return cls(
            profile=safe_name,
            storage_state=storage_path,
            save_storage_state=save_path,
            user_data_dir=resolve_assignment_path(user_data_dir) if user_data_dir else None,
            headless=_as_bool(metadata.get("headless"), default=True),
        )

    def new_context_options(self, **base_options: Any) -> dict[str, Any]:
        """Options for browser.new_context(...).

        Missing profile files are treated as an empty fresh profile when the
        profile was named with `browser_profile`. Explicit `storage_state`
        paths are only used when the file exists, so a first authenticated
        run can create them with `save_storage_state`.
        """
        opts = dict(base_options)
        if self.storage_state and self.storage_state.exists():
            opts["storage_state"] = str(self.storage_state)
        return opts

    def output_metadata(self) -> dict[str, str | None | bool]:
        return {
            "profile": self.profile,
            "storage_state_path": str(self.save_storage_state or self.storage_state)
            if (self.save_storage_state or self.storage_state) else None,
            "user_data_dir": str(self.user_data_dir) if self.user_data_dir else None,
            "headless": self.headless,
        }

    async def save_context(self, context: Any) -> None:
        if not self.save_storage_state:
            return
        self.save_storage_state.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(self.save_storage_state))
