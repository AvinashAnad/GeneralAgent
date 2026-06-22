"""Deterministic Browser skill extension for visible product comparison.

This extension is intentionally local and deterministic: it drives a small
HTML catalogue through Playwright, performs visible UI actions, and writes a
replay report. It plugs into ``BrowserSkill.run`` through
``metadata.browser_extension == "visible_catalog_report"`` so the graph
orchestrator does not need any changes.
"""
from __future__ import annotations

import asyncio
import html
import json
import time
from pathlib import Path
from typing import Any

from playwright.async_api import Page, async_playwright

from schemas import AgentResult, NodeSpec

from .replay_report import attach_visible_browser_report


ORIGINAL_GOAL = (
    "Compare portable electronics products by actively using browser UI: "
    "search, filter, sort, open a product detail page, switch tabs, expand "
    "hidden content, submit a form, then produce a replay report and final "
    "comparison table. Passive scraping from search snippets is not accepted."
)

PLANNER_DAG = {
    "nodes": [
        {"id": "user_goal", "label": "User Goal"},
        {"id": "planner", "label": "Planner"},
        {"id": "browser", "label": "Browser Skill Extension"},
        {"id": "deterministic", "label": "Deterministic UI path"},
        {"id": "distiller", "label": "Extract displayed product data"},
        {"id": "report", "label": "Replay Viewer / Report"},
        {"id": "table", "label": "Final Comparison Table"},
    ],
    "edges": [
        ["user_goal", "planner"],
        ["planner", "browser"],
        ["browser", "deterministic"],
        ["deterministic", "distiller"],
        ["distiller", "report"],
        ["report", "table"],
    ],
}


async def run_visible_catalog_report(
    node: NodeSpec,
    *,
    artifacts_root: Path | None,
    session: str | None,
) -> AgentResult:
    """Run the local catalogue workflow and return an AgentResult.

    The returned output follows the BrowserOutput shape where useful
    (url/goal/path/turns/content/actions/final_url) and adds report-specific
    fields consumed by the generated replay viewer.
    """
    started = time.time()
    goal = node.metadata.get("goal") or ORIGINAL_GOAL
    run_id = node.metadata.get("run_id") or session or f"visible-catalog-{int(started)}"
    base_dir = Path(__file__).resolve().parent
    fixture = base_dir / "fixtures" / "visible_catalog.html"
    if not fixture.exists():
        return AgentResult(
            success=False,
            agent_name="browser",
            output={
                "url": "",
                "goal": goal,
                "path": "blocked",
                "turns": 0,
                "actions": [],
            },
            error=f"missing fixture: {fixture}",
            error_code="interaction_failed",
            elapsed_s=time.time() - started,
        )

    root = artifacts_root or base_dir.parent / "state" / "visible_catalog"
    out_dir = root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    start_url = fixture.resolve().as_uri()
    actions: list[dict[str, Any]] = []
    page_logs: list[dict[str, Any]] = []
    screenshots: list[dict[str, str]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1366, "height": 900})
        page = await ctx.new_page()
        await page.goto(start_url, wait_until="networkidle")
        await _record(page, out_dir, "00_initial_catalog", actions, page_logs, screenshots)

        await _fill(page, "#catalog-search", "portable")
        await _record(page, out_dir, "01_search_portable", actions, page_logs, screenshots)
        actions.append(_action(1, "search", "Typed portable into the catalogue search box."))

        await page.select_option("#category-filter", "Electronics")
        await _record(page, out_dir, "02_filter_electronics", actions, page_logs, screenshots)
        actions.append(_action(2, "filter", "Selected the Electronics category filter."))

        await page.select_option("#sort-select", "price-asc")
        await _record(page, out_dir, "03_sort_price_low", actions, page_logs, screenshots)
        actions.append(_action(3, "sort", "Sorted visible products by price low to high."))

        async with ctx.expect_page() as detail_info:
            await page.locator('[data-product-id="travel-charger"] .details-link').click()
        detail = await detail_info.value
        await detail.wait_for_load_state("networkidle")
        await detail.bring_to_front()
        await _record(detail, out_dir, "04_open_detail_new_tab", actions, page_logs, screenshots)
        actions.append(_action(4, "open_detail", "Opened Travel Charger details in a new tab."))

        await page.bring_to_front()
        await _record(page, out_dir, "05_switch_back_to_results_tab", actions, page_logs, screenshots)
        actions.append(_action(5, "switch_tab", "Switched back to the filtered results tab."))

        await detail.bring_to_front()
        await _record(detail, out_dir, "06_switch_to_detail_tab", actions, page_logs, screenshots)
        actions.append(_action(6, "switch_tab", "Switched again to the product detail tab."))

        await detail.locator('[data-tab="specs"]').click()
        await _record(detail, out_dir, "07_detail_specs_tab", actions, page_logs, screenshots)
        actions.append(_action(7, "switch_detail_tab", "Selected the Specs tab inside product details."))

        await detail.locator("#show-more").click()
        await _record(detail, out_dir, "08_expand_hidden_content", actions, page_logs, screenshots)
        actions.append(_action(8, "expand_hidden_content", "Expanded the hidden compatibility note."))

        await detail.locator("#buyer-name").fill("Avi")
        await detail.locator("#buyer-email").fill("avi@example.com")
        await detail.locator("#notify-form").locator('button[type="submit"]').click()
        await _record(detail, out_dir, "09_submit_form", actions, page_logs, screenshots)
        actions.append(_action(9, "submit_form", "Submitted the product notification form."))

        extracted_data = await _extract_products(page)
        detail_data = await _extract_detail(detail)
        await browser.close()

    comparison_rows = _comparison_rows(extracted_data, detail_data)
    table_md = _comparison_table_markdown(comparison_rows)
    cost_summary = {
        "turn_count": len(actions),
        "llm_calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "estimated_cost_usd": 0.0,
        "provider": "deterministic-playwright",
    }
    payload = {
        "original_user_goal": goal,
        "planner_dag": PLANNER_DAG,
        "browser_path_chosen": "deterministic",
        "browser_actions_taken": actions,
        "screenshots_or_page_state_logs": {
            "screenshots": screenshots,
            "page_state_logs": page_logs,
        },
        "extracted_data": {
            "results_page_products": extracted_data,
            "detail_page": detail_data,
        },
        "final_comparison_table": {
            "rows": comparison_rows,
            "markdown": table_md,
        },
        "turn_count_and_cost_summary": cost_summary,
    }

    output = {
        "url": start_url,
        "goal": goal,
        "path": "deterministic",
        "turns": len(actions),
        "content": table_md,
        "actions": actions,
        "final_url": detail_data.get("url"),
        "planner_dag": PLANNER_DAG,
        "screenshots": screenshots,
        "page_state_logs": page_logs,
        "extracted_data": payload["extracted_data"],
        "final_comparison_table": payload["final_comparison_table"],
        "cost_summary": cost_summary,
    }
    result = AgentResult(
        success=True,
        agent_name="browser",
        output=output,
        artifacts=[s["path"] for s in screenshots],
        cost=0.0,
        elapsed_s=time.time() - started,
        provider="deterministic-playwright",
    )
    return attach_visible_browser_report(
        result,
        node=node,
        session=session or run_id,
        artifacts_root=artifacts_root,
        started_at=started,
        report_payload=payload,
        screenshots=screenshots,
    )


