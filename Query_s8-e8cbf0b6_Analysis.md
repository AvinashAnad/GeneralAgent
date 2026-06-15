# Query Analysis: s8-e8cbf0b6

## Original User Goal

`Compare 5 CNC/VMC training institutes in Bangalore.`

Session inspected: `s8-e8cbf0b6`

Primary session report:

[visible_browser_replay_report_s8-e8cbf0b6.html](S9SharedCodeVisibleAgent/code/state/sessions/s8-e8cbf0b6/visible_browser_reports/s8-e8cbf0b6/visible_browser_replay_report_s8-e8cbf0b6.html)

Browser-folder alias of the same session report:

[visible_browser_replay_report_s8-e8cbf0b6.html](S9SharedCodeVisibleAgent/code/state/sessions/s8-e8cbf0b6/browser/visible_browser_reports/s8-e8cbf0b6/visible_browser_replay_report_s8-e8cbf0b6.html)

## Short Answer

No Browser node was used in this run. The final answer came from non-browser skills in the DAG.

## Data Source Summary

| Source | Status | Used For Final Table |
| --- | --- | --- |
| Browser | not used | No |
| Researcher | 5 output(s) | Yes |
| Distiller | 4 output(s) | Maybe |
| Formatter | 5 output(s) | Yes |

## Planner DAG Observed

| Node | Skill | Status | Success | Purpose |
| --- | --- | --- | --- | --- |
| n:1 | planner | complete | True | Plan or re-plan the DAG. |
| n:2 | researcher | complete | True | Find 5 reputable CNC/VMC training institutes in Bangalore and provide details on their course offerings, duration, and placement support. |
| n:3 | distiller | complete | True | Extract structured details for 5 CNC/VMC training institutes: Name, Key Courses, Duration, and Placement Support. |
| n:4 | formatter | skipped | None | Produce the final user-facing answer. |
| n:5 | critic | complete | True | Evaluate an upstream output. |
| n:6 | planner | complete | True | Recovery for n:3 |
| n:7 | researcher | complete | True | Find 5 reputable CNC/VMC training institutes in Bangalore and provide details for each including course focus and reputation. |
| n:8 | distiller | complete | True | Extract structured fields. |
| n:9 | formatter | skipped | None | Produce the final user-facing answer. |
| n:10 | critic | complete | True | Evaluate an upstream output. |
| n:11 | planner | complete | True | Recovery for n:8 |
| n:12 | researcher | complete | True | Find a list of at least 5 reputable CNC/VMC training institutes in Bangalore with their key features. |
| n:13 | distiller | complete | True | Extract 5 CNC/VMC training institutes in Bangalore, including their name, key courses, and highlights. |
| n:14 | formatter | skipped | None | Produce the final user-facing answer. |
| n:15 | critic | complete | True | Evaluate an upstream output. |
| n:16 | planner | complete | True | Recovery for n:13 |
| n:17 | researcher | complete | True | Find 5 reputable CNC/VMC training institutes in Bangalore, including details like course duration, curriculum focus, and placement support. |
| n:18 | distiller | complete | True | Extract structured fields. |
| n:19 | formatter | skipped | None | Produce the final user-facing answer. |
| n:20 | critic | complete | True | Evaluate an upstream output. |
| n:21 | planner | complete | True | Recovery for n:18 |
| n:22 | researcher | complete | True | Find 5 reputable CNC/VMC training institutes in Bangalore and provide details on their courses, duration, and placement support for comparison. |
| n:23 | formatter | complete | True | Produce the final user-facing answer. |
| n:24 | session_reporter | complete | True | Write session replay and query analysis artifacts. |

## Browser Attempts

(none)

## Importance of a11y

`a11y` means the accessibility-tree layer of the Browser skill. It is cheaper than full vision and is useful for interactive UI controls such as filters, sort menus, tabs, accordions, product links, and forms when those controls are exposed to assistive technology.

For blocked pages, a11y is still useful evidence: it can show that the rendered page is an access-denied, CAPTCHA, login, geo, or rate-limit state rather than a normal product page.

## Did The Four-Layer Cascade Run?

No Browser node was used, so the browser cascade did not run.

## Final Comparison Table

| Product | Details |
| --- | --- |
| NTTF (Nettur Technical Training Foundation) | A well-established educational institution known for its formal Precision CNC Machinist programs. It is highly regarded for its industry-aligned curriculum, extensive hands-on laboratory experience, and a strong track record of placement (reported at over 98%). |
| RVM CAD | A prominent private training center specializing in CAD/CAM and CNC/VMC programming. They offer intensive, short-term programs (typically around 30 days) that combine software training (Mastercam, NX CAM) with practical machine operation. They provide 100% placement assistance. |
| Technologics Global Pvt Ltd | This provider focuses on industrial automation, offering CNC programming as part of a broader curriculum. Their model emphasizes real-time industrial projects at factory sites and hands-on practical sessions with placement support. |

## Final Answer

