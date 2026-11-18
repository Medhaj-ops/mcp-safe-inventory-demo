"""
Two switches that exist so the evals can measure what each safety
pattern is worth. Production code would never turn either one off.

REQUIRE_HUMAN_APPROVAL
    True: submit_purchase_order asks the human before committing.
    False: a valid draft commits immediately, the way many agent
    integrations work today. Used for the "no approval gate" ablation.

ACTIONABLE_ERRORS
    True: every error says what went wrong and what to do next.
    False: errors are a bare code ("GATE_BLOCKED"). Used for the
    "bare errors" ablation, which measures how much error wording
    affects an agent's ability to recover.
"""

REQUIRE_HUMAN_APPROVAL = True
ACTIONABLE_ERRORS = True


def error(code: str, detail: str) -> str:
    """Format an error the way the current config says to."""
    return f"{code}: {detail}" if ACTIONABLE_ERRORS else code
