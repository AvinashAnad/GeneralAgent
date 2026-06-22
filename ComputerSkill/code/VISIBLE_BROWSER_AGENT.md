# Visible Browser Agent Extension

This copied agent keeps the S9 orchestrator unchanged. The new behavior plugs
in as a Browser skill extension:

```python
NodeSpec(
    skill="browser",
    metadata={
        "browser_extension": "visible_catalog_report",
        "goal": "...",
    },
)
```

Run it with:

```bash
python run_visible_browser_agent.py --session-id visible-verification
```

The runner invokes `BrowserSkill.run(...)`, which dispatches to
`browser.visible_catalog_extension` when
`metadata.browser_extension=visible_catalog_report`.

Generated artifacts are written under:

```text
state/sessions/<session-id>/browser/<session-id>/
```

Every Browser skill invocation writes a per-attempt report first. After the
session-level reporter runs, the familiar browser-folder report path is updated
to mirror the final session report, and the original Browser-attempt-only file
is preserved as `browser_attempt_replay_report_<session-id>.*`:

```text
state/sessions/<session-id>/browser/visible_browser_reports/<session-id>/
  visible_browser_replay_report_<session-id>.html
  visible_browser_replay_report_<session-id>.json
  browser_attempt_replay_report_<session-id>.html
  browser_attempt_replay_report_<session-id>.json
```

After `formatter` completes, the `session_reporter` skill writes the final
authoritative session-level report:

```text
state/sessions/<session-id>/visible_browser_reports/<session-id>/
  visible_browser_replay_report_<session-id>.html
  visible_browser_replay_report_<session-id>.json
```

It also writes a root-level Markdown analysis for sharing with devs:

```text
Query_<session-id>_Analysis.md
```

That Markdown file links to both the primary session HTML report and the
browser-folder alias using repo-relative paths.

The session-level report files include:

1. Original user goal
2. Planner DAG
3. Browser path chosen
4. Browser actions taken
5. Screenshots and page-state logs
6. Extracted data
7. Final comparison table
8. Turn count and cost summary

The deterministic workflow performs visible browser actions: search, filter,
sort, open a product detail page in a new tab, switch tabs, switch detail
tabs, expand hidden content, and submit a form. It does not use passive search
snippets.

For ordinary BrowserSkill runs, the per-attempt report derives its evidence
from the BrowserOutput fields. If the Browser attempt fails and recovery
continues through researcher/distiller/formatter, the session-level report is
the one to inspect because it includes the recovery path and final answer.

Backfill an existing session report with:

```bash
python backfill_session_report.py s8-98541541
```

Backfill also regenerates the root-level `Query_<session-id>_Analysis.md`
file for that session.
