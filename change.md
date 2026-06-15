# How S9SharedCodeVisibleAgent Differs From S9SharedCode

## Summary

`S9SharedCodeVisibleAgent` is a copied agent built on top of `S9SharedCode`.
It keeps the original orchestrator behavior intact while adding visible browser
evidence, replay reports, session-level reporting, and automated query-analysis
Markdown files.

The orchestrator file is unchanged:

| File | Difference |
| --- | --- |
| `code/flow.py` | No difference between `S9SharedCode` and `S9SharedCodeVisibleAgent`. |

## Main Behavioral Differences

| Area | S9SharedCode | S9SharedCodeVisibleAgent |
| --- | --- | --- |
| Browser reporting | Browser returns normal `BrowserOutput`; no automatic visible replay report. | Every Browser attempt writes a session-tagged replay report. |
| Session reporting | No final session-level replay report. | `formatter` triggers `session_reporter`, which writes the authoritative session-level HTML/JSON report. |
| Query analysis | No root-level query analysis Markdown. | Writes `Query_<session-id>_Analysis.md` at the Session9 root. |
| Browser extension hook | No local visible demo extension. | Supports `metadata.browser_extension=visible_catalog_report`. |
| Recovery prompt | Browser `gateway_blocked` recovery is handled. | Browser failures such as `interaction_failed`, `all layers exhausted`, `step cap reached`, and `giveup` are treated as exhausted to avoid repeated Browser retries. |
| Token/cost reporting | Gateway ledger exists, but session replay does not pull it into a report. | Session report attempts to include `/v1/cost/by_agent?session=<session-id>` rollup, and Browser step output preserves per-turn token fields for future runs. |
| Documentation | Base code docs. | Adds visible-browser/reporting docs. |

## Added Files

| File | Purpose |
| --- | --- |
| [S9SharedCodeVisibleAgent/code/VISIBLE_BROWSER_AGENT.md](S9SharedCodeVisibleAgent/code/VISIBLE_BROWSER_AGENT.md) | Explains the visible browser extension, report paths, and backfill flow. |
| [S9SharedCodeVisibleAgent/code/backfill_session_report.py](S9SharedCodeVisibleAgent/code/backfill_session_report.py) | Regenerates session-level reports and root-level query analysis for existing sessions. |
| [S9SharedCodeVisibleAgent/code/query_analysis_report.py](S9SharedCodeVisibleAgent/code/query_analysis_report.py) | Generates `Query_<session-id>_Analysis.md` files at the Session9 root. |
| [S9SharedCodeVisibleAgent/code/run_visible_browser_agent.py](S9SharedCodeVisibleAgent/code/run_visible_browser_agent.py) | Local runner for the visible browser demo workflow. |
| [S9SharedCodeVisibleAgent/code/browser/replay_report.py](S9SharedCodeVisibleAgent/code/browser/replay_report.py) | Writes per-Browser-attempt reports and session-level Visible Browser Replay Reports. |
| [S9SharedCodeVisibleAgent/code/browser/visible_catalog_extension.py](S9SharedCodeVisibleAgent/code/browser/visible_catalog_extension.py) | Local deterministic browser workflow for visible actions: search, filter, sort, detail pages, tabs, hidden content, and form submission. |
| [S9SharedCodeVisibleAgent/code/browser/fixtures/visible_catalog.html](S9SharedCodeVisibleAgent/code/browser/fixtures/visible_catalog.html) | Local HTML fixture used by the visible browser extension. |
| [S9SharedCodeVisibleAgent/code/prompts/session_reporter.md](S9SharedCodeVisibleAgent/code/prompts/session_reporter.md) | Prompt stub/catalogue companion for the `session_reporter` skill. |

## Modified Files

| File | Change |
| --- | --- |
| [S9SharedCodeVisibleAgent/code/agent_config.yaml](S9SharedCodeVisibleAgent/code/agent_config.yaml) | Adds `session_reporter`; sets `formatter.internal_successors: [session_reporter]`; documents the Browser extension hook. |
| [S9SharedCodeVisibleAgent/code/skills.py](S9SharedCodeVisibleAgent/code/skills.py) | Adds Python dispatch for `session_reporter` in the skill layer, not in `flow.py`; prints the generated analysis path. |
| [S9SharedCodeVisibleAgent/code/browser/skill.py](S9SharedCodeVisibleAgent/code/browser/skill.py) | Adds the `visible_catalog_report` extension hook; wraps Browser results with replay-report generation; preserves per-turn provider/model/latency/token metadata in Browser actions. |
| [S9SharedCodeVisibleAgent/code/prompts/planner.md](S9SharedCodeVisibleAgent/code/prompts/planner.md) | Strengthens recovery guidance so failed Browser attempts are not retried repeatedly. |
| `S9SharedCodeVisibleAgent/code/usage.json` | Runtime usage counters differ; this is state, not an intended behavior change. |

## Report Artifacts Added By The Visible Agent

For each Browser attempt:

```text
S9SharedCodeVisibleAgent/code/state/sessions/<session-id>/browser/visible_browser_reports/<session-id>/
  browser_attempt_replay_report_<session-id>.html
  browser_attempt_replay_report_<session-id>.json
```

For each completed session that reaches `formatter`:

```text
S9SharedCodeVisibleAgent/code/state/sessions/<session-id>/visible_browser_reports/<session-id>/
  visible_browser_replay_report_<session-id>.html
  visible_browser_replay_report_<session-id>.json
```

The browser-folder path is also mirrored to the final session report:

```text
S9SharedCodeVisibleAgent/code/state/sessions/<session-id>/browser/visible_browser_reports/<session-id>/
  visible_browser_replay_report_<session-id>.html
  visible_browser_replay_report_<session-id>.json
```

The root-level query analysis file is:

```text
Query_<session-id>_Analysis.md
```

Example:

[Query_s8-b6934903_Analysis.md](Query_s8-b6934903_Analysis.md)

## Why This Design Keeps The Orchestrator Stable

The visible-agent behavior is added through existing extension points:

| Extension Point | How It Is Used |
| --- | --- |
| Skill catalogue | `session_reporter` is declared in `agent_config.yaml`. |
| Static successors | `formatter.internal_successors` queues `session_reporter` after final answer generation. |
| Skill dispatcher | `skills.py` handles `session_reporter` locally. |
| Browser skill extension | `browser/skill.py` checks `metadata.browser_extension`. |
| Report writer | `browser/replay_report.py` writes HTML/JSON and calls `query_analysis_report.py`. |

Because of that, the copied agent can add replay/reporting behavior without
changing `flow.py`.

## Practical Difference In A Run

With `S9SharedCode`, a query such as:

```text
Compare 3 laptops under INR 80,000.
```

returns a final answer through the DAG, but does not automatically produce a
session-level visible replay report or root-level analysis file.

With `S9SharedCodeVisibleAgent`, the same query can produce:

| Artifact | Meaning |
| --- | --- |
| Browser attempt report | Shows what the Browser node tried, including blocked/failure page-state evidence. |
| Session replay report | Shows the full DAG, recovery path, browser attempts, screenshots/page-state logs, extracted data, final answer, and final comparison table. |
| Query analysis Markdown | A root-level shareable explanation of what happened in the session, with links to the HTML reports. |

## Current Validation Notes

- `S9SharedCode/code/flow.py` and `S9SharedCodeVisibleAgent/code/flow.py` match.
- The original `S9SharedCode` git status was checked separately and remained clean on `master`.
- `S9SharedCodeVisibleAgent` was validated by backfilling session `s8-b6934903`, which generated [Query_s8-b6934903_Analysis.md](Query_s8-b6934903_Analysis.md).

