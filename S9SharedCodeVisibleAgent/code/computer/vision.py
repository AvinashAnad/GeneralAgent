"""Vision helpers for opaque desktop surfaces."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


VISION_ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["thinking", "x", "y"],
    "properties": {
        "thinking": {"type": "string"},
        "action": {"type": "string", "enum": ["click", "double_click"]},
        "x": {"type": "integer"},
        "y": {"type": "integer"},
    },
}


def draw_numbered_grid(image_path: str | Path, out_path: str | Path,
                       *, cols: int = 4, rows: int = 3) -> list[dict[str, int]]:
    image_path = Path(image_path)
    out_path = Path(out_path)
    im = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(im)
    width, height = im.size
    marks: list[dict[str, int]] = []
    font = ImageFont.load_default()
    idx = 1
    for r in range(rows):
        for c in range(cols):
            x0 = int(c * width / cols)
            y0 = int(r * height / rows)
            x1 = int((c + 1) * width / cols)
            y1 = int((r + 1) * height / rows)
            cx = (x0 + x1) // 2
            cy = (y0 + y1) // 2
            draw.rectangle([x0, y0, x1, y1], outline=(255, 80, 20), width=3)
            draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=(255, 80, 20))
            draw.text((cx - 4, cy - 5), str(idx), fill=(255, 255, 255), font=font)
            marks.append({"mark": idx, "x": cx, "y": cy})
            idx += 1
    im.save(out_path)
    return marks


def _data_url(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


async def choose_vision_action(client, *, image_path: str | Path, goal: str,
                               marks: list[dict[str, int]],
                               provider: str | None = None,
                               model: str | None = None) -> dict[str, Any]:
    prompt = (
        "You are controlling a desktop app from a screenshot with numbered "
        "regions. Choose the x/y coordinate to click for the user's goal. "
        "Prefer the exact visible target center when possible.\n\n"
        f"GOAL: {goal}\n\nMARKS:\n{marks}"
    )
    result = await client.vision(
        _data_url(image_path),
        prompt,
        schema=VISION_ACTION_SCHEMA,
        schema_name="ComputerVisionAction",
        max_tokens=500,
        provider=provider,
        model=model,
    )
    parsed = getattr(result, "parsed", None) or {}
    if "x" not in parsed or "y" not in parsed:
        raise RuntimeError("vision action did not include x/y")
    parsed.setdefault("action", "click")
    return parsed
