from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from browser_report import normalize_browser_path, visible_actions_count
from paths import REPORTS_ROOT, S9_CODE_ROOT, ensure_s9_path

ensure_s9_path()

from persistence import SessionStore  # noqa: E402
from schemas import AgentResult, NodeState  # noqa: E402


def _json(value: Any, limit: int = 6000) -> str:
    try:
        text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    return text if len(text) <= limit else text[:limit] + "\n..."


def _load_graph_summary(session_id: str) -> str:
    path = S9_CODE_ROOT / "state" / "sessions" / session_id / "graph.json"
    if not path.exists():
        return "(graph.json not found)"
    data = json.loads(path.read_text(encoding="utf-8"))
    node_lines = []
    for node in data.get("nodes", []):
        node_lines.append(
            f"- `{node.get('id')}` `{node.get('skill')}` "
            f"status=`{node.get('status')}` inputs={node.get('inputs') or []}"
        )
    edge_lines = [
        f"- `{edge.get('source')}` -> `{edge.get('target')}`"
        for edge in data.get("edges", [])
    ]
    if not edge_lines:
        edge_lines = ["- (no persisted edges)"]
    return "\n".join(["### Nodes", *node_lines, "", "### Edges", *edge_lines])


def _browser_nodes(states: list[NodeState]) -> list[NodeState]:
    return [
        st for st in states
        if st.skill == "browser"
        and st.result is not None
    ]


def _iter_browser_result_blocks(st: NodeState) -> list[dict[str, Any]]:
    result = st.result
    if result is None:
        return []
    output = result.output or {}
    return [{
        "node": st.node_id,
        "skill": st.skill,
        "url": output.get("url"),
        "path": normalize_browser_path(result),
        "turns": output.get("turns") or 0,
        "visible_actions": visible_actions_count(output.get("actions") or []),
        "actions": output.get("actions") or [],
        "content": output.get("content") or "",
        "error": result.error,
    }]


def _artifact_listing(session_id: str) -> str:
    root = S9_CODE_ROOT / "state" / "sessions" / session_id / "browser"
    if not root.exists():
        return "(no Browser artifact directory found)"
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and (
            p.name.endswith(".png") or p.name.endswith(".txt")
        )
    )
    if not files:
        return "(no screenshots or page-state logs found)"
    lines = []
    for p in files[:80]:
        lines.append(f"- `{p}`")
    if len(files) > 80:
        lines.append(f"- ... {len(files) - 80} more artifact file(s)")
    return "\n".join(lines)


def _cost_summary(session_id: str) -> str:
    try:
        r = httpx.get(
            "http://localhost:8109/v1/cost/by_agent",
            params={"session": session_id},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        return f"(cost unavailable: {type(exc).__name__}: {exc})"
    if not data:
        return "(no gateway ledger rows for this session)"
    rows = ["| Agent | Provider | Calls | Input | Output | Dollars |",
            "| --- | --- | ---: | ---: | ---: | ---: |"]
    for agent, providers in sorted(data.items()):
        for row in providers:
            rows.append(
                f"| {agent} | {row.get('provider')} | {row.get('calls')} | "
                f"{row.get('in_tok') or 0} | {row.get('out_tok') or 0} | "
                f"{float(row.get('dollars') or 0):.6f} |"
            )
    return "\n".join(rows)


def _final_answer(states: list[NodeState]) -> str:
    for st in reversed(states):
        if st.skill == "formatter" and st.result and st.result.output:
            answer = st.result.output.get("final_answer")
            if isinstance(answer, str):
                return answer
    return "(no formatter final answer found)"


def _distilled_data(states: list[NodeState]) -> str:
    for st in reversed(states):
        if st.skill == "distiller" and st.result:
            return _json(st.result.output, limit=8000)
    return "(no distiller output found)"


def _turn_summary(states: list[NodeState]) -> str:
    total_turns = 0
    visible = 0
    rows = ["| Node | Path | Turns | Visible actions |",
            "| --- | --- | ---: | ---: |"]
    for st in _browser_nodes(states):
        for block in _iter_browser_result_blocks(st):
            turns = int(block.get("turns") or 0)
            actions = int(block.get("visible_actions") or 0)
            total_turns += turns
            visible += actions
            rows.append(
                f"| {block.get('node')} | {block.get('path')} | "
                f"{turns} | {actions} |"
            )
    rows.append(f"| **Total** |  | **{total_turns}** | **{visible}** |")
    return "\n".join(rows)


def render_report(session_id: str) -> str:
    store = SessionStore(session_id)
    states = store.read_all_nodes()
    query = store.read_query() or ""

    browser_blocks = []
    for st in _browser_nodes(states):
        for block in _iter_browser_result_blocks(st):
            browser_blocks.append(block)

    path_lines = [
        f"- `{b['node']}` {b.get('url') or ''}: **{b.get('path')}**"
        for b in browser_blocks
    ] or ["- (no Browser nodes found)"]

    action_sections = []
    for block in browser_blocks:
        action_sections.append(
            f"### {block['node']} {block.get('url') or ''}\n\n"
            f"```json\n{_json(block.get('actions') or [], limit=5000)}\n```"
        )

    content_sections = []
    for block in browser_blocks:
        content = block.get("content") or block.get("error") or "(no content)"
        content_sections.append(
            f"### {block['node']} {block.get('url') or ''}\n\n"
            f"```text\n{str(content)[:5000]}\n```"
        )

    return "\n\n".join([
        f"# Replay Report: {session_id}",
        "## 1. Original User Goal",
        query or "(query not found)",
        "## 2. Planner DAG",
        _load_graph_summary(session_id),
        "## 3. Browser Path Chosen",
        "\n".join(path_lines),
        "## 4. Browser Actions Taken",
        "\n\n".join(action_sections) or "(no Browser actions found)",
        "## 5. Screenshots Or Page-State Logs",
        _artifact_listing(session_id),
        "## 6. Extracted Data",
        _distilled_data(states),
        "## 7. Final Comparison Table",
        _final_answer(states),
        "## 8. Turn Count And Cost Summary",
        _turn_summary(states),
        "### Cost",
        _cost_summary(session_id),
        "## Browser Extracted Page Evidence",
        "\n\n".join(content_sections) or "(no Browser evidence found)",
    ]) + "\n"


def write_report(session_id: str, reports_root: Path = REPORTS_ROOT) -> Path:
    out_dir = reports_root / session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    content = render_report(session_id)
    path = out_dir / "replay_report.md"
    path.write_text(content, encoding="utf-8")
    latest = reports_root.parent / "latest_replay_report.md"
    latest.write_text(content, encoding="utf-8")
    return path
