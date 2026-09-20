"""Rendering of a :class:`DiffReport` as JSON and standalone HTML."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.diff import DiffReport
from app.services.sensitive import MASK

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "j2"]),
)

GROUP_ORDER = ["Company", "Payments", "Terminals", "Features", "Billing", "Locations"]


def dump_json(value: Any, indent: int | None = None) -> str:
    """JSON serializer that emits ``Decimal`` as a plain JSON number (never via ``float``).

    Key order is preserved as given; callers pass already-ordered data.
    """
    return _dump(value, indent, 0)


def _dump(value: Any, indent: int | None, level: int) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [
            f"{json.dumps(str(k), ensure_ascii=False)}:{' ' if indent else ''}"
            f"{_dump(v, indent, level + 1)}"
            for k, v in value.items()
        ]
        return _wrap("{", "}", items, indent, level)
    if isinstance(value, list):
        if not value:
            return "[]"
        return _wrap("[", "]", [_dump(v, indent, level + 1) for v in value], indent, level)
    return json.dumps(str(value), ensure_ascii=False)


def _wrap(open_: str, close: str, items: list[str], indent: int | None, level: int) -> str:
    if indent is None:
        return open_ + ",".join(items) + close
    pad_in = " " * (indent * (level + 1))
    pad_out = " " * (indent * level)
    return open_ + "\n" + ",\n".join(pad_in + i for i in items) + "\n" + pad_out + close


def format_value(value: Any) -> str:
    """Short human-facing rendering. Strings keep quotes so ``"30"`` and ``30`` differ."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, str):
        return MASK if value == MASK else json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return dump_json(value, indent=2)
    if isinstance(value, list):
        return dump_json(value, indent=2)
    return str(value)


def is_block(value: Any) -> bool:
    return isinstance(value, dict | list)


def group_changes(report: DiffReport) -> list[tuple[str, list]]:
    groups: dict[str, list] = {}
    for change in report.changes:
        groups.setdefault(change.group, []).append(change)

    def order(name: str) -> tuple[int, str]:
        if name in GROUP_ORDER:
            return (GROUP_ORDER.index(name), name)
        if name == "Other":
            return (len(GROUP_ORDER) + 1, name)
        return (len(GROUP_ORDER), name)

    return sorted(groups.items(), key=lambda kv: order(kv[0]))


def report_to_dict(report: DiffReport) -> dict[str, Any]:
    return {
        "tool": "who-changed-it",
        "version": 1,
        "summary": report.summary.model_dump(),
        "notes": list(report.notes),
        "changes": [
            {
                "type": c.type.value,
                "path": c.path,
                "display_path": c.display_path,
                "group": c.group,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "identity": c.identity,
                "sensitive": c.sensitive,
                "note": c.note,
            }
            for c in report.changes
        ],
    }


def render_json_report(report: DiffReport) -> str:
    return dump_json(report_to_dict(report), indent=2) + "\n"


def render_html_report(report: DiffReport, *, title: str = "Configuration change report") -> str:
    template = _env.get_template("report.html")
    return template.render(
        report=report,
        groups=group_changes(report),
        title=title,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        format_value=format_value,
        is_block=is_block,
    )


def render_results_fragment(report: DiffReport) -> str:
    """The in-page results panel (same data, interactive filters)."""
    template = _env.get_template("_results.html")
    return template.render(
        report=report,
        groups=group_changes(report),
        report_json=render_json_report(report),
        format_value=format_value,
        is_block=is_block,
    )
