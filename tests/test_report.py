from __future__ import annotations

import json

from app.services.compare import compare_documents
from app.services.report import build_json_report, render_html_report, render_json_report
from tests.conftest import diff


def test_json_report_shape():
    r = diff({"a": 1, "b": {"c": 1}}, {"a": 2, "b": {"d": 1}})
    report = build_json_report(r)
    assert report["summary"] == {"total": 3, "added": 1, "removed": 1, "changed": 1}
    change = report["changes"][0]
    assert set(change) >= {
        "type",
        "path",
        "display_path",
        "old_value",
        "new_value",
        "identity",
        "sensitive",
    }


def test_json_report_is_valid_json_and_keeps_decimals():
    r = compare_documents('{"amount": 12.30}', '{"amount": 12.40}')
    text = render_json_report(r)
    data = json.loads(text)
    assert data["changes"][0]["old_value"] == 12.3
    assert '"old_value": 12.30' in text  # exact textual Decimal, not float


def test_json_report_identity():
    r = diff({"t": [{"id": "T1", "v": 1}]}, {"t": [{"id": "T1", "v": 2}]})
    data = build_json_report(r)
    assert data["changes"][0]["identity"] == {"key": "id", "value": "T1"}
    assert data["changes"][0]["path"] == "t[id=T1].v"


def test_html_report_is_standalone_and_escaped():
    r = diff({"<b>": "<script>alert(1)</script>"}, {"<b>": "safe"})
    html = render_html_report(r)
    assert html.startswith("<!doctype html>")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "1</span> change" in html


def test_html_report_equivalent():
    html = render_html_report(diff({"a": 1}, {"a": 1}))
    assert "Configurations are equivalent" in html


def test_example_files_give_seven_known_changes(example_pair):
    before, after = example_pair
    r = compare_documents(before, after)
    assert r.summary.total == 7
    assert (r.summary.changed, r.summary.added, r.summary.removed) == (4, 2, 1)
    by_path = {c.path: c for c in r.changes}
    assert by_path["payment_settings.timeout"].old_value == 30
    assert by_path["payment_settings.timeout"].new_value == 10
    assert by_path["payment_settings.wallets.google_pay"].new_value is True
    assert by_path["terminals[id=T-102].tid"].new_value == "887245"
    assert by_path["terminals[id=T-104]"].type.value == "removed"
    assert by_path["terminals[id=T-105]"].type.value == "added"
    assert by_path["billing.contact.email"].new_value == "billing@alnoor.example"
    secret = by_path["payment_settings.gateway.client_secret"]
    assert secret.sensitive and secret.old_value == secret.new_value == "••••••"
    assert r.positional_arrays == []
    assert [g for g, _ in r.groups] == ["Payments", "Terminals", "Billing"]
