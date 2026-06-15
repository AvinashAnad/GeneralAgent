from __future__ import annotations

from pathlib import Path

import yaml

from paths import PROJECT_ROOT

CONFIG_PATH = PROJECT_ROOT / "agent_config.yaml"


class ProjectSkill:
    def __init__(self, name: str, cfg: dict):
        self.name = name
        self.prompt_path = (PROJECT_ROOT / cfg["prompt"]).resolve()
        self.description = cfg.get("description", "")
        self.tools_allowed: list[str] = cfg.get("tools_allowed", []) or []
        self.internal_successors: list[str] = cfg.get("internal_successors", []) or []
        self.critic: bool = bool(cfg.get("critic", False))
        self.provider_pin: str | None = cfg.get("provider_pin")
        self.temperature: float = float(cfg.get("temperature", 0.3))
        self.max_tokens: int = int(cfg.get("max_tokens", 2048))

    def prompt_template(self) -> str:
        if not self.prompt_path.exists():
            return f"You are the {self.name} skill. (Prompt file missing.)"
        return self.prompt_path.read_text(encoding="utf-8")


class ProjectSkillRegistry:
    def __init__(self, config_path: Path = CONFIG_PATH):
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self._skills: dict[str, ProjectSkill] = {
            name: ProjectSkill(name, raw) for name, raw in cfg.items()
        }

    def get(self, name: str) -> ProjectSkill:
        if name not in self._skills:
            raise KeyError(f"unknown project skill: {name}")
        return self._skills[name]

    def names(self) -> list[str]:
        return list(self._skills)
