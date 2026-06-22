from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import _candidate_order
from providers import OllamaProvider, _ollama_disable_thinking, build_providers, model_capabilities


IMAGE_MESSAGES = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "What is in this image?"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}},
        ],
    }
]


def test_ollama_uses_vision_model_for_image_messages() -> None:
    provider = OllamaProvider("text-model", vision_model="vision-model")

    assert provider._select_model([{"role": "user", "content": "hello"}]) == "text-model"
    assert provider._select_model(IMAGE_MESSAGES) == "vision-model"
    assert provider._select_model(IMAGE_MESSAGES, model="request-override") == "request-override"


def test_ollama_vision_model_marks_provider_vision_capable(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "text-model")
    monkeypatch.setenv("VISION_OLLAMA_MODEL", "vision-model")

    providers = build_providers(cache_store=None)

    assert providers["ollama"].vision_model == "vision-model"
    assert providers["ollama"].capabilities["vision"] is True
    assert model_capabilities("ollama", "text-model", {}, "vision-model")["vision"] is True


def test_agent_pin_is_preference_not_hard_override() -> None:
    class RouterStub:
        order = ["ollama", "groq", "gemini"]

        def candidates(self, provider):
            return [provider]

    assert _candidate_order(RouterStub(), provider=None, agent_pin="gemini") == [
        "gemini",
        "ollama",
        "groq",
    ]
    assert _candidate_order(RouterStub(), provider="ollama", agent_pin="gemini") == ["ollama"]


def test_qwen_ollama_thinking_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_THINK", raising=False)
    assert _ollama_disable_thinking("qwen3.6:35b-mlx") is True
    assert _ollama_disable_thinking("gemma4:31b-mlx") is False

    monkeypatch.setenv("OLLAMA_THINK", "true")
    assert _ollama_disable_thinking("qwen3.6:35b-mlx") is False
