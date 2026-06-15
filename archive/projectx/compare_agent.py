from __future__ import annotations

import argparse
import asyncio
import uuid

from llm_delay import install_project_llm_delay
from paths import ensure_s9_path
from project_registry import ProjectSkillRegistry
from replay_report import write_report

ensure_s9_path()

from flow import Executor  # noqa: E402


async def run(query: str, *, session_id: str | None = None,
              resume: bool = False, report: bool = True) -> tuple[str, str]:
    delay_s, provider_name, browser_provider_name = install_project_llm_delay()
    if delay_s > 0:
        print(f"[projectx] delaying {delay_s:g}s before each Project X LLM call")
    if provider_name:
        print(f"[projectx] forcing Project X text-skill LLM provider -> {provider_name}")
    print(f"[projectx] Browser LLM provider -> {browser_provider_name or 'auto'}")
    sid = session_id or f"px-{uuid.uuid4().hex[:8]}"
    answer = await Executor(registry=ProjectSkillRegistry()).run(
        query, session_id=sid, resume=resume,
    )
    if report:
        report_path = write_report(sid)
        print(f"[projectx] replay report -> {report_path}")
    return sid, answer


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Project X browser comparison agent."
    )
    parser.add_argument("query", nargs="+", help="comparison query to run")
    parser.add_argument("--session", help="explicit session id")
    parser.add_argument("--resume", action="store_true", help="resume the session")
    parser.add_argument("--no-report", action="store_true", help="skip report generation")
    args = parser.parse_args()

    query = " ".join(args.query)
    sid, _ = asyncio.run(run(
        query, session_id=args.session, resume=args.resume,
        report=not args.no_report,
    ))
    print(f"[projectx] session -> {sid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
