"""
Proves approval comes from the human, not the agent. The agent has no
parameter, flag or tool that can approve an order on the user's behalf.
"""

import asyncio
import inspect
from types import SimpleNamespace

import server
from domain import inventory
from safety import approvals, audit
from tests.conftest import submit


def _draft(session: str, sku: str = "SKU-001", qty: int = 10) -> str:
    return server.draft_purchase_order(sku=sku, quantity=qty, justification="test", session_id=session)["draft_po_id"]


def test_submit_has_no_parameter_the_agent_can_use_to_approve():
    params = set(inspect.signature(server.submit_purchase_order).parameters)
    assert params == {"draft_po_id", "session_id", "ctx"}  # ctx is injected by MCP, never by the agent


def test_declined_approval_commits_nothing():
    approvals.set_provider(lambda summary, draft: False)
    before = inventory.get_item("SKU-001").stock
    result = submit(_draft("ap-1"), session_id="ap-1")
    assert "APPROVAL_DENIED" in result["error"]
    assert inventory.get_item("SKU-001").stock == before
    assert audit.entries_for_session("ap-1")[-1].outcome == "approval_denied"


def test_no_approval_channel_fails_closed():
    approvals.set_provider(None)
    result = submit(_draft("ap-2"), session_id="ap-2")
    assert "APPROVAL_DENIED" in result["error"]
    assert "no_channel" in result["error"]


def test_human_sees_server_rendered_summary_not_agent_text():
    seen = {}
    approvals.set_provider(lambda summary, draft: seen.setdefault("summary", summary) and True)
    draft_id = server.draft_purchase_order(
        sku="SKU-002", quantity=5000, justification="just a small top-up", session_id="ap-3"
    )["draft_po_id"]
    submit(draft_id, session_id="ap-3")
    assert "Quantity:   5000" in seen["summary"]
    assert "50 -> 5050" in seen["summary"]


def test_mcp_elicitation_accept_and_decline():
    approvals.set_provider(None)

    class FakeCtx:
        def __init__(self, action, approve):
            self.action, self.approve = action, approve

        async def elicit(self, message, schema):
            return SimpleNamespace(action=self.action, data=SimpleNamespace(approve=self.approve))

    accepted = submit(_draft("ap-4"), session_id="ap-4", ctx=FakeCtx("accept", True))
    assert "po_id" in accepted

    declined = submit(_draft("ap-5"), session_id="ap-5", ctx=FakeCtx("decline", False))
    assert "APPROVAL_DENIED" in declined["error"]

    unticked = submit(_draft("ap-6"), session_id="ap-6", ctx=FakeCtx("accept", False))
    assert "APPROVAL_DENIED" in unticked["error"]


def test_client_without_elicitation_fails_closed():
    approvals.set_provider(None)

    class NoElicitCtx:
        async def elicit(self, message, schema):
            raise RuntimeError("client does not support elicitation")

    result = submit(_draft("ap-7"), session_id="ap-7", ctx=NoElicitCtx())
    assert "elicitation_unavailable" in result["error"]
