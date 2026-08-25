# Example: happy path

This is real output from running the server's tool functions directly
(the same functions an MCP client would call over the protocol).

```python
>>> read_inventory_state(sku="SKU-002", session_id="demo")
{'sku': 'SKU-002', 'name': 'Widget B', 'stock': 50, 'reorder_threshold': 100}
```

Stock is below the reorder threshold (50 < 100). Draft a purchase order:

```python
>>> draft_purchase_order(
...     sku="SKU-002",
...     quantity=200,
...     justification="below reorder threshold",
...     session_id="demo",
... )
{
    'draft_po_id': 'draft-3e2cd2d6',
    'sku': 'SKU-002',
    'quantity': 200,
    'current_stock': 50,
    'projected_stock': 250,
    'validation_results': [
        {'ok': True, 'message': 'sku ok'},
        {'ok': True, 'message': 'quantity ok'},
        {'ok': True, 'message': 'within max order ok'},
        {'ok': True, 'message': 'justification ok'},
    ],
}
```

Note: inventory has NOT changed yet. This is a projection, not a mutation.
Now submit it, with explicit approval:

```python
>>> submit_purchase_order(
...     draft_po_id="draft-3e2cd2d6",
...     approved=True,
...     session_id="demo",
... )
{
    'po_id': 'po-518a8836',
    'sku': 'SKU-002',
    'quantity': 200,
    'before_state': {'sku': 'SKU-002', 'name': 'Widget B', 'stock': 50, 'reorder_threshold': 100},
    'after_state': {'sku': 'SKU-002', 'name': 'Widget B', 'stock': 250, 'reorder_threshold': 100},
}
```

Inventory now reflects the change, and the audit log (stdout, one JSON
object per line) recorded all three calls with full before/after state
for the mutation:

```json
{"timestamp": "...", "session_id": "demo", "tool_name": "read_inventory_state", "parameters": {"sku": "SKU-002"}, "outcome": "success", ...}
{"timestamp": "...", "session_id": "demo", "tool_name": "draft_purchase_order", "parameters": {"sku": "SKU-002", "quantity": 200, ...}, "outcome": "success", ...}
{"timestamp": "...", "session_id": "demo", "tool_name": "submit_purchase_order", "parameters": {"draft_po_id": "draft-3e2cd2d6", "approved": true}, "outcome": "success", "before_state": {...}, "after_state": {...}}
```
