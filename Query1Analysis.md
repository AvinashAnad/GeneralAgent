# Query 1 Analysis: Visible Browser Report and Recovery Path

## Original User Goal

`Compare 3 laptops under INR 80,000.`

Session inspected: `s8-b6934903`

Primary session report:

[visible_browser_replay_report_s8-b6934903.html](S9SharedCodeVisibleAgent/code/state/sessions/s8-b6934903/visible_browser_reports/s8-b6934903/visible_browser_replay_report_s8-b6934903.html)

Browser-folder alias of the same session report:

[visible_browser_replay_report_s8-b6934903.html](S9SharedCodeVisibleAgent/code/state/sessions/s8-b6934903/browser/visible_browser_reports/s8-b6934903/visible_browser_replay_report_s8-b6934903.html)

## Short Answer

The final laptop comparison was produced even though the Browser path was `blocked` because `blocked` applies only to the Browser node attempt, not to the entire DAG run.

In this session:

- Browser node `n:2` tried Croma and failed with `interaction_failed`.
- The orchestrator queued a recovery planner node `n:5`.
- The recovery planner switched to the `researcher` skill.
- Researcher node `n:6` gathered data from web sources.
- Formatter node `n:7` produced the final comparison table.
- Session reporter node `n:8` generated the session-level visible browser report.

So the extracted final answer came from the recovery path, mainly `researcher_outputs` and `formatter.final_answer`, not from the blocked Browser attempt.

## Why Data Exists If Browser Was Blocked

The report has two different concepts that are easy to mix up:

| Concept | Meaning in this run |
| --- | --- |
| Browser path chosen | The Browser skill's own attempt against Croma ended as `blocked`. |
| Full DAG result | The overall query recovered through planner -> researcher -> formatter. |
| Extracted data section | Session-level evidence, including failed Browser attempts plus successful researcher and formatter outputs. |
| Final comparison table | Parsed from `formatter.final_answer`, not from the failed Croma page. |

The Browser attempt did not extract usable product data:

- `node_id`: `n:2`
- `status`: `failed`
- `error_code`: `interaction_failed`
- `error`: `all layers exhausted; last: step cap reached (12)`
- `actions`: `[]`
- `content`: `null`

The recovery data came from researcher node `n:6`, which reported sources including:

- Smartprix: best laptops under 80000
- Gadgets Now: best laptops under 80000
- Croma: best laptops between 75000 and 100000

The final table came from formatter node `n:7`.

## Planner DAG Observed

| Node | Skill | Status | Purpose |
| --- | --- | --- | --- |
| `n:1` | `planner` | complete | Initial plan: try Browser on Croma, then distill and format. |
| `n:2` | `browser` | failed | Croma browser attempt failed after all browser layers were exhausted. |
| `n:3` | `distiller` | pending | Original branch node left pending because the upstream Browser node failed. |
| `n:4` | `formatter` | pending | Original branch formatter left pending because the upstream distiller did not run. |
| `n:5` | `planner` | complete | Recovery planner created after Browser failure. |
| `n:6` | `researcher` | complete | Recovery data gathering for popular laptops under INR 80,000. |
| `n:7` | `formatter` | complete | Produced the final answer and comparison table. |
| `n:8` | `session_reporter` | complete | Wrote the session-level Visible Browser Replay Report. |

## Importance of a11y

`a11y` means the accessibility-tree layer of the Browser skill.

It is important because it sits between deterministic selectors and full vision:

| Layer | Role | Cost / Behavior |
| --- | --- | --- |
| Extract | Fetch and extract page text with HTTP/trafilatura. | Cheapest, no browser UI. |
| Deterministic | Use known stable CSS selectors if provided. | Cheap and reliable when selectors are known. |
| a11y | Use Playwright plus the page accessibility tree. | Cheaper than vision; useful for buttons, inputs, filters, tabs, and forms exposed to assistive tech. |
| Vision | Use screenshots with set-of-marks and a vision-capable model. | Most expensive; fallback when text/a11y structure is insufficient. |

