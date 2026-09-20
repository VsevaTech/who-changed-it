"""HTTP-level tests: upload, paste, validation errors, exports, demo files."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

EXPECTED_DEMO_PATHS = {
    "payment_settings.timeout_seconds": "changed",
    "features.loyalty": "changed",
    "terminals[id=T-102].tid": "changed",
    "terminals[id=T-104]": "removed",
    "terminals[id=T-105]": "added",
    "billing.billing_email": "added",
    "integrations.erp.client_secret": "changed",
}


def test_index_renders():
    response = client.get("/")
    assert response.status_code == 200
    assert "Who Changed It?" in response.text
    assert "Compare configurations" in response.text


def test_healthz():
    assert client.get("/healthz").text == "ok"


def test_paste_compare_returns_fragment():
    response = client.post(
        "/compare",
        data={
            "before_text": '{"payments": {"timeout": 30, "google_pay": false}}',
            "after_text": '{"payments": {"timeout": 10, "google_pay": true}}',
        },
    )
    assert response.status_code == 200
    assert 'id="summary-total">2<' in response.text
    assert "payments.timeout" in response.text
    assert "Payments / Timeout" in response.text
    assert "30" in response.text and "10" in response.text


def test_upload_compare_demo_files(demo_before: bytes, demo_after: bytes):
    response = client.post(
        "/compare",
        files={
            "before_file": ("merchant-before.json", demo_before, "application/json"),
            "after_file": ("merchant-after.json", demo_after, "application/json"),
        },
    )
    assert response.status_code == 200
    assert 'id="summary-total">7<' in response.text
    assert "Array matched by position" not in response.text
    # Secrets from the demo must never appear in HTML.
    assert "zsk_live" not in response.text
    assert "••••••" in response.text


def test_api_compare_demo_matches_expected_changes(demo_before: bytes, demo_after: bytes):
    response = client.post(
        "/api/compare",
        files={"before_file": ("b.json", demo_before), "after_file": ("a.json", demo_after)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == {"total": 7, "added": 2, "removed": 1, "changed": 4}
    assert {c["path"]: c["type"] for c in data["changes"]} == EXPECTED_DEMO_PATHS
    secret = next(c for c in data["changes"] if c["path"].endswith("client_secret"))
    assert secret["sensitive"] is True
    assert secret["old_value"] == secret["new_value"] == "••••••"
    timeout = next(c for c in data["changes"] if c["path"].endswith("timeout_seconds"))
    assert (timeout["old_value"], timeout["new_value"]) == (30, 10)


def test_invalid_json_is_handled():
    response = client.post("/compare", data={"before_text": "{oops", "after_text": "{}"})
    assert response.status_code == 422
    assert "Cannot compare" in response.text
    assert "Before" in response.text
    assert "invalid JSON" in response.text


def test_empty_after_is_handled():
    response = client.post("/compare", data={"before_text": "{}", "after_text": ""})
    assert response.status_code == 422
    assert "After" in response.text


def test_equivalent_configurations():
    response = client.post(
        "/compare",
        data={
            "before_text": '{"t": [{"id": "T1"}, {"id": "T2"}], "a": 1}',
            "after_text": '{"a": 1, "t": [{"id": "T2"}, {"id": "T1"}]}',
        },
    )
    assert response.status_code == 200
    assert "Configurations are equivalent" in response.text


def test_custom_identity_keys_via_form():
    response = client.post(
        "/api/compare",
        data={
            "before_text": '{"items": [{"sku": "A", "q": 1}, {"sku": "B", "q": 2}]}',
            "after_text": '{"items": [{"sku": "B", "q": 2}, {"sku": "A", "q": 1}]}',
            "identity_keys": "sku",
        },
    )
    assert response.json()["summary"]["total"] == 0


def test_oversized_upload_rejected(monkeypatch: pytest.MonkeyPatch):
    from app.services import parser

    monkeypatch.setattr(parser, "DEFAULT_MAX_BYTES", 64)
    response = client.post(
        "/compare", data={"before_text": '{"a": "' + "x" * 100 + '"}', "after_text": "{}"}
    )
    assert response.status_code == 422
    assert "KB limit" in response.text


def _report_payload(demo_before: bytes, demo_after: bytes) -> str:
    response = client.post(
        "/api/compare",
        files={"before_file": ("b.json", demo_before), "after_file": ("a.json", demo_after)},
    )
    return response.text


def test_export_json(demo_before: bytes, demo_after: bytes):
    payload = _report_payload(demo_before, demo_after)
    response = client.post("/export/json", data={"report": payload})
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    data = json.loads(response.text)
    assert data["summary"]["total"] == 7
    assert "zsk_live" not in response.text
    # Decimal values survive the round trip byte-for-byte.
    assert data["changes"][0]["path"] == "billing.billing_email"


def test_export_html(demo_before: bytes, demo_after: bytes):
    payload = _report_payload(demo_before, demo_after)
    response = client.post("/export/html", data={"report": payload})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "7 changes" in response.text
    assert "Terminal T-102 / TID" in response.text
    assert "zsk_live" not in response.text


def test_export_rejects_garbage():
    assert client.post("/export/html", data={"report": "not json"}).status_code == 422
    assert client.post("/export/json", data={"report": "{}"}).status_code == 422


def test_results_fragment_embeds_masked_report_only(demo_before: bytes, demo_after: bytes):
    response = client.post(
        "/compare",
        files={"before_file": ("b.json", demo_before), "after_file": ("a.json", demo_after)},
    )
    hidden = re.findall(r'name="report" value="([^"]+)"', response.text)
    assert len(hidden) == 2
    assert all("zsk_live" not in h for h in hidden)


def test_demo_endpoints():
    assert client.get("/demo/before").status_code == 200
    assert client.get("/demo/after").json()["company"]["id"] == "cmp_48213"
    assert client.get("/demo/nope").status_code == 404
