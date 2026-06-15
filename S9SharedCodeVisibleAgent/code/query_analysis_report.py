"""Markdown query-analysis report writer.

This module is intentionally outside flow.py. The session_reporter skill calls
it after the final session replay payload is assembled, so every completed
query gets a root-level Query_<session-id>_Analysis.md without orchestrator
changes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def query_analysis_path(session_id: str, *, root_dir: Path) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in session_id)
    return root_dir / f"Query_{safe}_Analysis.md"


def query_analysis_metadata(session_id: str, *, root_dir: Path) -> dict[str, str]:
    path = query_analysis_path(session_id, root_dir=root_dir)
    return {
        "markdown": str(path),
        "relative_path": _relative_path(path, root_dir),
    }


def write_query_analysis_markdown(
    payload: dict[str, Any],
    *,
    root_dir: Path,
    primary_report: Path,
    browser_alias_report: Path | None = None,
) -> dict[str, str]:
    session_id = str(payload.get("session_id") or "no_sessionid")
    path = query_analysis_path(session_id, root_dir=root_dir)
    path.write_text(
        _render_markdown(
            payload,
            root_dir=root_dir,
            primary_report=primary_report,
            browser_alias_report=browser_alias_report,
        ),
        encoding="utf-8",
    )
    return {
        "markdown": str(path),
        "relative_path": _relative_path(path, root_dir),
    }


def _render_markdown(
    payload: dict[str, Any],
    *,
    root_dir: Path,
    primary_report: Path,
    browser_alias_report: Path | None,
) -> str:
    session_id = str(payload.get("session_id") or "no_sessionid")
    query = str(payload.get("original_user_goal") or "")
    browser_attempts = payload.get("browser_attempts") or []
    final_answer = str(payload.get("final_answer") or "")
    final_table = payload.get("final_comparison_table") or {}
    table_markdown = str(final_table.get("markdown") or "").strip()
    if not table_markdown:
        table_markdown = "(no comparison table)"

    lines = [
        f"# Query Analysis: {session_id}",
        "",
        "## Original User Goal",
        "",
        f"`{query}`",
        "",
        f"Session inspected: `{session_id}`",
        "",
        "Primary session report:",
        "",
        _markdown_link(
            primary_report.name,
            _relative_path(primary_report, root_dir),
        ),
        "",
    ]
    if browser_alias_report:
        lines += [
            "Browser-folder alias of the same session report:",
            "",
            _markdown_link(
                browser_alias_report.name,
                _relative_path(browser_alias_report, root_dir),
            ),
            "",
        ]

    lines += [
        "## Short Answer",
        "",
        _short_answer(payload),
        "",
        "## Data Source Summary",
        "",
        _data_source_table(payload),
        "",
        "## Planner DAG Observed",
        "",
        _planner_dag_table(payload),
        "",
        "## Browser Attempts",
        "",
        _browser_attempt_table(browser_attempts),
        "",
        "## Importance of a11y",
        "",
        "`a11y` means the accessibility-tree layer of the Browser skill. It is cheaper than full vision and is useful for interactive UI controls such as filters, sort menus, tabs, accordions, product links, and forms when those controls are exposed to assistive technology.",
        "",
        "For blocked pages, a11y is still useful evidence: it can show that the rendered page is an access-denied, CAPTCHA, login, geo, or rate-limit state rather than a normal product page.",
        "",
        "## Did The Four-Layer Cascade Run?",
        "",
        _cascade_table(payload),
        "",
        "## Browser Layer Trace",
        "",
        _cascade_trace(payload),
        "",
        "## Final Comparison Table",
        "",
        table_markdown,
        "",
        "## Final Answer",
        "",
        "```text",
        final_answer,
        "```",
        "",
        "## Module Responsibility Map",
        "",
        _module_map_table(),
        "",
        "## Turn Count And Cost Summary",
        "",
        "```json",
        _json_block(payload.get("turn_count_and_cost_summary") or {}),
        "```",
        "",
        "## Token Usage Capture",
        "",
        _token_usage_note(),
        "",
        "## Orchestrator Constraint",
        "",
        "This analysis file is generated through the copied agent's `session_reporter` skill path. The original `S9SharedCode` orchestrator remains untouched.",
        "",
    ]
    return "\n".join(lines)


def _short_answer(payload: dict[str, Any]) -> str:
    path = str(payload.get("browser_path_chosen") or "not_used")
    attempts = payload.get("browser_attempts") or []
    recovery = payload.get("recovery_path") or []
    final_answer = str(payload.get("final_answer") or "").strip()
    if path == "not_used":
        return (
            "No Browser node was used in this run. The final answer came from "
            "non-browser skills in the DAG."
        )
    if path == "blocked" and final_answer and recovery:
        return (
            "The final answer exists even though the Browser path was `blocked` "
            "because `blocked` applies to the Browser node attempt, not to the "
            "whole DAG. The run recovered through a planner recovery path and "
            "then produced the final answer through downstream skills."
        )
    if path == "blocked":
        return (
            "The Browser attempt was blocked and did not produce usable page "
            "content. No successful Browser extraction is implied by this report."
        )
    if any(attempt.get("success") for attempt in attempts):
        return (
            f"The Browser skill completed through the `{path}` path and the "
            "session report records the browser actions, page state, extracted "
            "data, and final formatter output."
        )
    return f"The session selected Browser path `{path}` and then completed through the recorded DAG."


def _data_source_table(payload: dict[str, Any]) -> str:
    extracted = payload.get("extracted_data") or {}
    browser_attempts = extracted.get("browser_attempts") or payload.get("browser_attempts") or []
    researcher_outputs = extracted.get("researcher_outputs") or []
    distiller_outputs = extracted.get("distiller_outputs") or []
    formatter_outputs = extracted.get("formatter_outputs") or []
    rows = [
        {
            "Source": "Browser",
            "Status": _attempt_status(browser_attempts),
            "Used For Final Table": "Yes" if any(a.get("success") for a in browser_attempts) else "No",
        },
        {
            "Source": "Researcher",
            "Status": f"{len(researcher_outputs)} output(s)",
            "Used For Final Table": "Yes" if researcher_outputs else "No",
        },
        {
            "Source": "Distiller",
            "Status": f"{len(distiller_outputs)} output(s)",
            "Used For Final Table": "Maybe" if distiller_outputs else "No",
        },
        {
            "Source": "Formatter",
            "Status": f"{len(formatter_outputs)} output(s)",
            "Used For Final Table": "Yes" if payload.get("final_answer") else "No",
        },
    ]
    return _markdown_table(rows, ["Source", "Status", "Used For Final Table"])


def _attempt_status(attempts: list[dict[str, Any]]) -> str:
    if not attempts:
        return "not used"
    if any(a.get("success") for a in attempts):
        return "success"
    codes = sorted({str(a.get("error_code") or "failed") for a in attempts})
    return "failed: " + ", ".join(codes)


def _planner_dag_table(payload: dict[str, Any]) -> str:
    nodes = payload.get("full_dag_nodes") or []
    if not nodes:
        nodes = [
            {
                "node_id": n.get("id"),
                "skill": n.get("label"),
                "status": n.get("status"),
                "success": n.get("success"),
            }
            for n in (payload.get("planner_dag") or {}).get("nodes", [])
        ]
    rows = []
    for node in nodes:
        rows.append(
            {
                "Node": node.get("node_id") or node.get("id") or "",
                "Skill": node.get("skill") or node.get("label") or "",
                "Status": node.get("status") or "",
                "Success": node.get("success"),
                "Purpose": _node_purpose(node),
            }
        )
    return _markdown_table(rows, ["Node", "Skill", "Status", "Success", "Purpose"])


def _node_purpose(node: dict[str, Any]) -> str:
    skill = str(node.get("skill") or node.get("label") or "")
    metadata = node.get("metadata") or {}
    if metadata.get("question"):
        return str(metadata["question"])
    if metadata.get("goal"):
        return str(metadata["goal"])
    if metadata.get("recovers"):
        return f"Recovery for {metadata.get('recovers')}"
    purposes = {
        "planner": "Plan or re-plan the DAG.",
        "browser": "Attempt live page extraction or interaction.",
        "researcher": "Gather supporting web research.",
        "distiller": "Extract structured fields.",
        "formatter": "Produce the final user-facing answer.",
        "session_reporter": "Write session replay and query analysis artifacts.",
        "critic": "Evaluate an upstream output.",
    }
    return purposes.get(skill, "")


def _browser_attempt_table(attempts: list[dict[str, Any]]) -> str:
    if not attempts:
        return "(none)"
    rows = []
    for attempt in attempts:
        rows.append(
            {
                "Node": attempt.get("node_id", ""),
                "Status": attempt.get("status", ""),
                "Path": attempt.get("path", ""),
                "Turns": attempt.get("turns", 0),
                "Error Code": attempt.get("error_code", ""),
                "URL": attempt.get("url", ""),
            }
        )
    return _markdown_table(rows, ["Node", "Status", "Path", "Turns", "Error Code", "URL"])


def _cascade_table(payload: dict[str, Any]) -> str:
    screenshots = (payload.get("screenshots_or_page_state_logs") or {}).get("screenshots") or []
    labels = [str(s.get("label") or "") for s in screenshots]
    attempts = payload.get("browser_attempts") or []
    if not attempts:
        return "No Browser node was used, so the browser cascade did not run."
    rows = [
        {
            "Layer": "Extract",
            "Role": "HTTP/trafilatura page text extraction.",
            "Observed Result": "No successful Browser extraction recorded."
            if not any(a.get("success") and a.get("path") == "extract" for a in attempts)
            else "Succeeded.",
        },
        {
            "Layer": "Deterministic",
            "Role": "Known stable CSS selectors, when provided.",
            "Observed Result": "No deterministic success recorded."
            if not any(a.get("path") == "deterministic" for a in attempts)
            else "Used.",
        },
        {
            "Layer": "a11y",
            "Role": "Playwright accessibility-tree interaction.",
            "Observed Result": "Evidence captured." if any("a11y/" in l for l in labels) else "No a11y evidence recorded.",
        },
        {
            "Layer": "Vision",
            "Role": "Screenshot set-of-marks fallback.",
            "Observed Result": "Evidence captured." if any("vision/" in l for l in labels) else "No vision evidence recorded.",
        },
        {
            "Layer": "Final Browser State",
            "Role": "Browser node outcome.",
            "Observed Result": str(payload.get("browser_path_chosen") or ""),
        },
    ]
    return _markdown_table(rows, ["Layer", "Role", "Observed Result"])


def _cascade_trace(payload: dict[str, Any]) -> str:
    attempts = payload.get("browser_attempts") or []
    if not attempts:
        return _non_browser_trace(payload)
    lines = []
    for attempt in attempts:
        node_id = str(attempt.get("node_id") or "browser")
        steps = _attempt_trace_steps(payload, attempt)
        lines.append(f"- `{node_id}`: " + " -> ".join(steps))
    recovery = _recovery_trace(payload)
    if recovery:
        lines.append(f"- Recovery: {recovery}")
    return "\n".join(lines)


def _non_browser_trace(payload: dict[str, Any]) -> str:
    extracted = payload.get("extracted_data") or {}
    pieces = ["Browser not used", "cascade did not run"]
    if extracted.get("researcher_outputs"):
        pieces.append("planner used researcher")
    if extracted.get("distiller_outputs"):
        pieces.append("distiller/critic path handled structured extraction")
    if payload.get("final_answer"):
        pieces.append("formatter produced final answer")
    return "- " + " -> ".join(pieces)


def _attempt_trace_steps(payload: dict[str, Any], attempt: dict[str, Any]) -> list[str]:
    path = str(attempt.get("path") or "")
    success = bool(attempt.get("success"))
    error = str(attempt.get("error") or "").strip()
    error_code = str(attempt.get("error_code") or "").strip()
    node_id = str(attempt.get("node_id") or "")
    metadata = _browser_metadata(payload, node_id)
    counts = _evidence_counts(payload)

    steps = ["extract attempted"]
    if path == "extract" and success:
        steps.append("extract succeeded")
        steps.append("deterministic/a11y/vision not needed")
        return steps
    if error_code == "gateway_blocked":
        steps.append("extract detected gateway block")
    else:
        steps.append("no useful content extracted")

    selectors = metadata.get("selectors")
    if path == "deterministic" and success:
        steps.append("deterministic selectors succeeded")
        steps.append("a11y/vision not needed")
        return steps
    if selectors:
        steps.append("deterministic attempted; selectors did not complete the goal")
    else:
        steps.append("deterministic skipped/no selectors")

    if path == "a11y" and success:
        steps.append(f"a11y succeeded in {attempt.get('turns', 0)} turn(s)")
        steps.append("vision not needed")
        return steps
    if counts["a11y"]:
        steps.append(f"a11y attempted; captured {counts['a11y']} page-state screenshot(s)")
    else:
        steps.append("a11y evidence not recorded")

    if path == "vision" and success:
        steps.append(f"vision succeeded in {attempt.get('turns', 0)} turn(s)")
        return steps
    if counts["vision"]:
        steps.append(f"vision attempted; captured {counts['vision']} screenshot artifact(s)")
    else:
        steps.append("vision not reached or not recorded")

    if success:
        steps.append(f"final browser state: {path}")
    else:
        final = "blocked"
        if error_code:
            final += f"/{error_code}"
        if error:
            final += f" ({error})"
        steps.append(f"final browser state: {final}")
    return steps


def _browser_metadata(payload: dict[str, Any], node_id: str) -> dict[str, Any]:
    for node in payload.get("full_dag_nodes") or []:
        if str(node.get("node_id") or "") == node_id:
            metadata = node.get("metadata") or {}
            return metadata if isinstance(metadata, dict) else {}
    return {}


def _evidence_counts(payload: dict[str, Any]) -> dict[str, int]:
    screenshots = (payload.get("screenshots_or_page_state_logs") or {}).get("screenshots") or []
    labels = [str(s.get("label") or "") for s in screenshots]
    return {
        "a11y": sum(1 for label in labels if "a11y/" in label),
        "vision": sum(1 for label in labels if "vision/" in label),
    }


def _recovery_trace(payload: dict[str, Any]) -> str:
    recovery = payload.get("recovery_path") or []
    if not recovery:
        return ""
    recovered = []
    for item in recovery:
        node = item.get("node_id", "planner")
        target = item.get("recovers", "failed node")
        reason = item.get("recovery_reason", "recovery")
        recovered.append(f"{node} recovered {target} via {reason}")
    extracted = payload.get("extracted_data") or {}
    tail = []
    if extracted.get("researcher_outputs"):
        tail.append("researcher gathered replacement data")
    if payload.get("final_answer"):
        tail.append("formatter produced final answer")
    return " -> ".join(recovered + tail)


def _module_map_table() -> str:
    rows = [
        ("browser/skill.py", "Owns the Browser cascade: extract, deterministic selectors, a11y, vision, and blocked/failure handling."),
        ("browser/driver.py", "Implements a11y and vision interaction drivers."),
        ("browser/dom.py", "Builds DOM and clickability context for browser drivers."),
        ("browser/highlight.py", "Produces visual marks for screenshot-based vision interaction."),
        ("browser/client.py", "Calls the LLM gateway for a11y chat and vision decisions."),
        ("browser/replay_report.py", "Writes Browser-attempt and session-level replay reports."),
        ("query_analysis_report.py", "Writes root-level Query_<session-id>_Analysis.md files."),
        ("skills.py", "Dispatches skills, including session_reporter."),
        ("agent_config.yaml", "Skill catalogue; formatter triggers session_reporter through internal_successors."),
        ("prompts/planner.md", "Planner and recovery guidance."),
    ]
    mapped = [
        {
            "Module": _markdown_link(path, f"S9SharedCodeVisibleAgent/code/{path}"),
            "Responsibility": desc,
        }
        for path, desc in rows
    ]
    return _markdown_table(mapped, ["Module", "Responsibility"], escape=False)


def _token_usage_note() -> str:
    return (
        "Browser a11y/vision turns record per-turn token counts in action/step "
        "records. Normal LLM skill calls are tagged with `agent` and `session` "
        "and are captured by the gateway ledger exposed at "
        "`/v1/cost/by_agent?session=<session-id>`. The session reporter now "
        "tries to include that gateway rollup in the cost summary. If the "
        "running gateway endpoint returns no rows, the reporter falls back to "
        "the local SQLite ledger at `llm_gatewayV9/gateway_v8.db`. If neither "
        "source has rows for that session, the summary falls back to node-local "
        "cost fields, which are often `0.0` for text skills."
    )


def _markdown_table(
    rows: list[dict[str, Any]],
    columns: list[str],
    *,
    escape: bool = True,
) -> str:
    if not rows:
        return "(none)"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        cells = []
        for col in columns:
            value = str(row.get(col, ""))
            cells.append(_md_cell(value) if escape else value)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _markdown_link(label: str, target: str) -> str:
    if " " in target:
        return f"[{label}](<{target}>)"
    return f"[{label}]({target})"


def _relative_path(path: Path, root_dir: Path) -> str:
    try:
        return path.resolve().relative_to(root_dir.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _json_block(value: Any) -> str:
    import json

    return json.dumps(value, indent=2, default=str)