For this query, the a11y screenshots show `Access Denied`. That is useful evidence: it tells us the live page was not exposing normal interactive content to the agent. The a11y layer therefore helped prove the Browser attempt was blocked rather than silently missing products.

## Did The Four-Layer Cascade Run?

Yes, the Browser skill is configured to run the cascade:

1. `extract`
2. `deterministic`
3. `a11y`
4. `vision`
5. report `blocked` if the browser cannot get useful page state

In this specific run:

| Browser layer | Result |
| --- | --- |
| Extract | No useful product content was obtained. |
| Deterministic | No useful selector-driven extraction was available for this Croma attempt. |
| a11y | Repeated page-state screenshots showed `Access Denied`. |
| Vision | Tried visual fallback, but the visible page state was still blocked. |
| Final Browser state | `blocked` / `interaction_failed`, with step cap reached. |

That is why the report shows screenshots but no Browser actions. The agent could see the denied page state, but there was no meaningful product UI to click, filter, sort, or open.

## Final Comparison Table Source

The final comparison table in the session report was parsed from `formatter.final_answer`.

| Feature | HP Victus Gaming Laptop | MSI Cyborg 15 | ASUS TUF Gaming A15 (FA506NCR) |
| --- | --- | --- | --- |
| Approx. Price | INR 79,990 | INR 79,990 | INR 78,990 |
| Processor | Intel Core i5-13420H | 12th Gen Intel Core i7 | AMD Ryzen 7 |
| RAM | 16GB | 16GB | 16GB |
| Storage | 512GB SSD | 512GB SSD | 512GB or 1TB SSD |
| Display | 15.6-inch | 15.6-inch | 15.6-inch 144Hz FHD |
| Graphics | NVIDIA RTX 4050 | 6GB NVIDIA RTX 3050 | Dedicated NVIDIA Graphics |

## Module Responsibility Map

| Module | Responsibility |
| --- | --- |
| `S9SharedCodeVisibleAgent/code/browser/skill.py` | Owns the Browser skill cascade: extract, deterministic selectors, a11y, vision, and final blocked/failure handling. |
| `S9SharedCodeVisibleAgent/code/browser/driver.py` | Implements the interactive a11y and vision drivers. a11y uses text/accessibility structure; vision uses screenshots and set-of-marks. |
| `S9SharedCodeVisibleAgent/code/browser/dom.py` | Builds DOM/clickability context used by browser drivers. |
| `S9SharedCodeVisibleAgent/code/browser/highlight.py` | Produces visual marks for screenshot-based vision interaction. |
| `S9SharedCodeVisibleAgent/code/browser/client.py` | Calls the LLM gateway for a11y chat and vision decisions. |
| `S9SharedCodeVisibleAgent/code/browser/replay_report.py` | Writes per-Browser attempt reports and session-level Visible Browser Replay Reports. |
| `S9SharedCodeVisibleAgent/code/skills.py` | Dispatches skills, including the copied-agent `session_reporter` hook. |
| `S9SharedCodeVisibleAgent/code/agent_config.yaml` | Skill catalogue configuration. `formatter` has `internal_successors: [session_reporter]`, so the report is generated after the final answer. |
| `S9SharedCodeVisibleAgent/code/prompts/planner.md` | Planner guidance, including recovery behavior after Browser failures. |

## Important Distinction

The Browser report is evidence for what happened inside the Browser attempt.

The session-level report is the authoritative report for the whole query. It can correctly show:

- Browser path: `blocked`
- Recovery path: planner -> researcher -> formatter
- Browser screenshots/page-state logs
- Researcher sources/findings
- Final formatter answer
- Final comparison table

That combination is expected for `s8-b6934903`.

## Orchestrator Constraint

The original `S9SharedCode` orchestrator was not modified.

The session-level report behavior was added in the copied agent through:

- a `session_reporter` skill in the skill catalogue
- `formatter.internal_successors`
- report-writing logic in the Browser/reporting layer
