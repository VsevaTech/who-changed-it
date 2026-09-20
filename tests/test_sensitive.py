"""Sensitive values must never leave the engine in clear text."""

from __future__ import annotations

from app import settings
from app.models.diff import ChangeType
from app.services.report import render_html_report, render_json_report
from app.services.sensitive import SensitiveDetector
from tests.conftest import diff

SECRET_OLD = "gwsecret_OLD_SECRET_VALUE_123"
SECRET_NEW = "gwsecret_NEW_SECRET_VALUE_456"


def test_sensitive_field_changed_is_masked():
    r = diff({"gateway": {"client_secret": SECRET_OLD}}, {"gateway": {"client_secret": SECRET_NEW}})
    assert r.summary.changed == 1
    c = r.changes[0]
    assert c.sensitive is True
    assert c.old_value == settings.MASK
    assert c.new_value == settings.MASK
    assert c.path == "gateway.client_secret"


def test_sensitive_field_added_is_masked():
    r = diff({}, {"api_key": SECRET_NEW})
    c = r.changes[0]
    assert c.type is ChangeType.ADDED
    assert c.sensitive and c.new_value == settings.MASK and c.old_value is None


def test_sensitive_field_removed_is_masked():
    r = diff({"password": SECRET_OLD}, {})
    c = r.changes[0]
    assert c.type is ChangeType.REMOVED
    assert c.sensitive and c.old_value == settings.MASK and c.new_value is None


def test_sensitive_parent_key_masks_nested_values():
    r = diff({"credentials": {"user": "a", "pin": "1"}}, {"credentials": {"user": "b", "pin": "2"}})
    assert all(c.sensitive for c in r.changes)
    assert all(c.old_value == settings.MASK for c in r.changes)


def test_sensitive_object_added_as_whole_is_masked():
    # A key on the list masks the whole subtree.
    r2 = diff({}, {"secrets": {"a": SECRET_NEW}})
    assert r2.changes[0].sensitive and r2.changes[0].new_value == settings.MASK


def test_secret_nested_inside_added_object_is_masked():
    # The change is reported at `oauth`, but the token inside must still be masked.
    r = diff({}, {"oauth": {"refresh_token": SECRET_NEW, "expires": 10}})
    c = r.changes[0]
    assert c.path == "oauth"
    assert c.sensitive is True
    assert c.new_value == {"refresh_token": settings.MASK, "expires": 10}
    assert SECRET_NEW not in r.model_dump_json()


def test_secret_nested_inside_removed_array_element_is_masked():
    before = {"terminals": [{"id": "T1", "api_key": SECRET_OLD, "tid": "1"}]}
    r = diff(before, {"terminals": []})
    c = r.changes[0]
    assert c.type is ChangeType.REMOVED
    assert c.old_value == {"id": "T1", "api_key": settings.MASK, "tid": "1"}
    assert SECRET_OLD not in r.model_dump_json()


def test_key_normalization_catches_camel_case_and_dashes():
    d = SensitiveDetector()
    assert d.is_sensitive_key("clientSecret")
    assert d.is_sensitive_key("CLIENT-SECRET")
    assert d.is_sensitive_key("Authorization")
    assert d.is_sensitive_key("privateKey")
    assert not d.is_sensitive_key("timeout")
    assert not d.is_sensitive_key("email")


def test_secrets_do_not_leak_into_exports():
    r = diff(
        {"gateway": {"client_secret": SECRET_OLD}, "t": 1},
        {"gateway": {"client_secret": SECRET_NEW}, "t": 2},
    )
    html = render_html_report(r)
    js = render_json_report(r)
    for text in (html, js):
        assert SECRET_OLD not in text
        assert SECRET_NEW not in text
        assert settings.MASK in text
    assert "gateway.client_secret" in js


def test_secrets_do_not_leak_via_repr():
    r = diff({"token": SECRET_OLD}, {"token": SECRET_NEW})
    assert SECRET_OLD not in repr(r)
    assert SECRET_OLD not in r.model_dump_json()
