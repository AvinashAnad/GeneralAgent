"""Accessibility-tree parsing and compact summaries for ComputerSkill."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AxCandidate:
    element_index: int
    role: str = ""
    label: str = ""
    value: str = ""


INDEXED_QUOTED_RE = re.compile(
    r"\[element_index\s+(?P<idx>\d+)\]\s+(?P<role>\w+)(?:\s+\"(?P<label>[^\"]*)\")?",
    re.IGNORECASE,
)
CUA_BULLET_RE = re.compile(
    r"-\s+\[(?P<idx>\d+)\]\s+(?P<role>AX\w+)(?:\s+(?:\"(?P<quoted>[^\"]*)\"|\((?P<paren>[^)]*)\)))?",
)
STATIC_TEXT_RE = re.compile(r"AXStaticText[^\"\n]*\"(?P<value>[^\"]*)\"")


def extract_ax_candidates(markdown: str, *, dedupe: bool = True,
                          limit: int | None = None) -> list[AxCandidate]:
    rows: list[AxCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for line in str(markdown or "").splitlines():
        candidate: AxCandidate | None = None
        m = INDEXED_QUOTED_RE.search(line)
        if m:
            candidate = AxCandidate(
                element_index=int(m.group("idx")),
                role=m.group("role") or "",
                label=(m.group("label") or "").strip(),
            )
        else:
            m = CUA_BULLET_RE.search(line)
            if m:
                candidate = AxCandidate(
                    element_index=int(m.group("idx")),
                    role=m.group("role") or "",
                    label=((m.group("quoted") or m.group("paren") or "").strip()),
                )
        if not candidate:
            continue
        key = (candidate.role.lower(), candidate.label.lower(), candidate.value.lower())
        if dedupe and key in seen:
            continue
        seen.add(key)
        rows.append(candidate)
        if limit and len(rows) >= limit:
            break
    return rows


def summarize_state(state: dict[str, Any], *, candidates: list[AxCandidate] | None = None) -> dict[str, Any]:
    markdown = str(state.get("tree_markdown") or "")
    candidates = candidates if candidates is not None else extract_ax_candidates(markdown, limit=40)
    return {
        "pid": state.get("pid"),
        "window_id": state.get("window_id"),
        "title": state.get("title") or state.get("window_title"),
        "element_count": state.get("element_count"),
        "candidates": [c.__dict__ for c in candidates[:40]],
        "static_text": STATIC_TEXT_RE.findall(markdown)[:20],
        "preview": markdown[:1600],
    }


def is_opaque_electron_tree(state: dict[str, Any]) -> bool:
    count = int(state.get("element_count") or 0)
    markdown = str(state.get("tree_markdown") or "").lower()
    if count <= 2 and any(s in markdown for s in ("axwebarea", "webview", "electron", "chromium")):
        return True
    return count <= 1 and not extract_ax_candidates(markdown)


def has_too_many_candidates(markdown: str, *, candidate_budget: int = 160) -> bool:
    return len(extract_ax_candidates(markdown, limit=candidate_budget + 1)) > candidate_budget
