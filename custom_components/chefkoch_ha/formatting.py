"""Render recipe lists for notifications (Telegram, mobile app, e-mail, ...).

The recipe title itself is the link and every recipe sits on its own line.
"""

from __future__ import annotations

import html
from typing import Any

from .filters import recipe_minutes

KEYCAPS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
NUMBERING_STYLES = ["emoji", "number", "bullet", "none"]
DETAIL_FIELDS = ["category", "time", "rating", "calories", "difficulty", "provider"]


def _marker(index: int, style: str) -> str:
    if style == "emoji":
        return KEYCAPS[index] if index < len(KEYCAPS) else f"{index + 1}."
    if style == "number":
        return f"{index + 1}."
    if style == "bullet":
        return "•"
    return ""


def _format_minutes(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} Std {mins} Min"
    return f"{hours} Std" if hours else f"{mins} Min"


def detail_parts(recipe: dict[str, Any], details: list[str]) -> list[str]:
    """Short human readable facts about a recipe, in the order of *details*."""
    parts: list[str] = []
    for key in details:
        if key == "category" and recipe.get("category"):
            parts.append(str(recipe["category"]))
        elif key == "time" and (minutes := recipe_minutes(recipe)):
            parts.append(_format_minutes(minutes))
        elif key == "rating" and recipe.get("rating"):
            parts.append(f"⭐ {float(recipe['rating']):.1f}")
        elif key == "calories" and recipe.get("calories"):
            parts.append(str(recipe["calories"]))
        elif key == "difficulty" and recipe.get("difficulty"):
            parts.append(str(recipe["difficulty"]))
        elif key == "provider" and recipe.get("provider_name"):
            parts.append(str(recipe["provider_name"]))
    return parts


def render_recipes(
    recipes: list[dict[str, Any]],
    *,
    header: str = "",
    footer: str = "",
    numbering: str = "emoji",
    details: list[str] | None = None,
) -> dict[str, str]:
    """Return ``markdown``, ``html`` and ``plain`` renderings (one recipe per line).

    ``header``/``footer`` are inserted unchanged, so write them in the target
    format (e.g. ``<b>..</b>`` for Telegram ``parse_mode: html``).
    """
    details = ["category"] if details is None else details
    md_lines: list[str] = []
    html_lines: list[str] = []
    plain_lines: list[str] = []
    for i, recipe in enumerate(recipes):
        title = str(recipe.get("title") or "?")
        url = str(recipe.get("url") or "")
        marker = _marker(i, numbering)
        prefix = f"{marker} " if marker else ""
        parts = detail_parts(recipe, details)
        suffix = f" ({' · '.join(parts)})" if parts else ""
        if url:
            safe_title = title.replace("[", "(").replace("]", ")")
            md_lines.append(f"{prefix}[{safe_title}]({url}){suffix}")
            html_lines.append(
                f'{prefix}<a href="{html.escape(url, quote=True)}">'
                f"{html.escape(title)}</a>{html.escape(suffix)}"
            )
            plain_lines.append(f"{prefix}{title}{suffix}\n   {url}")
        else:
            md_lines.append(f"{prefix}{title}{suffix}")
            html_lines.append(f"{prefix}{html.escape(title)}{html.escape(suffix)}")
            plain_lines.append(f"{prefix}{title}{suffix}")

    def assemble(lines: list[str]) -> str:
        blocks = [b for b in (header, "\n".join(lines), footer) if b]
        return "\n\n".join(blocks)

    return {
        "markdown": assemble(md_lines),
        "html": assemble(html_lines),
        "plain": assemble(plain_lines),
    }
