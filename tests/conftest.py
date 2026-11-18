import asyncio

import pytest

import server
from domain import inventory
from safety import approvals, config, phases


@pytest.fixture(autouse=True)
def fresh_state():
    """Every test starts from seed inventory, no sessions, a human who says yes,
    and the default (production) safety config."""
    inventory.reset()
    phases.reset()
    approvals.set_provider(lambda summary, draft: True)
    config.REQUIRE_HUMAN_APPROVAL = True
    config.ACTIONABLE_ERRORS = True
    yield
    approvals.set_provider(None)


def submit(draft_po_id: str, session_id: str = "default", ctx=None) -> dict:
    """Sync wrapper so tests read like the other tool calls."""
    return asyncio.run(server.submit_purchase_order(draft_po_id=draft_po_id, session_id=session_id, ctx=ctx))
