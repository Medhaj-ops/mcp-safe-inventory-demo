"""
Human approval: the gate the agent cannot open by itself.

The earlier version of this demo had submit_purchase_order(approved=True).
That flag was set by the agent, so "approval" really meant "the model
decided it was approved". An agent that is confused, overconfident or
prompt-injected can pass approved=True just as easily as a careful one.

Now approval comes from the human, through a channel the agent has no
write access to:

  - In a real MCP client, the server asks the user directly with MCP
    elicitation (ctx.elicit). The agent never sees an "approve" button.
  - In tests and evals, an ApprovalProvider stands in for the human.
  - With no channel at all, the answer is no. Fail closed.

The text the human approves is rendered here, from the draft the server
itself computed. It is never the agent's own description of what it is
about to do, so an agent cannot get a 5,000-unit order approved by
describing it as "a small top-up".
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel

from domain.purchase_orders import PurchaseOrderDraft

if TYPE_CHECKING:
    from mcp.server.mcpserver import Context

# A provider gets the server-rendered summary and the draft, and returns
# True only if a human said yes.
ApprovalProvider = Callable[[str, PurchaseOrderDraft], bool | Awaitable[bool]]

_provider: ApprovalProvider | None = None


class ApprovalForm(BaseModel):
    approve: bool


def set_provider(provider: ApprovalProvider | None) -> None:
    """Install a stand-in for the human (tests, evals, a CLI). None removes it."""
    global _provider
    _provider = provider


def render_summary(draft: PurchaseOrderDraft) -> str:
    return (
        f"Approve purchase order {draft.draft_id}?\n"
        f"  SKU:        {draft.sku}\n"
        f"  Quantity:   {draft.quantity}\n"
        f"  Stock:      {draft.current_stock} -> {draft.projected_stock}\n"
        f"  Reason:     {draft.justification}"
    )


async def request(draft: PurchaseOrderDraft, ctx: Context | None = None) -> tuple[bool, str]:
    """
    Ask the human. Returns (approved, channel) where channel names how the
    question was asked, for the audit log.
    """
    summary = render_summary(draft)

    if _provider is not None:
        result = _provider(summary, draft)
        if isinstance(result, Awaitable):
            result = await result
        return bool(result), "provider"

    if ctx is not None:
        try:
            response = await ctx.elicit(message=summary, schema=ApprovalForm)
        except Exception:
            # Client doesn't support elicitation: there is no human to ask.
            return False, "elicitation_unavailable"
        approved = response.action == "accept" and bool(getattr(response.data, "approve", False))
        return approved, "elicitation"

    return False, "no_channel"
