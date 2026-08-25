"""
Proves the audit log captures EVERYTHING, not just successful mutations.
An audit trail that's silent about blocked attempts is missing the
events most worth reviewing later.
"""

from safety import audit
import server


def setup_function():
    audit.clear()


def test_successful_read_is_logged():
    server.read_inventory_state(sku="SKU-001", session_id="audit-test-1")
    entries = audit.entries_for_session("audit-test-1")
    assert len(entries) == 1
    assert entries[0].tool_name == "read_inventory_state"
    assert entries[0].outcome == "success"


def test_validation_failure_is_logged_with_error():
    server.draft_purchase_order(
        sku="FAKE", quantity=-1, justification="", session_id="audit-test-2"
    )
    entries = audit.entries_for_session("audit-test-2")
    assert len(entries) == 1
    assert entries[0].outcome == "validation_failed"
    assert entries[0].error is not None


def test_gate_block_is_logged():
    server.submit_purchase_order(
        draft_po_id="draft-nonexistent", approved=True, session_id="audit-test-3"
    )
    entries = audit.entries_for_session("audit-test-3")
    assert len(entries) == 1
    assert entries[0].outcome == "gate_blocked"


def test_successful_submit_logs_before_and_after_state():
    draft = server.draft_purchase_order(
        sku="SKU-002", quantity=30, justification="test", session_id="audit-test-4"
    )
    server.submit_purchase_order(
        draft_po_id=draft["draft_po_id"], approved=True, session_id="audit-test-4"
    )

    entries = audit.entries_for_session("audit-test-4")
    submit_entry = [e for e in entries if e.tool_name == "submit_purchase_order"][0]

    assert submit_entry.outcome == "success"
    assert submit_entry.before_state is not None
    assert submit_entry.after_state is not None
    assert submit_entry.after_state["stock"] == submit_entry.before_state["stock"] + 30


def test_full_flow_produces_complete_audit_trail():
    """A realistic session: draft, then submit. Both calls should be traceable."""
    session = "audit-test-5"
    draft = server.draft_purchase_order(
        sku="SKU-001", quantity=20, justification="restock", session_id=session
    )
    server.submit_purchase_order(draft_po_id=draft["draft_po_id"], approved=True, session_id=session)

    entries = audit.entries_for_session(session)
    tool_names = [e.tool_name for e in entries]
    assert tool_names == ["draft_purchase_order", "submit_purchase_order"]
    assert all(e.outcome == "success" for e in entries)
