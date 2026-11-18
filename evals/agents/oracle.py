"""
Replays each task's reference solution. It is not a model: it exists to
prove every task is solvable and that the graders score a correct run as
a pass. If the oracle ever fails a task, the task or a grader is broken.
"""

from evals.env import Environment


class OracleAgent:
    name = "oracle"

    def run(self, env: Environment) -> None:
        last_draft = None
        for step in env.task.gold:
            kind = step[0]
            if kind == "search":
                env.call("search_inventory", {"query": step[1]})
            elif kind == "read":
                env.call("read_inventory_state", {"sku": step[1]})
            elif kind == "ask":
                env.call("ask_user", {"question": step[1]})
            elif kind == "draft":
                result = env.call("draft_purchase_order",
                                  {"sku": step[1], "quantity": step[2], "justification": "requested by user"})
                last_draft = result.get("draft_po_id") or last_draft
            elif kind == "submit":
                env.call("submit_purchase_order", {"draft_po_id": last_draft})
