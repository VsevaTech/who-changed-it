"""FastAPI entrypoint. Routes only translate HTTP <-> services; no diff logic lives here.

Privacy: request bodies are processed in memory and dropped when the response is sent.
Nothing is persisted, and the access log never contains payloads.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import __version__, settings
from app.services.compare import CompareError, compare_documents
from app.services.report import get_environment, render_html_report, render_json_report

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Who Changed It?", version=__version__, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
EXAMPLES_DIR = BASE_DIR.parent / "examples"
if EXAMPLES_DIR.is_dir():
    app.mount("/examples", StaticFiles(directory=str(EXAMPLES_DIR)), name="examples")

templates = Jinja2Templates(env=get_environment())

# Silence body-level logging entirely; uvicorn's access log only records method/path/status.
logging.getLogger("who_changed_it").setLevel(logging.WARNING)


async def _read_side(text: str | None, upload: UploadFile | None) -> bytes:
    """Prefer an uploaded file, fall back to pasted text. Enforce the size limit early."""
    if upload is not None and upload.filename:
        data = await upload.read(settings.MAX_JSON_BYTES + 1)
        await upload.close()
        return data
    return (text or "").encode("utf-8")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"version": __version__, "max_mb": settings.MAX_JSON_BYTES // (1024 * 1024)},
    )


@app.post("/compare", response_class=HTMLResponse)
async def compare(
    request: Request,
    before_text: Annotated[str | None, Form()] = None,
    after_text: Annotated[str | None, Form()] = None,
    before_file: Annotated[UploadFile | None, File()] = None,
    after_file: Annotated[UploadFile | None, File()] = None,
) -> HTMLResponse:
    before = await _read_side(before_text, before_file)
    after = await _read_side(after_text, after_file)
    try:
        result = compare_documents(before, after)
    except CompareError as exc:
        return templates.TemplateResponse(
            request,
            "partials/error.html",
            {"side": exc.side, "message": exc.message},
            status_code=422,
        )
    return templates.TemplateResponse(request, "partials/result.html", {"result": result})


@app.post("/export/json")
async def export_json(
    before_text: Annotated[str | None, Form()] = None,
    after_text: Annotated[str | None, Form()] = None,
    before_file: Annotated[UploadFile | None, File()] = None,
    after_file: Annotated[UploadFile | None, File()] = None,
) -> Response:
    before = await _read_side(before_text, before_file)
    after = await _read_side(after_text, after_file)
    try:
        result = compare_documents(before, after)
    except CompareError as exc:
        return PlainTextResponse(exc.message, status_code=422)
    return Response(
        content=render_json_report(result),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="change-report.json"'},
    )


@app.post("/export/html")
async def export_html(
    before_text: Annotated[str | None, Form()] = None,
    after_text: Annotated[str | None, Form()] = None,
    before_file: Annotated[UploadFile | None, File()] = None,
    after_file: Annotated[UploadFile | None, File()] = None,
) -> Response:
    before = await _read_side(before_text, before_file)
    after = await _read_side(after_text, after_file)
    try:
        result = compare_documents(before, after)
    except CompareError as exc:
        return PlainTextResponse(exc.message, status_code=422)
    return Response(
        content=render_html_report(result),
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="change-report.html"'},
    )


@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    return "ok"
