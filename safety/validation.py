"""
Validation: pure functions that answer "is this allowed?" without ever
answering "do it". None of these touch inventory state.

Design choice worth noting: run_all_validations() does not short-circuit
on the first failure. A draft with three problems returns three error
messages, not one. This matters in practice — an agent (or a human)
correcting one issue at a time, resubmitting, and hitting a new error
each round is a worse experience than seeing everything wrong up front.
"""

from dataclasses import dataclass

from domain import inventory

MAX_ORDER_QUANTITY = 10_000


@dataclass
class ValidationResult:
    ok: bool
    message: str


def validate_quantity(quantity: int) -> ValidationResult:
    if quantity <= 0:
        return ValidationResult(False, f"Quantity must be positive (got {quantity})")
    return ValidationResult(True, "quantity ok")


def validate_sku_exists(sku: str) -> ValidationResult:
    if not inventory.sku_exists(sku):
        return ValidationResult(False, f"SKU '{sku}' not found in inventory")
    return ValidationResult(True, "sku ok")


def validate_within_max_order(quantity: int) -> ValidationResult:
    if quantity > MAX_ORDER_QUANTITY:
        return ValidationResult(
            False,
            f"Quantity {quantity} exceeds max single-order threshold of {MAX_ORDER_QUANTITY}",
        )
    return ValidationResult(True, "within max order ok")


def validate_justification(justification: str) -> ValidationResult:
    if not justification or not justification.strip():
        return ValidationResult(False, "Justification is required and cannot be empty")
    return ValidationResult(True, "justification ok")


def run_all_validations(sku: str, quantity: int, justification: str) -> list[ValidationResult]:
    """
    Runs every check regardless of earlier failures. sku_exists is checked
    first because validate_within_max_order and a future stock-aware check
    would be meaningless against a SKU that doesn't exist — but even so,
    quantity and justification checks still run independently since they
    don't depend on the SKU being valid.
    """
    return [
        validate_sku_exists(sku),
        validate_quantity(quantity),
        validate_within_max_order(quantity),
        validate_justification(justification),
    ]


def all_ok(results: list[ValidationResult]) -> bool:
    return all(r.ok for r in results)
