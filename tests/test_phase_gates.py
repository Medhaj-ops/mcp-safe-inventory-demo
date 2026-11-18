"""
Proves the phase gate is real code, not documentation. Each test calls
the actual tool functions from server.py — nothing here is mocked.
"""

import server
from tests.conftest import submit


def test_submit_without_draft_is_blocked():
    result = submit(draft_po_id="draft-never-existed", session_id="gate-test-1"
    )
    assert "error" in result
    assert "GATE_BLOCKED" in result["error"]
    assert "draft_purchase_order first" in result["error"]


def test_happy_path_draft_then_submit_succeeds():
    draft = server.draft_purchase_order(
        sku="SKU-003", quantity=100, justification="restocking", session_id="gate-test-4"
    )
    assert draft["draft_po_id"] is not None

    result = submit(draft_po_id=draft["draft_po_id"], session_id="gate-test-4"
    )
    assert "po_id" in result
    assert result["after_state"]["stock"] == result["before_state"]["stock"] + 100


def test_draft_from_one_session_cannot_be_submitted_from_another():
    """Session isolation: a draft_id leaking across sessions must not be exploitable."""
    draft = server.draft_purchase_order(
        sku="SKU-001", quantity=10, justification="test", session_id="gate-test-owner"
    )
    result = submit(draft_po_id=draft["draft_po_id"], session_id="gate-test-intruder"
    )
    assert "error" in result
    assert "GATE_BLOCKED" in result["error"]


def test_draft_cannot_be_submitted_twice():
    draft = server.draft_purchase_order(
        sku="SKU-002", quantity=25, justification="test", session_id="gate-test-5"
    )
    first = submit(draft_po_id=draft["draft_po_id"], session_id="gate-test-5"
    )
    assert "po_id" in first

    second = submit(draft_po_id=draft["draft_po_id"], session_id="gate-test-5"
    )
    assert "error" in second
    assert "already been submitted" in second["error"]
