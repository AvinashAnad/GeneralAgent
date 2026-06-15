"""Run the visible Browser skill extension and write its replay report.

Usage:
    python run_visible_browser_agent.py
    python run_visible_browser_agent.py --session-id demo-visible

The extension is invoked through BrowserSkill, not through any orchestrator
change. It performs visible browser actions against a local product catalogue
fixture and writes an HTML replay viewer plus JSON report under state/.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from browser.skill import BrowserSkill
from browser.visible_catalog_extension import ORIGINAL_GOAL
from schemas import NodeSpec


ROOT = Path(__file__).resolve().parent


async def _run(session_id: str) -> int:
    node = NodeSpec(
        skill="browser",
        inputs=[],
        metadata={
            "browser_extension": "visible_catalog_report",
            "goal": ORIGINAL_GOAL,
            "run_id": session_id,
        },
    )
    skill = BrowserSkill(
        artifacts_root=str(ROOT / "state" / "sessions" / session_id / "browser"),
        session=session_id,
    )
    result = await skill.run(node)
    print(json.dumps({
        "success": result.success,
        "provider": result.provider,
        "elapsed_s": round(result.elapsed_s, 3),
        "report": result.output.get("report"),
        "path": result.output.get("path"),
        "turns": result.output.get("turns"),
        "cost_summary": result.output.get("cost_summary"),
    }, indent=2))
    if result.output.get("content"):
        print("\nFinal comparison table:\n")
        print(result.output["content"])
    if not result.success:
        if result.error:
            print(f"\nError: {result.error}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--session-id",
        default=f"visible-{int(time.time())}",
        help="Session/report id under code/state/sessions.",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.session_id))


if __name__ == "__main__":
    raise SystemExit(main())

