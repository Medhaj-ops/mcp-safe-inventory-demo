"""
Toy in-memory inventory "database".

This is intentionally the simplest possible thing that could work: a
module-level dict. There is no real database here on purpose — the point
of this demo is the safety patterns around mutation, not the storage layer.
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class InventoryItem:
    sku: str
    name: str
    stock: int
    reorder_threshold: int


# Seed data. Mutated only through apply_stock_change() below.
_inventory: dict[str, InventoryItem] = {
    "SKU-001": InventoryItem("SKU-001", "Widget A", stock=500, reorder_threshold=100),
    "SKU-002": InventoryItem("SKU-002", "Widget B", stock=50, reorder_threshold=100),
    "SKU-003": InventoryItem("SKU-003", "Gadget C", stock=200, reorder_threshold=50),
}


def get_item(sku: str) -> InventoryItem | None:
    """Pure read. No side effects."""
    return _inventory.get(sku)


def sku_exists(sku: str) -> bool:
    return sku in _inventory


def apply_stock_change(sku: str, delta: int) -> InventoryItem:
    """
    The ONLY function in this module that mutates state.

    This is called from exactly one place in the whole codebase:
    domain/purchase_orders.py::commit_draft(), which is itself only
    reachable after phase gates + validation have passed. Keeping the
    mutation surface this narrow is deliberate — it makes "where can
    inventory actually change?" a one-function answer.
    """
    current = _inventory[sku]
    updated = replace(current, stock=current.stock + delta)
    _inventory[sku] = updated
    return updated


def snapshot() -> dict[str, dict]:
    """Read-only snapshot of the whole inventory, for audit/before-after logging."""
    return {sku: vars(item) for sku, item in _inventory.items()}
