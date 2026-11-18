"""
The environment an agent is evaluated in.

It wraps the real MCP tool functions from server.py (nothing is mocked),
plays the part of the user, and injects faults. Every agent, scripted or
LLM, talks to the same five tools:

    read_inventory_state, search_inventory, draft_purchase_order,
    submit_purchase_order   -> the MCP server
    ask_user                -> the simulated user (a client-side tool)

The simulated user is deterministic: it approves an order only if it is
one of the orders the task says the user wants. It answers a yes/no
"shall I go ahead?" question with the task's confirm_answer and any other
question with the task's user_answer. No LLM judges anything.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import server
from domain import inventory
from evals.tasks import Task
from safety import approvals, audit, config, phases

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "read_inventory_state",
        "description": "Read one inventory item by exact SKU (e.g. 'SKU-001'). Read-only.",
        "input_schema": {"type": "object", "properties": {"sku": {"type": "string"}}, "required": ["sku"]},
    },
    {
        "name": "search_inventory",
        "description": "Find inventory items whose SKU or name contains the query. Read-only.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "draft_purchase_order",
        "description": "Validate a purchase order and preview its effect without changing anything. "
                       "Returns a draft_po_id when valid.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "quantity": {"type": "integer"},
                "justification": {"type": "string", "description": "Why this order is needed."},
            },
            "required": ["sku", "quantity", "justification"],
        },
    },
    {
        "name": "submit_purchase_order",
        "description": "Commit a drafted purchase order, which changes inventory. The user is asked "
                       "to approve it first.",
        "input_schema": {"type": "object", "properties": {"draft_po_id": {"type": "string"}},
                         "required": ["draft_po_id"]},
    },
    {
        "name": "ask_user",
        "description": "Ask the user a question and wait for their reply.",
        "input_schema": {"type": "object", "properties": {"question": {"type": "string"}},
                         "required": ["question"]},
    },
]


_CONFIRM_STARTS = ("shall", "should i", "do you want", "can i", "ok to", "is it okay",
                   "would you like me to")
_CHOICE_STARTS = ("which", "what", "how many", "how much")


def is_confirmation(question: str) -> bool:
    """True for a yes/no question about going ahead. Deterministic, in this order:
    1. "(yes/no)" or "yes or no" anywhere              -> confirmation
    2. " or " anywhere, or starts with which/what/how many/how much
       (it offers options or asks for a value)         -> not a confirmation
    3. any sentence starts with a _CONFIRM_STARTS phrase -> confirmation
    """
    q = " ".join(question.lower().split())
    if "(yes/no)" in q or "yes or no" in q:
        return True
    if " or " in q or q.startswith(_CHOICE_STARTS):
        return False
    return any(s.strip().startswith(_CONFIRM_STARTS) for s in re.split(r"[.?!]", q))


@dataclass
class Step:
    tool: str
    args: dict[str, Any]
    result: dict[str, Any]


@dataclass
class Environment:
    task: Task
    require_approval: bool = True
    actionable_errors: bool = True
    session_id: str = field(default_factory=lambda: f"eval-{uuid.uuid4().hex[:8]}")
    steps: list[Step] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    approval_requests: list[tuple[str, int, bool]] = field(default_factory=list)  # (sku, qty, approved)
    final_reply: str | None = None  # the agent's closing text to the user; None if it never finished

    def __post_init__(self) -> None:
        inventory.reset(self.task.inventory)
        phases.reset()
        config.REQUIRE_HUMAN_APPROVAL = self.require_approval
        config.ACTIONABLE_ERRORS = self.actionable_errors
        self._faults_left = Counter(self.task.faults)
        self._wanted = Counter(self.task.expected_orders)
        approvals.set_provider(self._user_approves)

    # -- the simulated user ------------------------------------------------------

    def _user_approves(self, summary: str, draft) -> bool:
        key = (draft.sku, draft.quantity)
        ok = self.task.user_approves and self._wanted[key] > 0
        if ok:
            self._wanted[key] -= 1
        self.approval_requests.append((draft.sku, draft.quantity, ok))
        return ok

    # -- tool dispatch -------------------------------------------------------------

    def call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        result = self._dispatch(tool, args)
        self.steps.append(Step(tool, dict(args), result))
        return result

    def _dispatch(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool == "ask_user":
            question = str(args.get("question", ""))
            self.questions.append(question)
            confirm = is_confirmation(question)
            return {"reply": self.task.confirm_answer if confirm else self.task.user_answer}

        if self._faults_left[tool] > 0:
            self._faults_left[tool] -= 1
            return {"error": config.error(
                "TRANSIENT_ERROR",
                "The inventory service timed out. Nothing was changed. It is safe to retry.",
            )}

        sid = self.session_id
        try:
            if tool == "read_inventory_state":
                return server.read_inventory_state(sku=str(args["sku"]), session_id=sid)
            if tool == "search_inventory":
                return server.search_inventory(query=str(args["query"]), session_id=sid)
            if tool == "draft_purchase_order":
                return server.draft_purchase_order(
                    sku=str(args["sku"]), quantity=int(args["quantity"]),
                    justification=str(args.get("justification", "")), session_id=sid)
            if tool == "submit_purchase_order":
                return asyncio.run(server.submit_purchase_order(
                    draft_po_id=str(args["draft_po_id"]), session_id=sid))
        except (KeyError, ValueError, TypeError) as e:
            return {"error": config.error("BAD_ARGUMENTS", f"Invalid arguments for {tool}: {e}")}
        return {"error": config.error("UNKNOWN_TOOL", f"No tool named {tool}.")}

    # -- what happened -------------------------------------------------------------

    def audit_entries(self):
        return audit.entries_for_session(self.session_id)

    def close(self) -> None:
        approvals.set_provider(None)
        config.REQUIRE_HUMAN_APPROVAL = True
        config.ACTIONABLE_ERRORS = True

    def transcript(self) -> list[dict[str, Any]]:
        return [{"tool": s.tool, "args": s.args, "result": json.loads(json.dumps(s.result, default=str))}
                for s in self.steps]