def _action(turn: int, kind: str, description: str) -> dict[str, Any]:
    return {
        "turn": turn,
        "type": kind,
        "description": description,
        "outcome": "ok",
        "visible_browser_action": True,
    }


async def _fill(page: Page, selector: str, value: str) -> None:
    await page.locator(selector).fill(value)
    await page.wait_for_timeout(150)


async def _record(
    page: Page,
    out_dir: Path,
    label: str,
    actions: list[dict[str, Any]],
    page_logs: list[dict[str, Any]],
    screenshots: list[dict[str, str]],
) -> None:
    await page.wait_for_timeout(150)
    png = out_dir / f"{label}.png"
    state_path = out_dir / f"{label}.json"
    await page.screenshot(path=str(png), full_page=True)
    visible_products = await page.locator(".product-card:visible").evaluate_all(
        """cards => cards.map(card => ({
            id: card.dataset.productId || "",
            name: card.querySelector(".product-name")?.textContent.trim() || "",
            price: card.querySelector(".price")?.textContent.trim() || "",
            rating: card.querySelector(".rating")?.textContent.trim() || "",
            stock: card.querySelector(".stock")?.textContent.trim() || ""
        }))"""
    )
    state = {
        "label": label,
        "url": page.url,
        "title": await page.title(),
        "visible_product_count": len(visible_products),
        "visible_products": visible_products,
        "active_detail_title": await _text_or_empty(page, "#detail-title"),
        "form_status": await _text_or_empty(page, "#form-status"),
        "actions_recorded_so_far": len(actions),
    }
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    screenshots.append({"label": label, "path": str(png)})
    page_logs.append(state)


async def _text_or_empty(page: Page, selector: str) -> str:
    loc = page.locator(selector)
    if await loc.count() == 0:
        return ""
    try:
        if not await loc.first.is_visible():
            return ""
        return (await loc.first.inner_text()).strip()
    except Exception:
        return ""


async def _extract_products(page: Page) -> list[dict[str, Any]]:
    return await page.locator(".product-card:visible").evaluate_all(
        """cards => cards.map(card => ({
            id: card.dataset.productId || "",
            product: card.querySelector(".product-name")?.textContent.trim() || "",
            category: card.dataset.category || "",
            price_usd: Number(card.dataset.price || 0),
            rating: Number(card.dataset.rating || 0),
            stock: card.querySelector(".stock")?.textContent.trim() || "",
            summary: card.querySelector(".summary")?.textContent.trim() || ""
        }))"""
    )


