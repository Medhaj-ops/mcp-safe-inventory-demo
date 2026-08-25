"""
MCP server: three tools over a toy inventory system, demonstrating
phase-gating, validation-before-mutation, and structured audit logging.

This file is deliberately thin. Every tool follows the same shape:
  1. look up / touch state
  2. delegate to safety/ for gates and validation
  3. delegate to domain/ for the actual business logic
  4. record an audit entry
  5. return a structured result

The MCP server framework itself (mcp.server.fastmcp) is a thin wrapper;
swap it for a different transport and none of the logic in safety/ or
domain/ has to change. That decoupling is intentional and is the same
shape used in the production servers this demo is modeled after.
"""

from mcp.server.mcpserver import MCPServer

from domain import inventory, purchase_orders
from safety import audit, phases, validation
from safety.phases import GateError

mcp = MCPServer("safe-inventory-demo")


@mcp.tool()
def read_inventory_state(sku: str, session_id: str = "default") -> dict:
    """Read-only. No gate, no side effects on state. Always safe to call."""
    item = inventory.get_item(sku)
    result = vars(item) if item else {"error": f"SKU '{sku}' not found"}

    audit.record(
        session_id=session_id,
        tool_name="read_inventory_state",
        parameters={"sku": sku},
        outcome="success" if item else "not_found",
    )
    return result


@mcp.tool()
def draft_purchase_order(
    sku: str, quantity: int, justification: str, session_id: str = "default"
) -> dict:
    """
    Dry-run: validates and computes a projected state WITHOUT mutating
    inventory. This is the only path that produces a draft_id, which
    submit_purchase_order requires as proof a draft happened first.
    """
    results = validation.run_all_validations(sku, quantity, justification)

    if not validation.all_ok(results):
        errors = [r.message for r in results if not r.ok]
        audit.record(
            session_id=session_id,
            tool_name="draft_purchase_order",
            parameters={"sku": sku, "quantity": quantity, "justification": justification},
            outcome="validation_failed",
            error="; ".join(errors),
        )
        return {"draft_po_id": None, "validation_results": [vars(r) for r in results]}

    draft = purchase_orders.create_draft(sku, quantity, justification)
    phases.register_draft(session_id, draft)

    audit.record(
        session_id=session_id,
        tool_name="draft_purchase_order",
        parameters={"sku": sku, "quantity": quantity, "justification": justification},
        outcome="success",
    )

    return {
        "draft_po_id": draft.draft_id,
        "sku": draft.sku,
        "quantity": draft.quantity,
        "current_stock": draft.current_stock,
        "projected_stock": draft.projected_stock,
        "validation_results": [vars(r) for r in results],
    }


@mcp.tool()
def submit_purchase_order(
    draft_po_id: str, approved: bool = False, session_id: str = "default"
) -> dict:
    """
    The only tool that mutates inventory. Hard-gated: requires a matching
    draft from draft_purchase_order in this same session, and requires
    explicit approved=true. Both checks fail closed by default.
    """
    if not approved:
        error_msg = (
            "GATE_BLOCKED: submit_purchase_order requires approved=true. "
            "This is a deliberate safety check, not an oversight — "
            "call again with approved=true once the draft has been reviewed."
        )
        audit.record(
            session_id=session_id,
            tool_name="submit_purchase_order",
            parameters={"draft_po_id": draft_po_id, "approved": approved},
            outcome="gate_blocked",
            error=error_msg,
        )
        return {"error": error_msg}

    try:
        draft = phases.require_draft_for_submit(session_id, draft_po_id)
    except GateError as e:
        audit.record(
            session_id=session_id,
            tool_name="submit_purchase_order",
            parameters={"draft_po_id": draft_po_id, "approved": approved},
            outcome="gate_blocked",
            error=str(e),
        )
        return {"error": str(e)}

    po = purchase_orders.commit_draft(draft)
    phases.mark_submitted(session_id, draft_po_id)

    audit.record(
        session_id=session_id,
        tool_name="submit_purchase_order",
        parameters={"draft_po_id": draft_po_id, "approved": approved},
        outcome="success",
        before_state=po.before_state,
        after_state=po.after_state,
    )

    return {
        "po_id": po.po_id,
        "sku": po.sku,
        "quantity": po.quantity,
        "before_state": po.before_state,
        "after_state": po.after_state,
    }


if __name__ == "__main__":
    mcp.run()
