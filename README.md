# Safe MCP patterns for agents that mutate business state

A minimal MCP server showing three patterns for giving AI agents safe
write-access to real business systems: **phase-gating**,
**validation-before-mutation**, and **structured audit logging**.

This is a demo, not a product. The domain (a toy inventory + purchase
order system) exists only to give the patterns something concrete to
apply to — the patterns themselves are the point, and they're
domain-agnostic.

## Why this exists

AI agents are increasingly given write access to real systems — orders,
inventory, CRM records, forecasts. The common failure mode isn't that
the underlying LLM is unreliable in some abstract sense; it's that
implementations often trust the model to "do the right thing" with no
structural guardrail behind it. When an agent hallucinates a state, gets
manipulated by a prompt injection, or just gets the order of operations
wrong, the result is a silent, incorrect write to a system that a human
now has to notice, diagnose, and fix after the fact.

The three patterns below aren't novel research — they're standard
engineering discipline for anything touching production state,
applied specifically to agent tool calls.

## The three patterns

**1. Phase gating.** A mutating operation (`submit_purchase_order`)
cannot succeed unless a corresponding read/preview operation
(`draft_purchase_order`) happened first, in the same session. This is
enforced in code — a hard error, not a prompt instruction the model can
ignore or be talked out of. The error message tells the caller exactly
what to do next, which is what lets an agent self-correct instead of
just failing.

**2. Validation-before-mutation.** Every check — does the SKU exist, is
the quantity sane, does this exceed a sane order threshold — runs
against a *pure* representation of the proposed change, before anything
is written. Validation never has side effects. And critically: all
checks run regardless of earlier failures, so a caller sees every
problem at once instead of fixing one, resubmitting, and hitting the
next.

**3. Structured audit logging.** Every tool call is logged — including
blocked and rejected ones, not just successful mutations. An audit trail
that's silent about denied attempts is missing exactly the events most
worth reviewing later: what did the agent try that got stopped, and why.

## The demo

- [`examples/happy_path.md`](examples/happy_path.md) — draft → review →
  submit, with real captured output
- [`examples/blocked_paths.md`](examples/blocked_paths.md) — five ways
  the safety layer actually stops a bad call, also with real output

## Try it yourself

```bash
pip install -r requirements.txt
pytest tests/ -v          # 17 tests, exercises every pattern above
python server.py          # runs the MCP server over stdio
```

The tests are the actual proof, not the prose above. If you want to
verify a claim in this README, the corresponding test is a better
source of truth than my description of it.

## Structure

```
server.py              # MCP tool definitions — thin, delegates everywhere
safety/
  phases.py             # session state + the phase gate itself
  validation.py         # pure validation functions
  audit.py               # structured logging, including failures
domain/
  inventory.py           # toy in-memory "database"
  purchase_orders.py    # draft/commit data + transformations
tests/                   # one file per pattern, ~17 tests total
examples/                 # real captured walkthroughs
```

`safety/` and `domain/` don't import from each other in the direction
you'd expect a "business logic" and "guardrails" split to invert: the
domain layer has no idea sessions or approval exist. The gate lives
entirely outside it, in `safety/phases.py`, which decides whether
`domain.purchase_orders.commit_draft()` is ever reached at all. That
separation is deliberate — it's what makes it possible to reason about
the safety properties without also reasoning about inventory logic at
the same time.

## What this is not

Not production code. No real database — inventory is a Python dict.
No authentication. Session state is in-memory and single-process. This
exists to make the safety patterns inspectable and testable in
isolation, not to be a system anyone should deploy.

## Background

I designed and built production MCP servers (Go, Kubernetes) during my
internship at Eli Lilly, including phase-gated tool access and mandatory
validation before any state-mutating deployment operation. This demo is
built fresh, in a different domain, using none of that code — it
isolates the same underlying patterns so they can be read, run, and
tested without requiring access to anything proprietary.
