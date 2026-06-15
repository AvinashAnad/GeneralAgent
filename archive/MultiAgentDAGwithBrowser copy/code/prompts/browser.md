The Browser skill fetches and interacts with web pages. It walks a
four-layer cascade starting from the cheapest path (HTML extraction)
and escalating only when needed (deterministic selectors, accessibility
tree, then visual set-of-marks with a vision model). The escalation
is internal; you pass `url` and `goal`, the skill chooses the layer.

Inputs: `metadata.url` (required), `metadata.goal` (required, free-text
description of what to extract or do). Optional session metadata:
`browser_profile` names a reusable storage-state file under
`state/browser_profiles/`, `storage_state` loads a Playwright
cookies/localStorage JSON file, `save_storage_state` writes the post-run
state, `user_data_dir` uses a persistent Chromium profile directory, and
`headless=false` is available for a deliberate manual-login/bootstrap
run.

Output: `BrowserOutput` with `content` (for extraction goals) or
`actions` plus `final_url` (for interaction goals), and `path`
reporting the cascade layer that actually ran. Replay-visible fields
also include `profile`, `storage_state_path`, `user_data_dir`, and
`block_type` when relevant. When the page is gated by CAPTCHA, login,
geo, rate-limit, or access-denied preconditions, the skill returns
`error_code="gateway_blocked"` and no content; the Planner should route
around by trying a different source URL or by handing back to the user.
