"""
MCP server: four tools over a toy inventory system, demonstrating
phase-gating, validation-before-mutation, human approval and structured
audit logging.

This file is deliberately thin. Every tool follows the same shape:
  1. look up / touch state
  2. delegate to safety/ for gates, validation and approval
  3. delegate to domain/ for the actual business logic
  4. record an audit entry
  5. return a structured result

Swap the transport and none of the logic in safety/ or domain/ has to
change. That decoupling is the same shape used in the production servers
this demo is modeled after.
"""

from mcp.server.mcpserver import Context, MCPServer

from domain import inventory, purchase_orders
from safety import approvals, audit, config, phases, validation
from safety.phases import GateError

mcp = MCPServer("safe-inventory-demo")


@mcp.tool()
def read_inventory_state(sku: str, session_id: str = "default") -> dict:
    """Read-only. No gate, no side effects on state. Always safe to call."""
    item = inventory.get_item(sku)
    result = vars(item) if item else {"error": config.error("NOT_FOUND", f"SKU '{sku}' not found. Try search_inventory.")}

    audit.record(
        session_id=session_id,
        tool_name="read_inventory_state",
        parameters={"sku": sku},
        outcome="success" if item else "not_found",
    )
    return result


@mcp.tool()
def search_inventory(query: str, session_id: str = "default") -> dict:
    """Read-only. Find items by SKU or name, e.g. 'widget'."""
    matches = [vars(i) for i in inventory.search(query)]
    audit.record(
        session_id=session_id,
        tool_name="search_inventory",
        parameters={"query": query},
        outcome="success",
    )
    return {"matches": matches}


@mcp.tool()
def draft_purchase_order(
    sku: str, quantity: int, justification: str, session_id: str = "default"
) -> dict:
    """
    Dry-run: validates and computes a projected state WITHOUT mutating
    inventory. This is the only path that produces a draft_po_id, which
    submit_purchase_order requires as proof a draft happened first.
    """
    params = {"sku": sku, "quantity": quantity, "justification": justification}
    results = validation.run_all_validations(sku, quantity, justification)

    if not validation.all_ok(results):
        errors = [r.message for r in results if not r.ok]
        audit.record(
            session_id=session_id,
            tool_name="draft_purchase_order",
            parameters=params,
            outcome="validation_failed",
            error="; ".join(errors),
        )
        if not config.ACTIONABLE_ERRORS:
            return {"draft_po_id": None, "error": "VALIDATION_FAILED"}
        return {"draft_po_id": None, "validation_results": [vars(r) for r in results]}

    draft = purchase_orders.create_draft(sku, quantity, justification)
    phases.register_draft(session_id, draft)

    audit.record(
        session_id=session_id,
        tool_name="draft_purchase_order",
        parameters=params,
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
async def submit_purchase_order(
    draft_po_id: str, session_id: str = "default", ctx: Context | None = None
) -> dict:
    """
    The only tool that mutates inventory. Needs a matching draft from
    draft_purchase_order in this session, and then asks the human to
    approve it. There is no parameter the agent can set to approve on
    the user's behalf.
    """
    params = {"draft_po_id": draft_po_id}

    try:
        draft = phases.require_draft_for_submit(session_id, draft_po_id)
    except GateError as e:
        audit.record(session_id=session_id, tool_name="submit_purchase_order",
                     parameters=params, outcome="gate_blocked", error=str(e))
        return {"error": str(e)}

    if config.REQUIRE_HUMAN_APPROVAL:
        approved, channel = await approvals.request(draft, ctx)
        if not approved:
            error_msg = config.error(
                "APPROVAL_DENIED",
                f"The user did not approve this order (via {channel}). Nothing was "
                "changed. Do not resubmit the same draft; ask the user what they "
                "want instead.",
            )
            audit.record(session_id=session_id, tool_name="submit_purchase_order",
                         parameters=params, outcome="approval_denied", error=error_msg)
            return {"error": error_msg}

    po = purchase_orders.commit_draft(draft)
    phases.mark_submitted(session_id, draft_po_id)

    audit.record(
        session_id=session_id,
        tool_name="submit_purchase_order",
        parameters=params,
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
