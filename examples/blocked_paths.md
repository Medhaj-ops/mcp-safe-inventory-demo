# Example: what the safety layer actually catches

Real output. Each of these is a separate session, showing one failure
mode in isolation.

## Scenario A — skipping the draft entirely

An agent (or a bug, or a prompt injection) tries to submit directly:

```python
>>> submit_purchase_order(draft_po_id="draft-fake", session_id="s2")
{'error': "GATE_BLOCKED: Cannot call submit_purchase_order. No draft 'draft-fake' found in this session. You must call draft_purchase_order first."}
```

Inventory is untouched. The error message tells the caller exactly what
to do next — this matters when the caller is an LLM agent trying to
self-correct, not just a human reading logs.

## Scenario B — the human says no

The agent cannot approve an order itself: `submit_purchase_order` has no
`approved` parameter. The server asks the human (MCP elicitation in a
real client), and shows them a summary it rendered from the draft, not
the agent's own description:

```text
Approve purchase order draft-43c04554?
  SKU:        SKU-001
  Quantity:   50
  Stock:      500 -> 550
  Reason:     test
```

```python
>>> submit_purchase_order(draft_po_id="draft-43c04554", session_id="s3")   # human declined
{'error': 'APPROVAL_DENIED: The user did not approve this order (via provider). Nothing was changed. Do not resubmit the same draft; ask the user what they want instead.'}

>>> submit_purchase_order(draft_po_id="draft-43c04554", session_id="s3")   # no approval channel at all
{'error': 'APPROVAL_DENIED: The user did not approve this order (via no_channel). Nothing was changed. Do not resubmit the same draft; ask the user what they want instead.'}
```

With no way to reach a human, the answer is no. Fail closed.

## Scenario C — invalid draft (multiple simultaneous problems)

```python
>>> draft_purchase_order(sku="SKU-FAKE", quantity=-5, justification="", session_id="s4")
{
    'draft_po_id': None,
    'validation_results': [
        {'ok': False, 'message': "SKU 'SKU-FAKE' not found in inventory"},
        {'ok': False, 'message': 'Quantity must be positive (got -5)'},
        {'ok': True,  'message': 'within max order ok'},
        {'ok': False, 'message': 'Justification is required and cannot be empty'},
    ],
}
```

All three real problems are reported in one response — not just the
first one encountered. Inventory is unchanged; no draft_id was issued,
so there is nothing to submit even if someone tried.

## Scenario D — session isolation

A draft created in one session cannot be submitted from a different
session, even with the correct draft_id:

```python
>>> draft = draft_purchase_order(sku="SKU-001", quantity=10, justification="test", session_id="owner")
>>> submit_purchase_order(draft_po_id=draft["draft_po_id"], session_id="intruder")
{'error': "GATE_BLOCKED: Cannot call submit_purchase_order. No draft '...' found in this session. You must call draft_purchase_order first."}
```

## Scenario E — replay protection

A draft can only be submitted once:

```python
>>> submit_purchase_order(draft_po_id="draft-a1b2c3d4", session_id="s3")
{'po_id': 'po-...', ...}  # succeeds

>>> submit_purchase_order(draft_po_id="draft-a1b2c3d4", session_id="s3")
{'error': 'GATE_BLOCKED: This draft has already been submitted. Call draft_purchase_order again to create a new draft.'}
```

Every one of these scenarios has an executable test in `tests/`
(`test_phase_gates.py`, `test_validation.py`) — this file shows what
they demonstrate; the tests are what prove it stays true.
