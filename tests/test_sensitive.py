"""Sensitive values: the fact of a change is shown, the value is not."""

from __future__ import annotations

from app.models.diff import ChangeType
from app.services.report import render_html_report, render_json_report
from app.services.sensitive import MASK, is_sensitive_key, mask_value
from tests.conftest import diff

SECRET_OLD = "zsk_live_OLD_5f8a2b7c9d1e"
SECRET_NEW = "zsk_live_NEW_9c1d3e5f7a2b"


def test_sensitive_field_changed_is_masked():
    report = diff({"erp": {"client_secret": SECRET_OLD}}, {"erp": {"client_secret": SECRET_NEW}})
    assert report.summary.changed == 1
    change = report.changes[0]
    assert change.sensitive is True
    assert change.old_value == MASK and change.new_value == MASK
    assert change.type is ChangeType.CHANGED


def test_sensitive_field_added_is_masked():
    report = diff({}, {"api_key": SECRET_NEW})
    assert report.changes[0].type is ChangeType.ADDED
    assert report.changes[0].sensitive is True
    assert report.changes[0].new_value == MASK


def test_sensitive_field_removed_is_masked():
    report = diff({"password": SECRET_OLD}, {})
    assert report.changes[0].type is ChangeType.REMOVED
    assert report.changes[0].sensitive is True
    assert report.changes[0].old_value == MASK


def test_sensitive_parent_path_masks_children():
    report = diff(
        {"credentials": {"user": "u", "pass": "a"}}, {"credentials": {"user": "u", "pass": "b"}}
    )
    assert report.changes[0].path == "credentials.pass"
    assert report.changes[0].old_value == MASK


def test_added_object_containing_secret_masks_only_that_field():
    report = diff({}, {"erp": {"provider": "zoho", "client_secret": SECRET_NEW}})
    change = report.changes[0]
    assert change.sensitive is True
    assert change.new_value == {"provider": "zoho", "client_secret": MASK}


def test_secrets_never_reach_exports():
    before = {"integrations": {"erp": {"client_secret": SECRET_OLD, "access_token": "tokOLD"}}}
    after = {"integrations": {"erp": {"client_secret": SECRET_NEW, "access_token": "tokNEW"}}}
    report = diff(before, after)
    for rendered in (render_json_report(report), render_html_report(report)):
        for secret in (SECRET_OLD, SECRET_NEW, "tokOLD", "tokNEW"):
            assert secret not in rendered
        assert MASK in rendered


def test_key_detection_rules():
    assert is_sensitive_key("client_secret")
    assert is_sensitive_key("clientSecret")
    assert is_sensitive_key("ACCESS_TOKEN")
    assert is_sensitive_key("api-key")
    assert is_sensitive_key("private_key")
    assert is_sensitive_key("Authorization")
    assert is_sensitive_key("db_password")
    # Identity-ish keys and near-misses must stay visible.
    assert not is_sensitive_key("key")
    assert not is_sensitive_key("id")
    assert not is_sensitive_key("tokenization_enabled")
    assert not is_sensitive_key("pin_on_glass")
    assert not is_sensitive_key("secretary")


def test_mask_value_recurses_into_lists():
    value = [{"id": 1, "token": "abc"}, {"id": 2, "name": "ok"}]
    assert mask_value(value) == [{"id": 1, "token": MASK}, {"id": 2, "name": "ok"}]
