# Session 9 Assignment Notes

This folder is a clean copy of `S9SharedCode/` with assignment-specific
browser additions applied only here. The original shared folder is untouched.

## What Was Added

| Requirement | Implementation |
|---|---|
| Browser skill in the Session 8 runtime | `code/agent_config.yaml`, `code/prompts/browser.md`, and the `browser` dispatch branch in `code/skills.py` |
| Four-layer cascade | `code/browser/skill.py`: extract -> deterministic selectors -> a11y -> vision |
| Layer 1 extract | `httpx` + `trafilatura`, zero gateway calls |
| Layer 2a deterministic selectors | `metadata.selectors` in `BrowserSkill._try_deterministic` |
| Layer 2b accessibility-tree/text loop | `code/browser/driver.py::A11yDriver` using `/v1/chat` |
| Layer 3 vision/set-of-marks loop | `code/browser/highlight.py` + `SetOfMarksDriver` using `/v1/vision` |
| Precondition failures | `detect_gateway_block()` returns `gateway_blocked` for CAPTCHA, login wall, geo block, rate limit, and access denied pages |
| Replay-visible structured output | `BrowserOutput` includes `path`, `turns`, `final_url`, `actions`, `profile`, `storage_state_path`, `user_data_dir`, and `block_type` |
| At least three visible browser actions | `BrowserOutput.actions` records Playwright `click`, `fill`, `key`, `scroll`, `wait`, and `done` turns; screenshots/legends are saved under `code/state/sessions/<session>/browser/` |
| Browser-profile/session persistence | `code/browser/session.py`, wired through all Playwright layers |
| Assignment-side Planner failover | `code/provider_routing.py` plus `planner.provider_order: [gemini, nvidia, groq, cerebras]` |
| Visible Critic failure reason | `code/flow.py` and `code/recovery.py` print critic verdict/rationale before recovery |
| No agentic frameworks | The code uses Playwright, Pillow, httpx, trafilatura, NetworkX, Pydantic, and the existing gateway only |

## New Browser Metadata

Use these fields on a `browser` node:

```json
{
  "url": "https://example.com/account",
  "goal": "Open the account page and extract the visible plan name.",
  "browser_profile": "example_logged_in",
  "storage_state": "state/browser_profiles/example_logged_in.json",
  "save_storage_state": "state/browser_profiles/example_logged_in.json",
  "user_data_dir": "state/browser_profiles/example_chrome",
  "headless": true
}
```

Notes:

- `browser_profile` is the simplest reusable option. It maps to
  `code/state/browser_profiles/<name>.json`.
- `storage_state` loads a Playwright cookie/localStorage JSON file.
- `save_storage_state` writes the post-run state on browser close.
- `user_data_dir` uses a persistent Chromium profile directory instead of a
  one-off storage-state JSON.
- `headless=false` is intended only for an explicit manual-login/bootstrap run.

## Visible Browser Action Evidence

Assignment 9 says passive scraping from snippets is not accepted. For browser
runs, verify at least three visible actions in the browser node JSON:

```text
code/state/sessions/<session_id>/nodes/n_###.json
```

Look for:

```json
"path": "a11y",
"turns": 5,
"actions": [
  {"turn": 1, "actions": [{"type": "fill"}, {"type": "key"}], "outcome": "..."},
  {"turn": 2, "actions": [{"type": "click"}], "outcome": "..."},
  {"turn": 3, "actions": [{"type": "scroll"}], "outcome": "..."}
]
```

Layer 2b and Layer 3 also save per-turn screenshots or legends under
`code/state/sessions/<session_id>/browser/`, which acts as replay evidence for
search, filter, sort, open-detail, expand, scroll, or form-submit actions.

## Validation

Run the targeted local checks from `s9assignment/code`:

```bash
uv run --quiet pytest tests/
```

The browser-assignment and provider-routing tests avoid live network/gateway
calls. Full end-to-end browser runs still require Playwright browsers and the
V9 gateway on `localhost:8109`.
