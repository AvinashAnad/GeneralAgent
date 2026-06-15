import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import provider_routing
from provider_routing import choose_provider, estimate_tokens


def _status(**overrides):
    live = {
        "gemini": {
            "rpm_used": 15,
            "rpm_limit": 15,
            "rpd_used": 10,
            "rpd_limit": 1000,
            "tpm_used": 0,
            "tpm_limit": 250000,
            "tokens_today": 1000,
            "cooldown_remaining": 0,
            "backoff_remaining": 0,
        },
        "nvidia": {
            "rpm_used": 0,
            "rpm_limit": 40,
            "rpd_used": 0,
            "rpd_limit": 9999,
            "tpm_used": 0,
            "tpm_limit": 100000,
            "tokens_today": 0,
            "cooldown_remaining": 0,
            "backoff_remaining": 0,
        },
        "groq": {
            "rpm_used": 0,
            "rpm_limit": 30,
            "rpd_used": 0,
            "rpd_limit": 1000,
            "tpm_used": 0,
            "tpm_limit": 6000,
            "tokens_today": 0,
            "cooldown_remaining": 0,
            "backoff_remaining": 0,
        },
        "cerebras": {
            "rpm_used": 0,
            "rpm_limit": 30,
            "rpd_used": 0,
            "rpd_limit": 9999,
            "tpm_used": 0,
            "tpm_limit": 60000,
            "tokens_today": 0,
            "cooldown_remaining": 0,
            "backoff_remaining": 0,
        },
    }
    for provider, patch in overrides.items():
        live[provider].update(patch)
    return {
        "live": live,
        "limits": {
            "gemini": {"max_ctx": 1000000, "rpm": 15, "rpd": 1000, "tpm": 250000},
            "nvidia": {"max_ctx": 100000, "rpm": 40, "rpd": 9999, "tpm": 100000},
            "groq": {"max_ctx": 100000, "rpm": 30, "rpd": 1000, "tpm": 6000},
            "cerebras": {"max_ctx": 8000, "rpm": 30, "rpd": 9999, "tpm": 60000},
        },
    }


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def test_choose_provider_skips_saturated_gemini(monkeypatch):
    monkeypatch.setattr(
        provider_routing.httpx,
        "get",
        lambda *a, **k: _Resp(_status()),
    )

    choice = choose_provider(
        ["gemini", "nvidia", "groq", "cerebras"],
        prompt="hello",
        max_tokens=100,
    )

    assert choice.provider == "nvidia"
    assert choice.skipped == ["gemini:RPM limit"]


def test_choose_provider_skips_tpm_overflow(monkeypatch):
    monkeypatch.setattr(
        provider_routing.httpx,
        "get",
        lambda *a, **k: _Resp(_status(gemini={"rpm_used": 0, "tpm_used": 249950})),
    )

    choice = choose_provider(
        ["gemini", "nvidia"],
        prompt="x" * 400,
        max_tokens=100,
    )

    assert choice.provider == "nvidia"
    assert choice.skipped == ["gemini:TPM limit"]


def test_choose_provider_falls_back_to_first_when_status_unavailable(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("gateway down")

    monkeypatch.setattr(provider_routing.httpx, "get", boom)

    choice = choose_provider(["gemini", "nvidia"], prompt="hello", max_tokens=10)

    assert choice.provider == "gemini"
    assert "status unavailable" in choice.note


def test_estimate_tokens_counts_prompt_and_completion_budget():
    assert estimate_tokens(prompt="abcd" * 10, max_tokens=100) == 110
