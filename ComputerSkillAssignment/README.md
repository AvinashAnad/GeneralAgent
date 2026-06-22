# ComputerSkill Assignment Runtime

Clean assignment copy assembled from:

- `../S9SharedCodeVisibleAgent/code` -> `code`
- `../llm_gatewayV9` -> `llm_gatewayV9`

The existing Browser skill remains in `code/browser` and is still registered
as `browser`. The new desktop automation work is isolated in `code/computer`
and registered as `computer`.

## Run Gateway

```bash
cd /Users/avi/Documents/SessionNotes/Session10/ComputerAgent/ComputerSkillAssignment/llm_gatewayV9
./run.sh
```

Current local model config:

```text
OLLAMA_MODEL=qwen3.6:35b-mlx
VISION_OLLAMA_MODEL=nemotron3:33b
LLM_ORDER=ollama,groq,openrouter
```

The gateway disables Ollama thinking by default for qwen/deepseek/gpt-oss style
models so Planner/Formatter calls return visible JSON/text instead of spending
the whole response budget on hidden reasoning. Set `OLLAMA_THINK=true` only
when you intentionally want that behavior.

## Run Calculator Smoke

In a second terminal:

```bash
cd /Users/avi/Documents/SessionNotes/Session10/ComputerAgent/ComputerSkillAssignment/code
COMPUTER_RESULT_HOLD_SECONDS=10 uv run python flow.py "Use the local Mac Calculator app to compute 11 * 11, verify the result, and answer with only the number."
```

Expected final answer:

```text
121
```

## What Was Added

- `computer` skill using `cua-driver`
- native trajectory recording
- semantic scan-act-verify ledger in `ComputerOutput.actions`
- macOS Calculator deterministic key path
- visible-window selection, avoiding menu-bar pseudo windows
- display verification that strips hidden Unicode direction marks
- `element_count == 0` handling hooks
- Electron/page-mode escape hatch hooks
- vision fallback hooks
- Planner desktop fallback when a model emits an empty plan
- Browser registration and Browser source kept intact

## Verification

```bash
cd /Users/avi/Documents/SessionNotes/Session10/ComputerAgent/ComputerSkillAssignment/code
.venv/bin/python -m pytest -q tests/test_computer_skill.py tests/test_recovery.py tests/test_recovery_amnesia.py tests/test_critic_autoinsert.py

cd /Users/avi/Documents/SessionNotes/Session10/ComputerAgent/ComputerSkillAssignment/llm_gatewayV9
.venv/bin/python -m pytest -q tests/test_gateway_routing_config.py
.venv/bin/python -m py_compile main.py providers.py router.py tests/test_gateway_routing_config.py
```

Latest result:

```text
code focused suite: 39 passed
gateway routing/config: 4 passed
gateway compile: passed
```
