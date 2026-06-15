from __future__ import annotations

import asyncio
import os
import time
from functools import wraps

from paths import ensure_s9_path

DEFAULT_DELAY_SECONDS = 0.0
DEFAULT_PROVIDER = "ollama"
DEFAULT_BROWSER_PROVIDER = "auto"
DELAY_ENV_VAR = "PROJECTX_LLM_CALL_DELAY_SECONDS"
PROVIDER_ENV_VAR = "PROJECTX_LLM_PROVIDER"
BROWSER_PROVIDER_ENV_VAR = "PROJECTX_BROWSER_LLM_PROVIDER"
PROJECT_SKILL_AGENTS = {
    "planner",
    "researcher",
    "distiller",
    "critic",
    "formatter",
    "retriever",
    "summariser",
    "coder",
    "sandbox_executor",
}


def _configured_delay(seconds: float | None) -> float:
    if seconds is not None:
        return max(0.0, float(seconds))
    raw = os.getenv(DELAY_ENV_VAR)
    if raw is None:
        return DEFAULT_DELAY_SECONDS
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_DELAY_SECONDS


def _configured_provider(
    provider: str | None = None,
    *,
    env_var: str = PROVIDER_ENV_VAR,
    default: str = DEFAULT_PROVIDER,
) -> str | None:
    raw = provider if provider is not None else os.getenv(env_var, default)
    name = (raw or "").strip()
    if not name or name.lower() in {"auto", "none", "default"}:
        return None
    return name


def install_project_llm_delay(
    seconds: float | None = None,
    provider: str | None = None,
    browser_provider: str | None = None,
) -> tuple[float, str | None, str | None]:
    """Provider-pin Project X gateway calls, with optional local delay.

    This wraps the client methods used by the existing S9 skill dispatcher and
    Browser skill. It affects only the current Project X process.
    """
    delay_s = _configured_delay(seconds)
    provider_name = _configured_provider(provider)
    browser_provider_name = _configured_provider(
        browser_provider,
        env_var=BROWSER_PROVIDER_ENV_VAR,
        default=DEFAULT_BROWSER_PROVIDER,
    )
    ensure_s9_path()

    import gateway as s9_gateway
    from browser.client import V9Client

    if not getattr(s9_gateway.LLM.chat, "_projectx_delay_wrapped", False):
        original_chat = s9_gateway.LLM.chat

        @wraps(original_chat)
        def delayed_chat(self, *args, **kwargs):
            agent = kwargs.get("agent")
            is_project_skill = isinstance(agent, str) and agent in PROJECT_SKILL_AGENTS
            if is_project_skill and delay_s > 0:
                time.sleep(delay_s)
            if is_project_skill and provider_name:
                kwargs["provider"] = provider_name
            return original_chat(self, *args, **kwargs)

        delayed_chat._projectx_delay_wrapped = True
        s9_gateway.LLM.chat = delayed_chat

    for method_name in ("chat", "vision"):
        original = getattr(V9Client, method_name)
        if getattr(original, "_projectx_delay_wrapped", False):
            continue

        @wraps(original)
        async def delayed_async(self, *args, __original=original, **kwargs):
            if delay_s > 0:
                await asyncio.sleep(delay_s)
            if browser_provider_name:
                kwargs["provider"] = browser_provider_name
            return await __original(self, *args, **kwargs)

        delayed_async._projectx_delay_wrapped = True
        setattr(V9Client, method_name, delayed_async)

    return delay_s, provider_name, browser_provider_name
