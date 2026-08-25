"""
Purchase order drafting + commitment.

Drafts are proposals: they compute a projected state WITHOUT touching
inventory. Only commit_draft() ever calls apply_stock_change(), and only
the safety layer (safety/phases.py) decides when commit_draft() is
allowed to be called.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from domain import inventory


@dataclass
class PurchaseOrderDraft:
    draft_id: str
    sku: str
    quantity: int
    justification: str
    current_stock: int
    projected_stock: int
    created_at: str


@dataclass
class PurchaseOrder:
    po_id: str
    draft_id: str
    sku: str
    quantity: int
    before_state: dict
    after_state: dict
    committed_at: str


def create_draft(sku: str, quantity: int, justification: str) -> PurchaseOrderDraft:
    """
    Pure: computes a projected state, does NOT call apply_stock_change.
    Assumes the caller has already validated sku/quantity — this function
    does not re-validate, it just projects. Validation lives in
    safety/validation.py and runs before this is called.
    """
    item = inventory.get_item(sku)
    current_stock = item.stock if item else 0
    return PurchaseOrderDraft(
        draft_id=f"draft-{uuid.uuid4().hex[:8]}",
        sku=sku,
        quantity=quantity,
        justification=justification,
        current_stock=current_stock,
        projected_stock=current_stock + quantity,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def commit_draft(draft: PurchaseOrderDraft) -> PurchaseOrder:
    """
    The only function that turns a draft into a real, inventory-affecting
    purchase order. This is intentionally NOT gated internally — the gate
    lives in safety/phases.py, which decides whether this function is
    ever reached. Keeping the gate external to the domain logic is the
    whole point: the domain layer doesn't know or care about sessions,
    phases, or approval — it just correctly does the one thing it's asked.
    """
    before = inventory.snapshot()
    inventory.apply_stock_change(draft.sku, draft.quantity)
    after = inventory.snapshot()

    return PurchaseOrder(
        po_id=f"po-{uuid.uuid4().hex[:8]}",
        draft_id=draft.draft_id,
        sku=draft.sku,
        quantity=draft.quantity,
        before_state=before[draft.sku],
        after_state=after[draft.sku],
        committed_at=datetime.now(timezone.utc).isoformat(),
    )
