"""End-to-end demo against a running instance: upload, filters, exports, paste, errors.

Usage:
    python scripts/demo.py [--base http://localhost:8000] [--out docs]

Requires ``pip install playwright && playwright install chromium``. Prints a JSON summary of
what was verified and writes screenshots to ``--out``. Exit code 1 if any check fails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"

PASTE_BEFORE = (
    '{"payments": {"timeout": 30, "google_pay": false}, "t": [{"id": "T1"}, {"id": "T2"}]}'
)
PASTE_AFTER = '{"t": [{"id": "T2"}, {"id": "T1"}], "payments": {"google_pay": true, "timeout": 10}}'
PASTE_SAME = '{"t": [{"id": "T2"}, {"id": "T1"}], "payments": {"google_pay": false, "timeout": 30}}'


async def run(base: str, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    results: dict = {}
    tmp = Path(tempfile.mkdtemp())

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 900})

        # 1. Upload flow with the bundled demo files.
        await page.goto(base)
        await page.click('.tab[data-mode="upload"]')
        await page.set_input_files("#before_file", str(EXAMPLES / "merchant-before.json"))
        await page.set_input_files("#after_file", str(EXAMPLES / "merchant-after.json"))
        await page.screenshot(path=str(out / "01-upload.png"))
        await page.click("#compare-btn")
        await page.wait_for_selector("#summary-total")
        results["upload_total"] = await page.inner_text("#summary-total")
        results["masked_rows"] = await page.locator(".change.sensitive").count()
        results["positional_notes"] = await page.locator(".pill.note").count()
        results["secret_leak_in_dom"] = "zsk_live" in await page.content()
        await page.screenshot(path=str(out / "02-results.png"), full_page=True)

        # 2. Filters and search.
        counts = {}
        for kind in ("removed", "added", "changed"):
            await page.click(f'.filter[data-filter="{kind}"]')
            counts[kind] = await page.locator(".change:not(.hidden)").count()
        results["filter_counts"] = counts
        await page.click('.filter[data-filter="all"]')
        await page.fill("#search", "terminal")
        results["search_terminal_visible"] = await page.locator(".change:not(.hidden)").count()
        await page.screenshot(path=str(out / "03-filter-terminal.png"))
        await page.fill("#search", "")

        # 3. Exports (downloads).
        async with page.expect_download() as dl:
            await page.click('form[action="/export/html"] button')
        html_path = tmp / (await dl.value).suggested_filename
        await (await dl.value).save_as(str(html_path))
        html = html_path.read_text("utf-8")
        results["html_export"] = {"has_7": "7 changes" in html, "leak": "zsk_live" in html}

        async with page.expect_download() as dl:
            await page.click('form[action="/export/json"] button')
        json_path = tmp / (await dl.value).suggested_filename
        await (await dl.value).save_as(str(json_path))
        raw = json_path.read_text("utf-8")
        results["json_export"] = {"summary": json.loads(raw)["summary"], "leak": "zsk_live" in raw}

        # 4. Paste flow: real changes + reordered array (no noise).
        await page.goto(base)
        await page.fill("#before_text", PASTE_BEFORE)
        await page.fill("#after_text", PASTE_AFTER)
        await page.click("#compare-btn")
        await page.wait_for_selector("#summary-total")
        results["paste_total"] = await page.inner_text("#summary-total")
        await page.screenshot(path=str(out / "04-paste.png"), full_page=True)

        # 5. Invalid JSON.
        await page.fill("#after_text", '{"oops": }')
        await page.click("#compare-btn")
        await page.wait_for_selector(".panel.error")
        results["invalid_json_message"] = await page.inner_text(".panel.error p")
        await page.screenshot(path=str(out / "05-invalid.png"))

        # 6. Equivalent configurations.
        await page.fill("#after_text", PASTE_SAME)
        await page.click("#compare-btn")
        await page.wait_for_selector(".equivalent")
        results["equivalent_shown"] = True
        await page.screenshot(path=str(out / "06-equivalent.png"))
        await browser.close()

    results["ok"] = (
        results["upload_total"] == "7"
        and results["masked_rows"] == 1
        and results["positional_notes"] == 0
        and results["secret_leak_in_dom"] is False
        and results["filter_counts"] == {"removed": 1, "added": 2, "changed": 4}
        and results["search_terminal_visible"] == 3
        and results["html_export"] == {"has_7": True, "leak": False}
        and results["json_export"]["leak"] is False
        and results["json_export"]["summary"]["total"] == 7
        and results["paste_total"] == "2"
        and "invalid JSON" in results["invalid_json_message"]
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--out", default=str(ROOT / "docs"))
    args = parser.parse_args()
    results = asyncio.run(run(args.base, Path(args.out)))
    print(json.dumps(results, indent=2))
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