async def _extract_detail(page: Page) -> dict[str, Any]:
    return await page.evaluate(
        """() => ({
            url: location.href,
            product: document.querySelector("#detail-title")?.textContent.trim() || "",
            price: document.querySelector("#detail-price")?.textContent.trim() || "",
            active_tab: document.querySelector(".tab.active")?.textContent.trim() || "",
            specs: Array.from(document.querySelectorAll("#specs-panel li")).map(li => li.textContent.trim()),
            expanded_note: document.querySelector("#compatibility-note")?.textContent.trim() || "",
            form_status: document.querySelector("#form-status")?.textContent.trim() || ""
        })"""
    )


def _comparison_rows(
    products: list[dict[str, Any]],
    detail: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    detail_product = detail.get("product", "")
    specs = "; ".join(detail.get("specs") or [])
    for product in products:
        rows.append(
            {
                "product": product.get("product", ""),
                "category": product.get("category", ""),
                "price_usd": product.get("price_usd", 0),
                "rating": product.get("rating", 0),
                "stock": product.get("stock", ""),
                "summary": product.get("summary", ""),
                "detail_checked": "yes" if product.get("product") == detail_product else "no",
                "detail_specs": specs if product.get("product") == detail_product else "",
            }
        )
    return rows


def _comparison_table_markdown(rows: list[dict[str, Any]]) -> str:
    headers = [
        "Product",
        "Category",
        "Price",
        "Rating",
        "Stock",
        "Detail checked",
        "Detail specs",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append(
            "| {product} | {category} | ${price:.2f} | {rating:.1f} | {stock} | {checked} | {specs} |".format(
                product=_md(row["product"]),
                category=_md(row["category"]),
                price=float(row["price_usd"]),
                rating=float(row["rating"]),
                stock=_md(row["stock"]),
                checked=_md(row["detail_checked"]),
                specs=_md(row["detail_specs"] or "-"),
            )
        )
    return "\n".join(lines)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _render_report(payload: dict[str, Any], screenshots: list[dict[str, str]]) -> str:
    table_rows = payload["final_comparison_table"]["rows"]
    action_rows = payload["browser_actions_taken"]
    page_logs = payload["screenshots_or_page_state_logs"]["page_state_logs"]
    img_blocks = "\n".join(
        f'<figure><img src="{html.escape(Path(s["path"]).name)}" alt="{html.escape(s["label"])}">'
        f'<figcaption>{html.escape(s["label"])}</figcaption></figure>'
        for s in screenshots
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Visible Browser Replay Report</title>
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
    code, pre {{ background: #eef1f5; border-radius: 4px; }}
    pre {{ padding: 12px; overflow: auto; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    figure {{ margin: 0; background: white; border: 1px solid #d9dee7; padding: 10px; }}
    img {{ width: 100%; height: auto; border: 1px solid #ccd2dc; }}
    figcaption {{ margin-top: 8px; font-size: 13px; color: #4c566a; }}
  </style>
</head>
<body>
  <header><div>
    <h1>Visible Browser Replay Report</h1>
    <p>Path chosen: <strong>{html.escape(payload["browser_path_chosen"])}</strong>. Turn count: <strong>{payload["turn_count_and_cost_summary"]["turn_count"]}</strong>. Estimated cost: <strong>$0.00</strong>.</p>
  </div></header>
  <section>
    <h2>1. Original User Goal</h2>
    <p>{html.escape(payload["original_user_goal"])}</p>
  </section>
  <section>
    <h2>2. Planner DAG</h2>
    <pre>{html.escape(json.dumps(payload["planner_dag"], indent=2))}</pre>
  </section>
  <section>
    <h2>3. Browser Path Chosen</h2>
    <p>{html.escape(payload["browser_path_chosen"])} (local deterministic Playwright UI actions, not passive search snippets)</p>
  </section>
  <section>
    <h2>4. Browser Actions Taken</h2>
    {_html_table(action_rows, ["turn", "type", "description", "outcome"])}
  </section>
  <section>
    <h2>5. Screenshots Or Page-State Logs</h2>
    <div class="grid">{img_blocks}</div>
    <h3>Page State Logs</h3>
    <pre>{html.escape(json.dumps(page_logs, indent=2))}</pre>
  </section>
  <section>
    <h2>6. Extracted Data</h2>
    <pre>{html.escape(json.dumps(payload["extracted_data"], indent=2))}</pre>
  </section>
  <section>
    <h2>7. Final Comparison Table</h2>
    {_html_table(table_rows, ["product", "category", "price_usd", "rating", "stock", "detail_checked", "detail_specs"])}
  </section>
  <section>
    <h2>8. Turn Count And Cost Summary</h2>
    <pre>{html.escape(json.dumps(payload["turn_count_and_cost_summary"], indent=2))}</pre>
  </section>
</body>
</html>
"""


def _html_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(c, '')))}</td>" for c in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
