"""HTTP-level tests for the FastAPI app."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_index_renders(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Who Changed It?" in res.text
    assert "Compare configurations" in res.text


def test_health(client):
    assert client.get("/health").text == "ok"


def test_compare_paste(client):
    res = client.post(
        "/compare",
        data={
            "before_text": '{"payments": {"timeout": 30}}',
            "after_text": '{"payments": {"timeout": 10}}',
        },
    )
    assert res.status_code == 200
    assert "1</span> change" in res.text
    assert "payments.timeout" in res.text
    assert "Payments / Timeout" in res.text
    assert "30" in res.text and "10" in res.text


def test_compare_upload(client, example_pair):
    before, after = example_pair
    res = client.post(
        "/compare",
        files={
            "before_file": ("before.json", before, "application/json"),
            "after_file": ("after.json", after, "application/json"),
        },
    )
    assert res.status_code == 200
    assert "7</span> change" in res.text
    assert "Terminal T-102 / TID" in res.text
    assert "sk_live_" not in res.text  # secrets never reach HTML
    assert "••••••" in res.text


def test_compare_upload_takes_precedence_over_empty_text(client):
    res = client.post(
        "/compare",
        data={"before_text": "", "after_text": ""},
        files={
            "before_file": ("b.json", b'{"a": 1}', "application/json"),
            "after_file": ("a.json", b'{"a": 2}', "application/json"),
        },
    )
    assert res.status_code == 200
    assert "1</span> change" in res.text


def test_compare_invalid_json(client):
    res = client.post("/compare", data={"before_text": "{", "after_text": "{}"})
    assert res.status_code == 422
    assert "BEFORE could not be parsed" in res.text
    assert "not valid JSON" in res.text


def test_compare_equivalent(client):
    res = client.post(
        "/compare", data={"before_text": '{"a":[1,2]}', "after_text": '{ "a": [1, 2] }'}
    )
    assert "Configurations are equivalent" in res.text


def test_export_json(client, example_pair):
    before, after = example_pair
    res = client.post(
        "/export/json",
        files={"before_file": ("b.json", before), "after_file": ("a.json", after)},
    )
    assert res.status_code == 200
    assert res.headers["content-disposition"].endswith('filename="change-report.json"')
    data = json.loads(res.text)
    assert data["summary"]["total"] == 7
    assert "sk_live_" not in res.text


def test_export_html(client, example_pair):
    before, after = example_pair
    res = client.post(
        "/export/html",
        files={"before_file": ("b.json", before), "after_file": ("a.json", after)},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert "7</span> change" in res.text
    assert "sk_live_" not in res.text


def test_export_invalid_json(client):
    res = client.post("/export/json", data={"before_text": "nope", "after_text": "{}"})
    assert res.status_code == 422


def test_examples_are_served(client):
    res = client.get("/examples/merchant-before.json")
    assert res.status_code == 200
    assert json.loads(res.text)["company"]["company_id"] == "CMP-40021"
