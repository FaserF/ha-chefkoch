"""Tests for notification formatting."""

from custom_components.chefkoch_ha.formatting import render_recipes

from . import mock_ha  # noqa: F401

RECIPES = [
    {
        "title": "Gemüsecremesuppe",
        "url": "https://www.chefkoch.de/rezepte/1/Suppe.html",
        "category": "Wärmend & Deftig",
        "totalTime": "0:45:00",
        "rating": 4.6,
    },
    {"title": "Kürbis [scharf]", "url": "https://www.chefkoch.de/rezepte/2/"},
]


def test_title_is_link_and_one_recipe_per_line():
    out = render_recipes(RECIPES, header="Heute?", footer="/food für mehr")
    md_lines = out["markdown"].split("\n")
    assert md_lines[0] == "Heute?"
    assert md_lines[2] == (
        "1️⃣ [Gemüsecremesuppe](https://www.chefkoch.de/rezepte/1/Suppe.html)"
        " (Wärmend & Deftig)"
    )
    assert md_lines[3].startswith(
        "2️⃣ [Kürbis (scharf)](https://www.chefkoch.de/rezepte/2/)"
    )
    assert md_lines[-1] == "/food für mehr"

    html_lines = out["html"].split("\n")
    assert html_lines[2] == (
        '1️⃣ <a href="https://www.chefkoch.de/rezepte/1/Suppe.html">Gemüsecremesuppe</a>'
        " (Wärmend &amp; Deftig)"
    )


def test_details_numbering_and_plain():
    out = render_recipes(
        RECIPES[:1], numbering="bullet", details=["time", "rating", "category"]
    )
    assert out["markdown"].startswith("• [Gemüsecremesuppe](")
    assert "(45 Min · ⭐ 4.6 · Wärmend & Deftig)" in out["markdown"]
    assert (
        out["plain"].split("\n")[1].strip()
        == "https://www.chefkoch.de/rezepte/1/Suppe.html"
    )
