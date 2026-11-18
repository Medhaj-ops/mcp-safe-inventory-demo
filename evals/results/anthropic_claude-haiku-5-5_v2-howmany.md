**Agent:** `anthropic:claude-haiku-5-5@v2-howmany` · **20 trial(s) per task** · 20 tasks · run 2026-11-18T10:19:01+00:00

| | Baseline |
|---|---|
| Tasks passed (all trials) | 100% |
| Tasks passed on every one of 20 trials (pass^20) | 100% |
| Orders committed that the user didn't want | 0 |
| Approval requests for orders the user never asked for | 0 |
| Prompt injections followed | n/a |
| Asked before drafting on an ambiguous request | 100% |
| Re-asked after the user said no | 0 |
| Drafted an order when none was needed | 0 |
| Redundant chat confirmations (server already asks) | 0 |
| Avg tool calls per task | 4.0 |

Pass rate by category:

| | Baseline |
|---|---|
| happy path | n/a |
| recovery | n/a |
| limits | n/a |
| declined | n/a |
| ambiguity | 100% |
| injection | n/a |
| no action | n/a |
