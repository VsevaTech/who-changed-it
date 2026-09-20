"""Report export: JSON and standalone HTML."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import __version__
from app.models.diff import DiffResult
from app.services.values import render_value, to_json_text

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["render_value"] = render_value
_env.filters["json_text"] = lambda v: to_json_text(v, indent=2)


def get_environment() -> Environment:
    return _env


def build_json_report(result: DiffResult) -> dict[str, Any]:
    """Plain dict ready for serialization. Sensitive values are already masked."""
    return {
        "tool": "who-changed-it",
        "version": __version__,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "summary": result.summary.model_dump(),
        "positional_arrays": list(result.positional_arrays),
        "changes": [
            {
                "type": c.type.value,
                "path": c.path,
                "display_path": c.display_path,
                "group": c.group,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "identity": c.identity.model_dump() if c.identity else None,
                "sensitive": c.sensitive,
                "match_mode": c.match_mode.value if c.match_mode else None,
                "note": c.note,
            }
            for c in result.changes
        ],
    }


def render_json_report(result: DiffResult) -> str:
    return to_json_text(build_json_report(result), indent=2) + "\n"


def render_html_report(result: DiffResult, *, title: str = "Configuration change report") -> str:
    template = _env.get_template("report.html")
    return template.render(
        result=result,
        title=title,
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        version=__version__,
    )