```text
While there are many vocational training providers in Bangalore, comprehensive side-by-side data for five distinct institutes is limited. Based on available information, here are three reputable options for CNC/VMC training in Bangalore:

1. NTTF (Nettur Technical Training Foundation): A well-established educational institution known for its formal Precision CNC Machinist programs. It is highly regarded for its industry-aligned curriculum, extensive hands-on laboratory experience, and a strong track record of placement (reported at over 98%).

2. RVM CAD: A prominent private training center specializing in CAD/CAM and CNC/VMC programming. They offer intensive, short-term programs (typically around 30 days) that combine software training (Mastercam, NX CAM) with practical machine operation. They provide 100% placement assistance.

3. Technologics Global Pvt Ltd: This provider focuses on industrial automation, offering CNC programming as part of a broader curriculum. Their model emphasizes real-time industrial projects at factory sites and hands-on practical sessions with placement support.

Other options in the city often include various private technical academies and government-run Industrial Training Institutes (ITI). When evaluating these, it is recommended to verify specific placement claims and ensure the institute provides sufficient hands-on access to actual CNC/VMC machinery.
```

## Module Responsibility Map

| Module | Responsibility |
| --- | --- |
| [browser/skill.py](S9SharedCodeVisibleAgent/code/browser/skill.py) | Owns the Browser cascade: extract, deterministic selectors, a11y, vision, and blocked/failure handling. |
| [browser/driver.py](S9SharedCodeVisibleAgent/code/browser/driver.py) | Implements a11y and vision interaction drivers. |
| [browser/dom.py](S9SharedCodeVisibleAgent/code/browser/dom.py) | Builds DOM and clickability context for browser drivers. |
| [browser/highlight.py](S9SharedCodeVisibleAgent/code/browser/highlight.py) | Produces visual marks for screenshot-based vision interaction. |
| [browser/client.py](S9SharedCodeVisibleAgent/code/browser/client.py) | Calls the LLM gateway for a11y chat and vision decisions. |
| [browser/replay_report.py](S9SharedCodeVisibleAgent/code/browser/replay_report.py) | Writes Browser-attempt and session-level replay reports. |
| [query_analysis_report.py](S9SharedCodeVisibleAgent/code/query_analysis_report.py) | Writes root-level Query_<session-id>_Analysis.md files. |
| [skills.py](S9SharedCodeVisibleAgent/code/skills.py) | Dispatches skills, including session_reporter. |
| [agent_config.yaml](S9SharedCodeVisibleAgent/code/agent_config.yaml) | Skill catalogue; formatter triggers session_reporter through internal_successors. |
| [prompts/planner.md](S9SharedCodeVisibleAgent/code/prompts/planner.md) | Planner and recovery guidance. |

## Turn Count And Cost Summary

```json
{
  "node_count": 24,
  "browser_attempt_count": 0,
  "browser_turn_count": 0,
  "completed_nodes": 20,
  "failed_nodes": 0,
  "llm_calls": 25,
  "tokens_in": 47065,
  "tokens_out": 5446,
  "estimated_cost_usd": 0.001013,
  "node_result_cost_usd": 0.0,
  "gateway_ledger_cost_usd": 0.001013,
  "providers": [
    "gemini",
    "groq"
  ],
  "gateway_cost_by_agent": {
    "critic": [
      {
        "agent": "critic",
        "provider": "groq",
        "calls": 4,
        "in_tok": 3447,
        "out_tok": 661,
        "total_latency_ms": 3295,
        "total_retries": 0,
        "ok": 4,
        "errors": 0,
        "dollars": 0.001013
      }
    ],
    "distiller": [
      {
        "agent": "distiller",
        "provider": "gemini",
        "calls": 4,
        "in_tok": 4962,
        "out_tok": 641,
        "total_latency_ms": 5347,
        "total_retries": 0,
        "ok": 4,
        "errors": 0,
        "dollars": 0.0
      }
    ],
    "formatter": [
      {
        "agent": "formatter",
        "provider": "gemini",
        "calls": 1,
        "in_tok": 1315,
        "out_tok": 290,
        "total_latency_ms": 1974,
        "total_retries": 0,
        "ok": 1,
        "errors": 0,
        "dollars": 0.0
      }
    ],
    "planner": [
      {
        "agent": "planner",
        "provider": "gemini",
        "calls": 5,
        "in_tok": 12692,
        "out_tok": 1199,
        "total_latency_ms": 18562,
        "total_retries": 0,
        "ok": 5,
        "errors": 0,
        "dollars": 0.0
      }
    ],
    "researcher": [
      {
        "agent": "researcher",
        "provider": "gemini",
        "calls": 11,
        "in_tok": 24649,
        "out_tok": 2655,
        "total_latency_ms": 49939,
        "total_retries": 1,
        "ok": 11,
        "errors": 0,
        "dollars": 0.0
      }
    ]
  }
}
```

## Token Usage Capture

Browser a11y/vision turns record per-turn token counts in action/step records. Normal LLM skill calls are tagged with `agent` and `session` and are captured by the gateway ledger exposed at `/v1/cost/by_agent?session=<session-id>`. The session reporter now tries to include that gateway rollup in the cost summary. If the running gateway endpoint returns no rows, the reporter falls back to the local SQLite ledger at `llm_gatewayV9/gateway_v8.db`. If neither source has rows for that session, the summary falls back to node-local cost fields, which are often `0.0` for text skills.

## Orchestrator Constraint

This analysis file is generated through the copied agent's `session_reporter` skill path. The original `S9SharedCode` orchestrator remains untouched.
