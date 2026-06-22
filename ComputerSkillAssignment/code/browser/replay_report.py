"""Session-tagged Visible Browser Replay Report writer.

The writer is deliberately independent of the graph orchestrator. BrowserSkill
calls it after each Browser result is packed, and Browser extensions can call
it directly when they have richer screenshots/page-state logs.
"""
from __future__ import annotations

import html
import importlib.util
import json
import re
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

from schemas import AgentResult, NodeSpec
from query_analysis_report import (
    query_analysis_metadata,
    write_query_analysis_markdown,
)


def write_session_visible_browser_report(
    *,
    session_id: str,
    query: str,
    graph_nodes: Any,
    sessions_root: Path,
    started_at: float | None = None,
    reporter_node_id: str | None = None,
) -> AgentResult:
    """Write a session-level report after the full DAG reaches Formatter."""
    session_tag = _safe_session(session_id)
    session_dir = sessions_root / session_tag
    out_dir = session_dir / "visible_browser_reports" / session_tag
    out_dir.mkdir(parents=True, exist_ok=True)

    nodes = _session_nodes(graph_nodes, reporter_node_id=reporter_node_id)
    final_answer = _latest_final_answer(nodes)
    table_rows = _session_table_rows(nodes, final_answer)
    table_markdown = _markdown_from_rows(table_rows) or final_answer
    browser_attempts = _browser_attempts(nodes)
    screenshots = _collect_session_screenshots(session_dir)
    gateway_cost = _gateway_cost_by_agent(session_tag)
    cost_summary = _session_cost_summary(nodes, browser_attempts, gateway_cost)
    payload = {
        "session_id": session_tag,
        "generated_at_unix": int(time.time()),
        "original_user_goal": query,
        "planner_dag": _session_dag(nodes),
        "full_dag_nodes": nodes,
        "recovery_path": _recovery_path(nodes),
        "browser_path_chosen": _session_browser_path(browser_attempts),
        "browser_attempts": browser_attempts,
        "browser_actions_taken": _all_browser_actions(browser_attempts),
        "screenshots_or_page_state_logs": {
            "screenshots": screenshots,
            "page_state_logs": _session_page_logs(browser_attempts),
        },
        "extracted_data": _session_extracted_data(nodes),
        "final_answer": final_answer,
        "final_comparison_table": {
            "rows": table_rows,
            "markdown": table_markdown,
        },
        "turn_count_and_cost_summary": cost_summary,
        "node_count_and_cost_summary": cost_summary,
    }

    html_path = out_dir / f"visible_browser_replay_report_{session_tag}.html"
    json_path = out_dir / f"visible_browser_replay_report_{session_tag}.json"
    analysis_root = _workspace_root()
    browser_alias_html = (
        session_dir
        / "browser"
        / "visible_browser_reports"
        / session_tag
        / f"visible_browser_replay_report_{session_tag}.html"
    )
    payload["query_analysis_report"] = query_analysis_metadata(
        session_tag,
        root_dir=analysis_root,
    )
    json_text = json.dumps(payload, indent=2)
    html_text = _render_report(payload, screenshots)
    json_path.write_text(json_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    browser_alias = _mirror_session_report_to_browser_path(
        session_dir, session_tag, html_text, json_text,
    )
    analysis_report = write_query_analysis_markdown(
        payload,
        root_dir=analysis_root,
        primary_report=html_path,
        browser_alias_report=browser_alias_html,
    )
    payload["query_analysis_report"] = analysis_report
    json_text = json.dumps(payload, indent=2)
    html_text = _render_report(payload, screenshots)
    json_path.write_text(json_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    browser_alias = _mirror_session_report_to_browser_path(
        session_dir, session_tag, html_text, json_text,
    )

    report = {
        "html": str(html_path),
        "json": str(json_path),
        "artifact_dir": str(out_dir),
        "session_id": session_tag,
    }
    return AgentResult(
        success=True,
        agent_name="session_reporter",
        output={
            "visible_browser_report": report,
            "report": report,
            "browser_report_alias": browser_alias,
            "query_analysis_report": analysis_report,
            "session_id": session_tag,
            "browser_path_chosen": payload["browser_path_chosen"],
            "final_answer": final_answer,
        },
        artifacts=[str(html_path), str(json_path), analysis_report["markdown"]]
        + [s["path"] for s in screenshots],
        elapsed_s=max(0.0, time.time() - started_at) if started_at else 0.0,
        provider="local-session-reporter",
    )


def attach_visible_browser_report(
    result: AgentResult,
    *,
    node: NodeSpec | None,
    session: str | None,
    artifacts_root: Path | None,
    started_at: float | None = None,
    report_payload: dict[str, Any] | None = None,
    screenshots: list[dict[str, str]] | None = None,
) -> AgentResult:
    """Write an HTML/JSON report and attach its paths to ``result.output``.

    ``report_payload`` is optional. When omitted, a generic report is derived
    from ``AgentResult.output`` so every BrowserSkill path gets a report,
    including extract and blocked failures.
    """
    session_tag = _safe_session(session)
    out_dir = _report_dir(artifacts_root, session_tag)
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = report_payload or _payload_from_result(result, node, session_tag)
    payload.setdefault("session_id", session_tag)
    payload.setdefault("generated_at_unix", int(time.time()))
    if started_at is not None:
        payload.setdefault("elapsed_s", max(0.0, time.time() - started_at))

    shots = screenshots or _collect_screenshots(payload, artifacts_root)
    html_path = out_dir / f"visible_browser_replay_report_{session_tag}.html"
    json_path = out_dir / f"visible_browser_replay_report_{session_tag}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    html_path.write_text(_render_report(payload, shots), encoding="utf-8")

    report = {
        "html": str(html_path),
        "json": str(json_path),
        "artifact_dir": str(out_dir),
        "session_id": session_tag,
    }
    result.output["visible_browser_report"] = report
    result.output.setdefault("report", report)
    if str(html_path) not in result.artifacts:
        result.artifacts.append(str(html_path))
    if str(json_path) not in result.artifacts:
        result.artifacts.append(str(json_path))
    return result


def _session_nodes(graph_nodes: Any, *, reporter_node_id: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node_id in sorted(list(graph_nodes), key=_node_sort_key):
        data = graph_nodes[node_id]
        result = data.get("result")
        output = result.output if isinstance(result, AgentResult) else {}
        status = data.get("status", "")
        success = result.success if isinstance(result, AgentResult) else None
        if node_id == reporter_node_id:
            status = "complete"
            success = True
        rows.append(
            {
                "node_id": node_id,
                "skill": data.get("skill", ""),
                "status": status,
                "inputs": list(data.get("inputs") or []),
                "metadata": dict(data.get("metadata") or {}),
                "success": success,
                "error": result.error if isinstance(result, AgentResult) else None,
                "error_code": result.error_code if isinstance(result, AgentResult) else None,
                "elapsed_s": result.elapsed_s if isinstance(result, AgentResult) else 0.0,
                "cost": result.cost if isinstance(result, AgentResult) else 0.0,
                "provider": result.provider if isinstance(result, AgentResult) else "",
                "output": output,
            }
        )
    return rows


def _node_sort_key(node_id: str) -> tuple[int, str]:
    try:
        return int(str(node_id).split(":", 1)[1]), str(node_id)
    except (IndexError, ValueError):
        return 10_000, str(node_id)


def _latest_final_answer(nodes: list[dict[str, Any]]) -> str:
    for node in reversed(nodes):
        if node.get("skill") == "formatter" and node.get("status") == "complete":
            answer = node.get("output", {}).get("final_answer")
            if isinstance(answer, str):
                return answer
    return ""


def _browser_attempts(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    attempts = []
    for node in nodes:
        if node.get("skill") != "browser":
            continue
        out = node.get("output") or {}
        path = out.get("path") or "blocked"
        if not node.get("success") and path == "extract":
            path = "blocked"
        attempts.append(
            {
                "node_id": node["node_id"],
                "status": node.get("status"),
                "success": node.get("success"),
                "url": out.get("url") or node.get("metadata", {}).get("url", ""),
                "goal": out.get("goal") or node.get("metadata", {}).get("goal", ""),
                "path": path,
                "turns": out.get("turns", 0),
                "actions": out.get("actions") or [],
                "final_url": out.get("final_url"),
                "error": node.get("error"),
                "error_code": node.get("error_code"),
                "report": out.get("visible_browser_report") or out.get("report"),
            }
        )
    return attempts


def _session_dag(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": node["node_id"],
                "label": node.get("skill", ""),
                "status": node.get("status", ""),
                "success": node.get("success"),
                "metadata": node.get("metadata", {}),
            }
            for node in nodes
        ],
        "edges": _session_edges(nodes),
    }


def _session_edges(nodes: list[dict[str, Any]]) -> list[list[str]]:
    node_ids = {node["node_id"] for node in nodes}
    edges: list[list[str]] = []
    for node in nodes:
        for inp in node.get("inputs") or []:
            if isinstance(inp, str) and inp in node_ids:
                edges.append([inp, node["node_id"]])
    return edges


def _recovery_path(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recovery = []
    for node in nodes:
        metadata = node.get("metadata") or {}
        if "recovers" in metadata or "failure_report" in metadata or "recovery_reason" in metadata:
            recovery.append(
                {
                    "node_id": node["node_id"],
                    "skill": node.get("skill"),
                    "status": node.get("status"),
                    "recovers": metadata.get("recovers"),
                    "recovery_reason": metadata.get("recovery_reason"),
                    "prior_complete": metadata.get("prior_complete", []),
                }
            )
    return recovery


def _session_browser_path(browser_attempts: list[dict[str, Any]]) -> str:
    if not browser_attempts:
        return "not_used"
    if any(a.get("success") for a in browser_attempts):
        for attempt in browser_attempts:
            if attempt.get("success"):
                return str(attempt.get("path") or "extract")
    return "blocked"


def _all_browser_actions(browser_attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions = []
    for attempt in browser_attempts:
        for action in attempt.get("actions") or []:
            if isinstance(action, dict):
                actions.append({"browser_node": attempt["node_id"], **action})
    return actions


def _session_page_logs(browser_attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "browser_node": attempt["node_id"],
            "url": attempt.get("url", ""),
            "final_url": attempt.get("final_url"),
            "path": attempt.get("path", ""),
            "success": attempt.get("success"),
            "error": attempt.get("error"),
            "turns": attempt.get("turns", 0),
        }
        for attempt in browser_attempts
    ]


def _session_extracted_data(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "browser_attempts": _browser_attempts(nodes),
        "researcher_outputs": [
            {
                "node_id": node["node_id"],
                "question": node.get("output", {}).get("question"),
                "sources": node.get("output", {}).get("sources", []),
                "findings": node.get("output", {}).get("findings"),
            }
            for node in nodes
            if node.get("skill") == "researcher"
        ],
        "distiller_outputs": [
            {"node_id": node["node_id"], "output": node.get("output", {})}
            for node in nodes
            if node.get("skill") == "distiller"
        ],
        "formatter_outputs": [
            {"node_id": node["node_id"], "output": node.get("output", {})}
            for node in nodes
            if node.get("skill") == "formatter"
        ],
    }


def _session_cost_summary(
    nodes: list[dict[str, Any]],
    browser_attempts: list[dict[str, Any]],
    gateway_cost: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ledger_rows = _flatten_gateway_cost(gateway_cost or {})
    ledger_cost = round(sum(float(row.get("dollars") or 0.0) for row in ledger_rows), 6)
    node_cost = round(sum(float(node.get("cost") or 0.0) for node in nodes), 6)
    ledger_providers = {row.get("provider", "") for row in ledger_rows if row.get("provider")}
    node_providers = {node.get("provider", "") for node in nodes if node.get("provider")}
    return {
        "node_count": len(nodes),
        "browser_attempt_count": len(browser_attempts),
        "browser_turn_count": sum(int(a.get("turns", 0) or 0) for a in browser_attempts),
        "completed_nodes": sum(1 for node in nodes if node.get("status") == "complete"),
        "failed_nodes": sum(1 for node in nodes if node.get("status") == "failed"),
        "llm_calls": sum(int(row.get("calls") or 0) for row in ledger_rows),
        "tokens_in": sum(int(row.get("in_tok") or 0) for row in ledger_rows),
        "tokens_out": sum(int(row.get("out_tok") or 0) for row in ledger_rows),
        "estimated_cost_usd": ledger_cost or node_cost,
        "node_result_cost_usd": node_cost,
        "gateway_ledger_cost_usd": ledger_cost,
        "providers": sorted(ledger_providers | node_providers),
        "gateway_cost_by_agent": gateway_cost or {},
    }


def _gateway_cost_by_agent(session_tag: str) -> dict[str, Any]:
    http_cost: dict[str, Any] = {}
    try:
        from gateway import LLM

        if LLM is not None:
            http_cost = LLM().cost_by_agent(session=session_tag)
    except Exception:
        http_cost = {}
    if _flatten_gateway_cost(http_cost):
        return http_cost
    return _gateway_cost_from_sqlite(session_tag)


def _gateway_cost_from_sqlite(session_tag: str) -> dict[str, Any]:
    db_path = _workspace_root() / "llm_gatewayV9" / "gateway_v8.db"
    if not db_path.exists() or db_path.stat().st_size == 0:
        return {}
    query = """
        SELECT agent, provider, COUNT(*) AS calls,
               SUM(input_tokens) AS in_tok,
               SUM(output_tokens) AS out_tok,
               SUM(latency_ms) AS total_latency_ms,
               SUM(retries) AS total_retries,
               SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) AS ok,
               SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS errors
          FROM calls
         WHERE session=? AND agent IS NOT NULL
         GROUP BY agent, provider
    """
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, (session_tag,)).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        if conn is not None:
            conn.close()
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        item = dict(row)
        agent = item.pop("agent")
        item["dollars"] = _estimate_gateway_usd(
            str(item.get("provider") or ""),
            int(item.get("in_tok") or 0),
            int(item.get("out_tok") or 0),
        )
        out.setdefault(agent, []).append(item)
    return out


def _estimate_gateway_usd(provider: str, in_tokens: int, out_tokens: int) -> float:
    pricing_path = _workspace_root() / "llm_gatewayV9" / "pricing.py"
    if not pricing_path.exists():
        return 0.0
    try:
        spec = importlib.util.spec_from_file_location("_s9_gateway_pricing", pricing_path)
        if spec is None or spec.loader is None:
            return 0.0
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return float(mod.estimate_usd(provider, in_tokens, out_tokens))
    except Exception:
        return 0.0


def _flatten_gateway_cost(gateway_cost: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for agent, agent_rows in gateway_cost.items():
        if not isinstance(agent_rows, list):
            continue
        for row in agent_rows:
            if isinstance(row, dict):
                rows.append({"agent": agent, **row})
    return rows


def _session_table_rows(nodes: list[dict[str, Any]], final_answer: str) -> list[dict[str, str]]:
    return (
        _rows_from_content(final_answer)
        or _rows_from_distiller(nodes)
        or _rows_from_numbered_list(final_answer)
    )


def _rows_from_distiller(nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    for node in reversed(nodes):
        if node.get("skill") != "distiller":
            continue
        output = node.get("output") or {}
        fields = output.get("fields")
        if isinstance(fields, dict):
            laptop_items = [
                (key, value)
                for key, value in fields.items()
                if re.match(r"^(laptop|product|item)_?\d+", str(key))
            ]
            if laptop_items:
                rows = []
                for _, value in sorted(laptop_items, key=lambda item: _natural_key(item[0])):
                    product, details = _split_product_details(str(value))
                    rows.append({"Product": product, "Details": details})
                return rows
        for key in ("records", "items", "products", "laptops"):
            records = output.get(key)
            if isinstance(records, list) and all(isinstance(r, dict) for r in records):
                return [{str(k): str(v) for k, v in record.items()} for record in records]
    return []


def _rows_from_numbered_list(text: str) -> list[dict[str, str]]:
    rows = []
    for line in (text or "").splitlines():
        match = re.match(r"^\s*\d+\.\s*([^:]+):\s*(.+?)\s*$", line)
        if match:
            rows.append({"Product": match.group(1).strip(), "Details": match.group(2).strip()})
    return rows


def _split_product_details(value: str) -> tuple[str, str]:
    match = re.match(r"^(.*?)\s*\((.*)\)\s*$", value)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return value.strip(), ""


def _natural_key(value: Any) -> tuple[str, int]:
    text = str(value)
    match = re.search(r"(\d+)", text)
    return re.sub(r"\d+", "", text), int(match.group(1)) if match else 0


def _markdown_from_rows(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    columns = list(rows[0].keys())
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md_cell(row.get(col, "")) for col in columns) + " |")
    return "\n".join(lines)


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _mirror_session_report_to_browser_path(
    session_dir: Path,
    session_tag: str,
    html_text: str,
    json_text: str,
) -> dict[str, str]:
    legacy_dir = session_dir / "browser" / "visible_browser_reports" / session_tag
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_html = legacy_dir / f"visible_browser_replay_report_{session_tag}.html"
    legacy_json = legacy_dir / f"visible_browser_replay_report_{session_tag}.json"
    attempt_html = legacy_dir / f"browser_attempt_replay_report_{session_tag}.html"
    attempt_json = legacy_dir / f"browser_attempt_replay_report_{session_tag}.json"

    if legacy_json.exists() and not _json_has_full_session(legacy_json):
        if legacy_html.exists() and not attempt_html.exists():
            shutil.copy2(legacy_html, attempt_html)
        if not attempt_json.exists():
            shutil.copy2(legacy_json, attempt_json)

    legacy_html.write_text(html_text, encoding="utf-8")
    legacy_json.write_text(json_text, encoding="utf-8")
    return {
        "html": str(legacy_html),
        "json": str(legacy_json),
        "artifact_dir": str(legacy_dir),
    }


def _json_has_full_session(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return "full_dag_nodes" in payload and "final_answer" in payload


def _collect_session_screenshots(session_dir: Path) -> list[dict[str, str]]:
    browser_dir = session_dir / "browser"
    if not browser_dir.exists():
        return []
    shots = []
    for path in sorted(browser_dir.rglob("*.png")):
        if "visible_browser_reports" in path.parts:
            continue
        label = f"{path.parent.name}/{path.stem}"
        shots.append({"label": label, "path": str(path)})
    return shots


def _payload_from_result(
    result: AgentResult,
    node: NodeSpec | None,
    session_tag: str,
) -> dict[str, Any]:
    out = result.output or {}
    goal = out.get("goal") or (node.metadata.get("goal") if node else "") or ""
    path = out.get("path") or ("blocked" if not result.success else "extract")
    if not result.success and path == "extract":
        path = "blocked" if result.error_code == "gateway_blocked" else "blocked"
    actions = out.get("actions") or []
    content = out.get("content")
    rows = _rows_from_content(content)
    return {
        "session_id": session_tag,
        "original_user_goal": goal,
        "planner_dag": _browser_node_dag(node, path),
        "browser_path_chosen": path,
        "browser_actions_taken": actions,
        "screenshots_or_page_state_logs": {
            "screenshots": [],
            "page_state_logs": _page_logs_from_result(result),
        },
        "extracted_data": {
            "url": out.get("url", ""),
            "final_url": out.get("final_url", ""),
            "content": content,
            "error": result.error,
            "error_code": result.error_code,
        },
        "final_comparison_table": {
            "rows": rows,
            "markdown": content or "",
        },
        "turn_count_and_cost_summary": {
            "turn_count": out.get("turns", len(actions) if isinstance(actions, list) else 0),
            "llm_calls": len(actions) if path in ("a11y", "vision") else 0,
            "tokens_in": _sum_step_tokens(actions, "tokens_in"),
            "tokens_out": _sum_step_tokens(actions, "tokens_out"),
            "estimated_cost_usd": result.cost,
            "provider": result.provider,
        },
    }


def _browser_node_dag(node: NodeSpec | None, path: str) -> dict[str, Any]:
    metadata = dict(node.metadata) if node else {}
    return {
        "nodes": [
            {"id": "user_goal", "label": "User Goal"},
            {"id": "planner", "label": "Planner"},
            {"id": "browser", "label": "Browser Skill"},
            {"id": path, "label": f"Browser path: {path}"},
            {"id": "report", "label": "Visible Browser Replay Report"},
        ],
        "edges": [
            ["user_goal", "planner"],
            ["planner", "browser"],
            ["browser", path],
            [path, "report"],
        ],
        "browser_node_metadata": metadata,
    }


def _page_logs_from_result(result: AgentResult) -> list[dict[str, Any]]:
    out = result.output or {}
    return [
        {
            "url": out.get("url", ""),
            "final_url": out.get("final_url", ""),
            "path": out.get("path", ""),
            "success": result.success,
            "error": result.error,
            "content_chars": len(out.get("content") or ""),
        }
    ]


def _collect_screenshots(
    payload: dict[str, Any],
    artifacts_root: Path | None,
) -> list[dict[str, str]]:
    existing = (
        payload.get("screenshots_or_page_state_logs", {}).get("screenshots", [])
        if isinstance(payload.get("screenshots_or_page_state_logs"), dict)
        else []
    )
    if existing:
        return existing
    if not artifacts_root or not artifacts_root.exists():
        return []
    shots = []
    for path in sorted(artifacts_root.rglob("*.png")):
        shots.append({"label": path.stem, "path": str(path)})
    payload.setdefault("screenshots_or_page_state_logs", {})["screenshots"] = shots
    return shots


def _report_dir(artifacts_root: Path | None, session_tag: str) -> Path:
    if artifacts_root is not None:
        return artifacts_root / "visible_browser_reports" / session_tag
    return Path(__file__).resolve().parents[1] / "state" / "visible_browser_reports" / session_tag


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _safe_session(session: str | None) -> str:
    raw = session or "no_sessionid"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("_")
    return safe or "no_sessionid"


def _rows_from_content(content: Any) -> list[dict[str, str]]:
    if not isinstance(content, str) or "|" not in content:
        return []
    lines = [line.strip() for line in content.splitlines() if line.strip().startswith("|")]
    if len(lines) < 3:
        return []
    headers = [part.strip() for part in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        values = [part.strip() for part in line.strip("|").split("|")]
        if len(values) == len(headers):
            rows.append(dict(zip(headers, values)))
    return rows


def _sum_step_tokens(actions: Any, key: str) -> int:
    if not isinstance(actions, list):
        return 0
    total = 0
    for action in actions:
        if isinstance(action, dict):
            total += int(action.get(key, 0) or 0)
    return total


def _render_report(payload: dict[str, Any], screenshots: list[dict[str, str]]) -> str:
    rows = payload.get("final_comparison_table", {}).get("rows") or []
    actions = payload.get("browser_actions_taken") or []
    page_logs = payload.get("screenshots_or_page_state_logs", {}).get("page_state_logs") or []
    full_nodes = payload.get("full_dag_nodes") or []
    recovery = payload.get("recovery_path") or []
    browser_attempts = payload.get("browser_attempts") or []
    image_blocks = "\n".join(_image_block(s) for s in screenshots)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Visible Browser Replay Report {html.escape(str(payload.get("session_id", "")))}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #172033; background: #f6f7f9; }}
    header, section {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    header {{ background: #172033; color: white; max-width: none; }}
    header div {{ max-width: 1120px; margin: 0 auto; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; }}
    h2 {{ margin-top: 0; }}
    table {{ border-collapse: collapse; width: 100%; background: white; }}
    th, td {{ border: 1px solid #d9dee7; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #edf0f5; }}
    pre {{ background: #eef1f5; border-radius: 4px; padding: 12px; overflow: auto; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    figure {{ margin: 0; background: white; border: 1px solid #d9dee7; padding: 10px; }}
    img {{ width: 100%; height: auto; border: 1px solid #ccd2dc; }}
    figcaption {{ margin-top: 8px; font-size: 13px; color: #4c566a; }}
  </style>
</head>
<body>
  <header><div>
    <h1>Visible Browser Replay Report</h1>
    <p>Session: <strong>{html.escape(str(payload.get("session_id", "")))}</strong>. Path: <strong>{html.escape(str(payload.get("browser_path_chosen", "")))}</strong>. Turns: <strong>{html.escape(str(payload.get("turn_count_and_cost_summary", {}).get("turn_count", 0)))}</strong>.</p>
  </div></header>
  <section><h2>1. Original User Goal</h2><p>{html.escape(str(payload.get("original_user_goal", "")))}</p></section>
  <section><h2>2. Planner DAG</h2><pre>{html.escape(json.dumps(payload.get("planner_dag", {}), indent=2))}</pre></section>
  <section><h2>3. Browser Path Chosen</h2><p>{html.escape(str(payload.get("browser_path_chosen", "")))}</p></section>
  <section><h2>4. Browser Actions Taken</h2>{_html_table(actions, _columns(actions, ["browser_node", "turn", "type", "description", "outcome"]))}</section>
  <section><h2>5. Screenshots Or Page-State Logs</h2><div class="grid">{image_blocks}</div><h3>Page State Logs</h3><pre>{html.escape(json.dumps(page_logs, indent=2))}</pre></section>
  <section><h2>6. Extracted Data</h2><pre>{html.escape(json.dumps(payload.get("extracted_data", {}), indent=2))}</pre></section>
  <section><h2>7. Final Comparison Table</h2>{_table_or_pre(rows, payload.get("final_comparison_table", {}).get("markdown", ""))}</section>
  <section><h2>8. Turn Count And Cost Summary</h2><pre>{html.escape(json.dumps(payload.get("turn_count_and_cost_summary", {}), indent=2))}</pre></section>
  <section><h2>Full DAG Nodes</h2>{_html_table(full_nodes, ["node_id", "skill", "status", "success", "error_code", "elapsed_s"])}</section>
  <section><h2>Recovery Path</h2>{_html_table(recovery, ["node_id", "skill", "status", "recovers", "recovery_reason"])}</section>
  <section><h2>Browser Attempts</h2>{_html_table(browser_attempts, ["node_id", "status", "success", "path", "turns", "url", "error_code", "error"])}</section>
  <section><h2>Final Answer</h2><pre>{html.escape(str(payload.get("final_answer", "")))}</pre></section>
  <section><h2>Query Analysis Markdown</h2>{_analysis_report_link(payload.get("query_analysis_report") or {})}</section>
</body>
</html>
"""


def _image_block(shot: dict[str, str]) -> str:
    path = Path(shot.get("path", ""))
    label = shot.get("label") or path.stem
    src = html.escape(str(path))
    return f'<figure><img src="{src}" alt="{html.escape(label)}"><figcaption>{html.escape(label)}</figcaption></figure>'


def _table_or_pre(rows: list[dict[str, Any]], markdown: str) -> str:
    if rows:
        columns = list(rows[0].keys())
        return _html_table(rows, columns)
    return f"<pre>{html.escape(markdown or '(no comparison table)')}</pre>"


def _html_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "<p>(none)</p>"
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(c, '')))}</td>" for c in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _analysis_report_link(report: dict[str, Any]) -> str:
    path = str(report.get("markdown") or "")
    label = str(report.get("relative_path") or path)
    if not path:
        return "<p>(none)</p>"
    return f'<p><a href="{html.escape(path)}">{html.escape(label)}</a></p>'


def _columns(rows: list[dict[str, Any]], preferred: list[str]) -> list[str]:
    if not rows:
        return preferred
    seen = set()
    cols = []
    for col in preferred:
        if any(col in row for row in rows):
            cols.append(col)
            seen.add(col)
    for row in rows:
        for col in row:
            if col not in seen and len(cols) < 8:
                cols.append(col)
                seen.add(col)
    return cols
