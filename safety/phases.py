"""
Phase gating: the core pattern this demo exists to show.

The rule is simple and deliberately boring: submit_purchase_order cannot
succeed unless a matching draft_purchase_order happened first, in the
SAME session, and hasn't already been submitted. This is enforced here,
in code, server-side — not by an instruction telling an agent "please
call draft first." An agent that hallucinates, gets prompt-injected, or
just gets the order of operations wrong hits a hard, structured error
instead of silently corrupting state.

Session state lives in memory, keyed by session_id, with a lock guarding
concurrent access. This mirrors the pattern of short-lived, per-connection
state used in real MCP tool servers: sessions are cheap to create, cheap
to lose, and never the source of truth for anything durable.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from domain.purchase_orders import PurchaseOrderDraft


class GateError(Exception):
    """
    Raised whenever a tool is called out of the phase it requires.
    The message is written to tell the caller (human or agent) exactly
    what to do next — this is what lets an agent self-correct instead
    of just failing and stopping.
    """


@dataclass
class SessionState:
    session_id: str
    pending_drafts: dict[str, PurchaseOrderDraft] = field(default_factory=dict)
    submitted_draft_ids: set[str] = field(default_factory=set)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_access: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_sessions: dict[str, SessionState] = {}
_lock = threading.RLock()


def get_or_create_session(session_id: str) -> SessionState:
    with _lock:
        if session_id not in _sessions:
            _sessions[session_id] = SessionState(session_id=session_id)
        session = _sessions[session_id]
        session.last_access = datetime.now(timezone.utc).isoformat()
        return session


def register_draft(session_id: str, draft: PurchaseOrderDraft) -> None:
    """Called after draft_purchase_order succeeds. No gate on entry —
    drafting is always allowed, it has no side effects on real state."""
    with _lock:
        session = get_or_create_session(session_id)
        session.pending_drafts[draft.draft_id] = draft


def require_draft_for_submit(session_id: str, draft_id: str) -> PurchaseOrderDraft:
    """
    The actual gate. Raises GateError with a corrective message on every
    failure path — this is intentional; a generic "denied" is much less
    useful to an agent than "here is specifically what you're missing."
    """
    with _lock:
        session = _sessions.get(session_id)

        if session is None or draft_id not in session.pending_drafts:
            raise GateError(
                "GATE_BLOCKED: Cannot call submit_purchase_order. "
                f"No draft '{draft_id}' found in this session. "
                "You must call draft_purchase_order first."
            )

        if draft_id in session.submitted_draft_ids:
            raise GateError(
                "GATE_BLOCKED: This draft has already been submitted. "
                "Call draft_purchase_order again to create a new draft."
            )

        return session.pending_drafts[draft_id]


def mark_submitted(session_id: str, draft_id: str) -> None:
    with _lock:
        session = _sessions[session_id]
        session.submitted_draft_ids.add(draft_id)
