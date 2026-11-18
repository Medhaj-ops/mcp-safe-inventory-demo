**Agent:** `anthropic:claude-haiku-5-5@v3` · **3 trial(s) per task** · 20 tasks · run 2026-11-18T10:14:54+00:00

| | Baseline |
|---|---|
| Tasks passed (all trials) | 100% |
| Tasks passed on every one of 3 trials (pass^3) | 100% |
| Orders committed that the user didn't want | 0 |
| Approval requests for orders the user never asked for | 0 |
| Prompt injections followed | 0% |
| Asked before drafting on an ambiguous request | 100% |
| Re-asked after the user said no | 0 |
| Drafted an order when none was needed | 0 |
| Redundant chat confirmations (server already asks) | 0 |
| Avg tool calls per task | 2.8 |

Pass rate by category:

| | Baseline |
|---|---|
| happy path | 100% |
| recovery | 100% |
| limits | 100% |
| declined | 100% |
| ambiguity | 100% |
| injection | 100% |
| no action | 100% |
