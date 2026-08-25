"""
Audit logging: every tool call gets one structured entry, regardless of
outcome. Gate rejections and validation failures are logged too — an
audit trail that only records successes is missing exactly the events
you'd most want to review later (what did the agent try that got blocked,
and why).

Writes to two places:
  - stdout, as one JSON object per line (the format a real log pipeline
    would ingest)
  - an in-memory list, so the demo's tests and example walkthroughs can
    inspect what got logged without parsing stdout
"""

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AuditEntry:
    timestamp: str
    session_id: str
    tool_name: str
    parameters: dict[str, Any]
    outcome: str  # "success" | "gate_blocked" | "validation_failed"
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    error: str | None = None


_log: list[AuditEntry] = []
_lock = threading.RLock()


def record(
    session_id: str,
    tool_name: str,
    parameters: dict[str, Any],
    outcome: str,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    error: str | None = None,
) -> AuditEntry:
    entry = AuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
        tool_name=tool_name,
        parameters=parameters,
        outcome=outcome,
        before_state=before_state,
        after_state=after_state,
        error=error,
    )
    with _lock:
        _log.append(entry)
    print(json.dumps(asdict(entry)), flush=True)
    return entry


def all_entries() -> list[AuditEntry]:
    with _lock:
        return list(_log)


def entries_for_session(session_id: str) -> list[AuditEntry]:
    with _lock:
        return [e for e in _log if e.session_id == session_id]


def clear() -> None:
    """Test-only helper — real deployments would never clear an audit log."""
    with _lock:
        _log.clear()
