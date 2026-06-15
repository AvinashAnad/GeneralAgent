1. unpin gemma to nvidia
2. critic explainer ehy failed
3. critic node cap 60
4. final result uncapped from 600
5. 

## s9assignment - S9SharedCode delta

Updated: 2026-06-13

This section records the intentional source, prompt, doc, and test changes in
`s9assignment` compared with `S9SharedCode`. Generated/runtime differences
such as `.venv`, `__pycache__`, `.DS_Store`, `state/sessions`, FAISS memory
files, logs, and usage counters are not treated as source changes.

### New files added in `s9assignment`

| File | What was added |
|---|---|
| `README.md` | Assignment-facing README with module summary, browser cascade, visible browser action evidence, provider failover, critic visibility, and Mermaid component map. |
| `ASSIGNMENT_9.md` | Checklist mapping assignment requirements to implementation files, including replay-visible browser actions and provider routing. |
| `code/provider_routing.py` | Assignment-local provider selection. Reads `llm_gatewayV9 /v1/status`, skips providers in cooldown/RPM/RPD/TPM/backoff/context/daily-cap states, pins the first available provider, and retries ordered providers on retryable gateway failures. |
| `code/browser/session.py` | Browser session/profile helper. Resolves `browser_profile`, `storage_state`, `save_storage_state`, `user_data_dir`, and `headless`; saves Playwright storage state when requested. |
| `code/tests/test_browser_assignment_features.py` | Tests browser profile metadata, storage-state resolution, gateway-block detection, and replay-visible `BrowserOutput` fields. |
| `code/tests/test_provider_routing.py` | Tests provider availability checks, Gemini saturation skip, TPM overflow skip, status-unavailable fallback, and token estimation. |
| `code/changes.md` | This change log. |
| `code/Query1.txt`, `code/Query2.txt`, `code/Query3.txt`, `code/Query4.txt` | Saved sample/live test queries used while validating the assignment. |
| `logs/browser.log` | Runtime browser log created during local runs; not core source. |

### Modified runtime/config files

| File | Difference from `S9SharedCode` |
|---|---|
| `code/agent_config.yaml` | Added Planner-only `provider_order: [gemini, nvidia, groq, cerebras]`. Updated Browser description to include profile/session metadata and authenticated-session use cases. |
| `code/skills.py` | Added `Skill.provider_order`. Standard non-tool LLM skills call `chat_with_provider_order(...)` only when configured; currently this is used by Planner. Browser dispatch remains isolated to `BrowserSkill.run(...)`. |
| `code/browser/driver.py` | Added typed `gateway_blocked` and `gateway_block_type` fields on `DriverResult` so rendered-page block detection can be surfaced cleanly. |
| `code/browser/skill.py` | Added browser profile/session support, storage-state save/load, persistent Chromium profile support, headless override, stealth/context options, extended block detection for geo/rate/access-denied cases, and replay-visible session metadata. Browser a11y remains pinned to Gemini for stable action loops. |
| `code/browser/__init__.py` | Exported `BrowserSessionConfig` and `safe_profile_name`. |
| `code/schemas.py` | Extended `BrowserOutput` with `profile`, `storage_state_path`, `user_data_dir`, and `block_type` so replay/report output can show session and gateway-block evidence. |
| `code/flow.py` | Prints Critic verdict/rationale inline. Removed final-answer stdout truncation from 600 characters so complete tables render in terminal. |
| `code/recovery.py` | Critic-fail recovery logs now include the Critic rationale, including cap-hit cases. |

### Modified prompts

| File | Difference from `S9SharedCode` |
|---|---|
| `code/prompts/planner.md` | Planner instructions now explain how to include `browser_profile`, `storage_state`, `save_storage_state`, and `headless=false` for authenticated/profile-backed browser runs. |
| `code/prompts/browser.md` | Browser prompt now documents optional session metadata, replay-visible session fields, and CAPTCHA/login/geo/rate-limit/access-denied gateway-block behavior. |
| `code/prompts/distiller.md` | Distiller must put unsupported requested fields in `missing_fields` instead of inventing them. It specifically avoids turning model tags/params/likes into fake one-line descriptions. |
| `code/prompts/critic.md` | Critic passes honest `missing_fields` when evidence is absent, but fails generic guesses inserted for unsupported fields. |

### Modified docs and validation helpers

| File | Difference from `S9SharedCode` |
|---|---|
| `code/MODULE_MAP.md` | Renamed to `s9assignment` module map, added provider-routing section, updated data model docs for browser profile fields, and documented provider-order-aware MCP calls. |
| `code/VALIDATION.md` | Added Assignment 9 validation notes for browser session metadata, replay-visible fields, block detection, and browser assignment tests. |
| `run_demo.sh` | Updated unit-test summary from 29 tests to 38 tests, including browser assignment and provider routing tests. |

### Assignment behavior differences

| Area | `S9SharedCode` behavior | `s9assignment` behavior |
|---|---|---|
| Provider routing | Gateway/default routing could keep Planner pinned on Gemini even when Gemini was saturated. | Assignment runtime uses `gemini -> nvidia -> groq -> cerebras` for Planner only, based on live gateway status. |
| Tool-using skills | MCP/tool loop accepted only `provider_pin`. | Unchanged; broad provider-order routing was rolled back after Nvidia/Groq/Cerebras 502/503 instability. |
| Browser a11y layer | A11y was hard-pinned to Gemini by default. | Kept pinned to Gemini by default to avoid unstable action-loop provider failover. |
| Browser sessions | Public-page browser flow only. | Supports reusable Playwright storage-state JSON, persistent user-data directories, and manual-login bootstrap runs. |
| Browser block handling | CAPTCHA/login-oriented block detection. | Adds geo-block, rate-limit, and access-denied precondition reporting with `block_type`. |
| Replay evidence | Browser output had path/actions/final URL. | Browser output also exposes profile/session/block metadata and docs identify where to count visible actions. |
| Critic failure visibility | Recovery happened, but the reason was hard to see in stdout. | Critic verdict/rationale prints directly before recovery, including cap-hit cases. |
| Final stdout | Final answer was clipped to 600 characters. | Final answer prints in full. |

### Validation status

Last focused validation run from `s9assignment/code`:

```bash
uv run --quiet pytest tests/
```

Result: 38 tests passed.

### Generated or intentionally ignored differences

- `S9SharedCode/code/.env` exists only in the shared folder and was not copied
  into the assignment changelog as a source change.
- `.venv`, `__pycache__`, `.pytest_cache`, `.DS_Store`, `state/sessions`,
  `state/index.faiss`, `state/index_ids.json`, `state/memory.json`,
  `usage.json`, and `logs/*` are runtime/local artifacts, not assignment logic.
