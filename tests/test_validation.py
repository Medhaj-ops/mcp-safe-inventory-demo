"""
Proves validation actually prevents bad drafts from producing a usable
draft_po_id, and that inventory is genuinely untouched when validation
fails — not just that an error message gets returned.
"""

from domain import inventory
import server


def test_negative_quantity_is_rejected_and_inventory_unchanged():
    before = inventory.get_item("SKU-001").stock

    result = server.draft_purchase_order(
        sku="SKU-001", quantity=-5, justification="test", session_id="val-test-1"
    )

    assert result["draft_po_id"] is None
    assert any(not r["ok"] for r in result["validation_results"])
    assert inventory.get_item("SKU-001").stock == before


def test_nonexistent_sku_is_rejected():
    result = server.draft_purchase_order(
        sku="SKU-DOES-NOT-EXIST", quantity=10, justification="test", session_id="val-test-2"
    )
    assert result["draft_po_id"] is None
    messages = [r["message"] for r in result["validation_results"]]
    assert any("not found" in m for m in messages)


def test_quantity_above_max_order_threshold_is_rejected():
    result = server.draft_purchase_order(
        sku="SKU-001", quantity=999_999, justification="test", session_id="val-test-3"
    )
    assert result["draft_po_id"] is None
    messages = [r["message"] for r in result["validation_results"]]
    assert any("exceeds max single-order threshold" in m for m in messages)


def test_empty_justification_is_rejected():
    result = server.draft_purchase_order(
        sku="SKU-001", quantity=10, justification="   ", session_id="val-test-4"
    )
    assert result["draft_po_id"] is None
    messages = [r["message"] for r in result["validation_results"]]
    assert any("Justification is required" in m for m in messages)


def test_multiple_failures_are_all_reported_not_just_the_first():
    """The whole point of run_all_validations: no short-circuiting."""
    result = server.draft_purchase_order(
        sku="SKU-NOPE", quantity=-1, justification="", session_id="val-test-5"
    )
    failed = [r for r in result["validation_results"] if not r["ok"]]
    assert len(failed) == 3  # sku, quantity, justification all fail independently


def test_valid_draft_does_not_touch_inventory_until_submit():
    """draft_purchase_order should NEVER be the thing that mutates state."""
    before = inventory.get_item("SKU-003").stock

    server.draft_purchase_order(
        sku="SKU-003", quantity=50, justification="valid draft", session_id="val-test-6"
    )

    assert inventory.get_item("SKU-003").stock == before
