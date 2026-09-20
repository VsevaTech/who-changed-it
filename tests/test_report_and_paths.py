from __future__ import annotations

import json
from decimal import Decimal

from app.services.paths import Segment as Seg
from app.services.paths import display_path, humanize_key, singularize
from app.services.report import dump_json, format_value, render_html_report, render_json_report
from tests.conftest import diff, loads


def test_humanize_key():
    assert humanize_key("payment_settings") == "Payment settings"
    assert humanize_key("terminal_id") == "Terminal ID"
    assert humanize_key("tid") == "TID"
    assert humanize_key("webhookUrl") == "Webhook URL"


def test_singularize():
    assert singularize("terminals") == "terminal"
    assert singularize("policies") == "policy"
    assert singularize("address") == "address"
    assert singularize("status") == "status"


def test_display_path_examples_from_spec():
    assert display_path([Seg(key="company"), Seg(key="payment_settings"), Seg(key="timeout")]) == (
        "Company / Payment settings / Timeout"
    )
    assert (
        display_path([Seg(key="terminals"), Seg(identity="id=T2"), Seg(key="tid")])
        == "Terminal T2 / TID"
    )
    assert display_path([Seg(key="rules"), Seg(index=0), Seg(key="x")]) == "Rule #0 / X"


def test_format_value_keeps_types_distinguishable():
    assert format_value("30") == '"30"'
    assert format_value(30) == "30"
    assert format_value(True) == "true"
    assert format_value(None) == "null"
    assert format_value(Decimal("1.50")) == "1.50"


def test_dump_json_decimal_round_trip():
    text = dump_json({"fee": Decimal("1.50"), "n": 3, "s": "x", "l": [Decimal("0.1")], "b": False})
    assert text == '{"fee":1.50,"n":3,"s":"x","l":[0.1],"b":false}'
    assert json.loads(text, parse_float=Decimal)["fee"] == Decimal("1.50")


def test_json_report_shape():
    report = diff(
        loads('{"a": 1, "b": 2, "c": {"d": 1}}'), loads('{"a": 2, "c": {"d": 1}, "e": 3}')
    )
    data = json.loads(render_json_report(report))
    assert data["summary"] == {"total": 3, "added": 1, "removed": 1, "changed": 1}
    change = data["changes"][0]
    assert set(change) == {
        "type",
        "path",
        "display_path",
        "group",
        "old_value",
        "new_value",
        "identity",
        "sensitive",
        "note",
    }


def test_html_report_escapes_values():
    report = diff({"name": "<script>alert(1)</script>"}, {"name": "safe"})
    html = render_html_report(report)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "3 changes" not in html and "1 change" in html


def test_html_report_equivalent_state():
    html = render_html_report(diff({"a": 1}, {"a": 1}))
    assert "Configurations are equivalent" in html
