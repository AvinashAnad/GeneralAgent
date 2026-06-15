"""Assignment-side provider selection for gateway calls.

The gateway's `agent_routing.yaml` can pin an agent like `planner` to Gemini.
That is useful as a preference, but it also narrows the request to one
provider before the worker failover ring can consider Nvidia/Groq/Cerebras.

This module keeps the change local to `s9assignment`: a skill may define
`provider_order` in `agent_config.yaml`; before the call we inspect
`llm_gatewayV9 /v1/status` and explicitly pin the first provider in that
order with enough live RPM/TPM/cooldown room.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from gateway import GATEWAY_URL, LLM


RETRYABLE_STATUS = {429, 502, 503, 504}


@dataclass(frozen=True)
class ProviderChoice:
    provider: str | None
    skipped: list[str] = field(default_factory=list)
    note: str = ""


def estimate_tokens(*, prompt: str | None = None,
                    messages: list[dict] | None = None,
                    max_tokens: int = 0) -> int:
    chars = len(prompt or "")
    for m in messages or []:
        content = m.get("content", "")
        if isinstance(content, str):
            chars += len(content)
        else:
            chars += len(str(content))
    return max(1, chars // 4) + int(max_tokens or 0)


def _availability(status: dict[str, Any], provider: str,
                  est_tokens: int) -> tuple[bool, str]:
    live = (status.get("live") or {}).get(provider)
    limits = (status.get("limits") or {}).get(provider) or {}
    if not live:
        return False, "not wired"
    if float(live.get("backoff_remaining") or 0) > 0:
        return False, f"backoff {float(live.get('backoff_remaining') or 0):.1f}s"
    if float(live.get("cooldown_remaining") or 0) > 0:
        return False, f"cooldown {float(live.get('cooldown_remaining') or 0):.1f}s"
    if int(live.get("rpm_used") or 0) >= int(live.get("rpm_limit") or limits.get("rpm") or 0):
        return False, "RPM limit"
    rpd_limit = int(live.get("rpd_limit") or limits.get("rpd") or 0)
    if rpd_limit and int(live.get("rpd_used") or 0) >= rpd_limit:
        return False, "RPD limit"
    tpm_limit = int(live.get("tpm_limit") or limits.get("tpm") or 0)
    if tpm_limit and int(live.get("tpm_used") or 0) + est_tokens > tpm_limit:
        return False, "TPM limit"
    max_ctx = int(limits.get("max_ctx") or live.get("max_ctx") or 0)
    if max_ctx and est_tokens > max_ctx:
        return False, f"context {est_tokens} > {max_ctx}"
    daily_cap = live.get("tokens_per_day") or limits.get("tokens_per_day")
    if daily_cap and int(live.get("tokens_today") or 0) + est_tokens > int(daily_cap):
        return False, "daily token cap"
    return True, "available"


def choose_provider(provider_order: list[str], *,
                    prompt: str | None = None,
                    messages: list[dict] | None = None,
                    max_tokens: int = 0,
                    gateway_url: str = GATEWAY_URL) -> ProviderChoice:
    order = [p for p in provider_order if p]
    if not order:
        return ProviderChoice(None)
    est = estimate_tokens(prompt=prompt, messages=messages, max_tokens=max_tokens)
    try:
        status = httpx.get(f"{gateway_url}/v1/status", timeout=2.0).json()
    except Exception as e:  # noqa: BLE001
        return ProviderChoice(order[0], note=f"status unavailable: {type(e).__name__}")

    skipped: list[str] = []
    for provider in order:
        ok, why = _availability(status, provider, est)
        if ok:
            return ProviderChoice(provider, skipped=skipped)
        skipped.append(f"{provider}:{why}")
    return ProviderChoice(order[0], skipped=skipped,
                          note="all configured providers reported unavailable")


def chat_with_provider_order(*, provider_order: list[str],
                             prompt: str | None = None,
                             messages: list[dict] | None = None,
                             agent: str,
                             session: str,
                             max_tokens: int,
                             temperature: float,
                             tools: list[dict] | None = None,
                             tool_choice: Any = None) -> dict:
    choice = choose_provider(provider_order, prompt=prompt, messages=messages,
                             max_tokens=max_tokens)
    skipped_names = {s.split(":", 1)[0] for s in choice.skipped}
    ordered: list[str] = []
    if choice.provider:
        ordered.append(choice.provider)
    ordered.extend(
        p for p in provider_order
        if p and p not in ordered and p not in skipped_names
    )
    ordered.extend(
        p for p in provider_order
        if p and p not in ordered
    )

    last_error: Exception | None = None
    for provider in ordered:
        if choice.skipped and provider == choice.provider:
            print(f"[routing] {agent}: using {provider}; skipped {', '.join(choice.skipped)}")
        elif choice.note and provider == choice.provider:
            print(f"[routing] {agent}: using {provider}; {choice.note}")
        try:
            return LLM().chat(
                prompt=prompt,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                agent=agent,
                session=session,
                provider=provider,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code not in RETRYABLE_STATUS:
                raise
            print(f"[routing] {agent}: {provider} failed with {e.response.status_code}; trying next provider")
        except httpx.HTTPError as e:
            last_error = e
            print(f"[routing] {agent}: {provider} transport error; trying next provider")

    if last_error:
        raise last_error
    return LLM().chat(
        prompt=prompt,
        messages=messages,
        agent=agent,
        session=session,
        max_tokens=max_tokens,
        temperature=temperature,
    )
