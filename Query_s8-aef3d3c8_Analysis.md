# Query Analysis: s8-aef3d3c8

## Original User Goal

`Compare 5 AI coding tools by free plan and paid plan.`

Session inspected: `s8-aef3d3c8`

Primary session report:

[visible_browser_replay_report_s8-aef3d3c8.html](S9SharedCodeVisibleAgent/code/state/sessions/s8-aef3d3c8/visible_browser_reports/s8-aef3d3c8/visible_browser_replay_report_s8-aef3d3c8.html)

Browser-folder alias of the same session report:

[visible_browser_replay_report_s8-aef3d3c8.html](S9SharedCodeVisibleAgent/code/state/sessions/s8-aef3d3c8/browser/visible_browser_reports/s8-aef3d3c8/visible_browser_replay_report_s8-aef3d3c8.html)

## Short Answer

No Browser node was used in this run. The final answer came from non-browser skills in the DAG.

## Data Source Summary

| Source | Status | Used For Final Table |
| --- | --- | --- |
| Browser | not used | No |
| Researcher | 5 output(s) | Yes |
| Distiller | 0 output(s) | No |
| Formatter | 1 output(s) | Yes |

## Planner DAG Observed

| Node | Skill | Status | Success | Purpose |
| --- | --- | --- | --- | --- |
| n:1 | planner | complete | True | Plan or re-plan the DAG. |
| n:2 | researcher | complete | True | What are the free and paid plan details for GitHub Copilot? |
| n:3 | researcher | complete | True | What are the free and paid plan details for Cursor AI? |
| n:4 | researcher | complete | True | What are the free and paid plan details for Claude Dev / Anthropic Claude? |
| n:5 | researcher | complete | True | What are the free and paid plan details for Tabnine? |
| n:6 | researcher | complete | True | What are the free and paid plan details for Cody by Sourcegraph? |
| n:7 | formatter | complete | True | Produce the final user-facing answer. |
| n:8 | session_reporter | complete | True | Write session replay and query analysis artifacts. |

## Browser Attempts

(none)

## Importance of a11y

`a11y` means the accessibility-tree layer of the Browser skill. It is cheaper than full vision and is useful for interactive UI controls such as filters, sort menus, tabs, accordions, product links, and forms when those controls are exposed to assistive technology.

For blocked pages, a11y is still useful evidence: it can show that the rendered page is an access-denied, CAPTCHA, login, geo, or rate-limit state rather than a normal product page.

## Did The Four-Layer Cascade Run?

No Browser node was used, so the browser cascade did not run.

## Browser Layer Trace

- Browser not used -> cascade did not run -> planner used researcher -> formatter produced final answer

## Final Comparison Table

| Tool | Free Plan | Paid Plan(s) | Key Notes |
| --- | --- | --- | --- |
| **GitHub Copilot** | Limited (2k completions/50 chats per month) | $10–$100/mo (Pro/Max); $19–$39/user/mo (Business) | Free access available for students/teachers/maintainers. |
| **Cursor AI** | Limited (Hobby tier: 2k completions, 50 slow premium requests) | $20/mo (Pro); $40/seat/mo (Business) | Pro includes unlimited tab completions and a monthly credit pool. |
| **Claude (Anthropic)** | Free tier with daily usage limits | $20/mo (Pro); $100–$200/mo (Max tiers) | Pro/Max offer higher capacity and access to Claude Code. |
| **Tabnine** | No permanent free tier; offers a trial period | Starts at ~$39/user/mo | Focused on professional/enterprise; offers on-premises/air-gapped options. |
| **Cody (Sourcegraph)** | None (Discontinued) | Enterprise only (Custom pricing) | Now positioned exclusively as an enterprise-grade tool. |

## Final Answer

```text
Here is a comparison of five popular AI coding tools based on their current free and paid plan structures:

| Tool | Free Plan | Paid Plan(s) | Key Notes |
| :--- | :--- | :--- | :--- |
| **GitHub Copilot** | Limited (2k completions/50 chats per month) | $10–$100/mo (Pro/Max); $19–$39/user/mo (Business) | Free access available for students/teachers/maintainers. |
| **Cursor AI** | Limited (Hobby tier: 2k completions, 50 slow premium requests) | $20/mo (Pro); $40/seat/mo (Business) | Pro includes unlimited tab completions and a monthly credit pool. |
| **Claude (Anthropic)** | Free tier with daily usage limits | $20/mo (Pro); $100–$200/mo (Max tiers) | Pro/Max offer higher capacity and access to Claude Code. |
| **Tabnine** | No permanent free tier; offers a trial period | Starts at ~$39/user/mo | Focused on professional/enterprise; offers on-premises/air-gapped options. |
| **Cody (Sourcegraph)** | None (Discontinued) | Enterprise only (Custom pricing) | Now positioned exclusively as an enterprise-grade tool. |

**Summary of Findings:**
* **For Personal Use:** GitHub Copilot, Cursor, and Claude offer the most accessible entry points with functional free tiers, though they are subject to usage caps.
* **For Professional/Enterprise:** Tabnine and Cody focus heavily on security, compliance, and team-based features, with Cody having moved entirely away from individual consumer plans.
* **Note:** Pricing and availability for SaaS tools change frequently. It is recommended to verify the latest terms directly on the official websites of these providers.
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
  "node_count": 8,
  "browser_attempt_count": 0,
  "browser_turn_count": 0,
  "completed_nodes": 8,
  "failed_nodes": 0,
  "llm_calls": 12,
  "tokens_in": 23433,
  "tokens_out": 2890,
  "estimated_cost_usd": 0.0,
  "node_result_cost_usd": 0.0,
  "gateway_ledger_cost_usd": 0.0,
  "providers": [
    "gemini",
    "local-session-reporter"
  ],
  "gateway_cost_by_agent": {
    "formatter": [
      {
        "provider": "gemini",
        "calls": 1,
        "in_tok": 2876,
        "out_tok": 425,
        "total_latency_ms": 20848,
        "total_retries": 0,
        "ok": 1,
        "errors": 0,
        "dollars": 0.0
      }
    ],
    "planner": [
      {
        "provider": "gemini",
        "calls": 1,
        "in_tok": 2512,
        "out_tok": 419,
        "total_latency_ms": 2060,
        "total_retries": 0,
        "ok": 1,
        "errors": 0,
        "dollars": 0.0
      }
    ],
    "researcher": [
      {
        "provider": "gemini",
        "calls": 10,
        "in_tok": 18045,
        "out_tok": 2046,
        "total_latency_ms": 69130,
        "total_retries": 0,
        "ok": 10,
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
