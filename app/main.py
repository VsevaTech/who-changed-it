"""Who Changed It? — FastAPI entry point. Routes stay thin; logic lives in ``app.services``.

Privacy: request bodies are processed in memory only. Nothing is persisted, and exception
handlers deliberately do not include request payloads in log output.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.models.diff import DiffReport
from app.services.compare import compare_texts, parse_identity_keys
from app.services.parser import DEFAULT_MAX_BYTES, JsonInputError
from app.services.report import (
    render_html_report,
    render_json_report,
    render_results_fragment,
    report_to_dict,
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(
    title="Who Changed It?",
    description="Turn noisy JSON diffs into human-readable configuration changes.",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Silence uvicorn's per-request error tracebacks that could echo request context.
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"max_kb": DEFAULT_MAX_BYTES // 1024},
    )


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz() -> str:
    return "ok"


EXAMPLES_DIR = BASE_DIR.parent / "examples"
DEMO_FILES = {"before": "merchant-before.json", "after": "merchant-after.json"}


@app.get("/demo/{side}")
async def demo(side: str) -> Response:
    """Serve the bundled demo configurations for the "Load demo" button."""
    name = DEMO_FILES.get(side)
    if name is None:
        return PlainTextResponse("Not found", status_code=404)
    return Response((EXAMPLES_DIR / name).read_text("utf-8"), media_type="application/json")


async def _read_side(text: str | None, upload: UploadFile | None) -> str | bytes:
    if upload is not None and upload.filename:
        data = await upload.read(DEFAULT_MAX_BYTES + 1)
        return data
    return text or ""


@app.post("/compare", response_class=HTMLResponse)
async def compare(
    request: Request,
    before_text: Annotated[str | None, Form()] = None,
    after_text: Annotated[str | None, Form()] = None,
    before_file: Annotated[UploadFile | None, File()] = None,
    after_file: Annotated[UploadFile | None, File()] = None,
    identity_keys: Annotated[str | None, Form()] = None,
) -> HTMLResponse:
    """Returns an HTML fragment with the results (or an error panel). Never stores inputs."""
    before = await _read_side(before_text, before_file)
    after = await _read_side(after_text, after_file)
    try:
        report = compare_texts(before, after, parse_identity_keys(identity_keys))
    except JsonInputError as exc:
        html = templates.get_template("_error.html").render(side=exc.side, message=exc.user_message)
        return HTMLResponse(html, status_code=422)
    return HTMLResponse(render_results_fragment(report))


@app.post("/api/compare")
async def api_compare(
    before_text: Annotated[str | None, Form()] = None,
    after_text: Annotated[str | None, Form()] = None,
    before_file: Annotated[UploadFile | None, File()] = None,
    after_file: Annotated[UploadFile | None, File()] = None,
    identity_keys: Annotated[str | None, Form()] = None,
) -> Response:
    """JSON variant of ``/compare`` for scripting. Sensitive values are masked."""
    before = await _read_side(before_text, before_file)
    after = await _read_side(after_text, after_file)
    try:
        report = compare_texts(before, after, parse_identity_keys(identity_keys))
    except JsonInputError as exc:
        return JSONResponse({"error": {"side": exc.side, "message": exc.user_message}}, 422)
    return Response(render_json_report(report), media_type="application/json")


def _load_report(raw: str) -> DiffReport | None:
    # Parse floats as Decimal so exported numbers are byte-identical to the report.
    try:
        data = json.loads(raw, parse_float=Decimal)
        return DiffReport.model_validate(data)
    except (ValueError, ValidationError):
        return None


@app.post("/export/html")
async def export_html(report: Annotated[str, Form()]) -> Response:
    """The browser posts back the (already masked) report JSON; we render it standalone."""
    parsed = _load_report(report)
    if parsed is None:
        return PlainTextResponse("Invalid report payload", status_code=422)
    html = render_html_report(parsed)
    return Response(
        html,
        media_type="text/html",
        headers={"Content-Disposition": 'attachment; filename="who-changed-it-report.html"'},
    )


@app.post("/export/json")
async def export_json(report: Annotated[str, Form()]) -> Response:
    parsed = _load_report(report)
    if parsed is None:
        return PlainTextResponse("Invalid report payload", status_code=422)
    body = render_json_report(parsed)
    return Response(
        body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="who-changed-it-report.json"'},
    )


__all__ = ["app", "report_to_dict"]
