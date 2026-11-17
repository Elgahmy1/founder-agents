"""Founder approval queue.

Anything that would be published, sent, spent or signed becomes an
ApprovalItem. `execute()` refuses to run an item the founder has not
approved: this is the single code path to the outside world, so the rule is
enforced in code rather than in a prompt. Rejection is final for that item.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable

from app import guard
from app.decision_log import DecisionLog

KINDS = ("publish", "send", "spend", "sign")


class ApprovalRequired(PermissionError):
    pass


@dataclass
class ApprovalItem:
    kind: str
    title: str
    content: str
    executor: str  # name of a registered executor
    phase: int
    status: str = "pending"  # pending | approved | rejected | executed | superseded
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    decided_at: str | None = None
    note: str | None = None
    result: str | None = None


class ApprovalQueue:
    def __init__(self, log: DecisionLog, run_id: str, executors: dict[str, Callable[[ApprovalItem], str]]):
        self.log = log
        self.run_id = run_id
        self.executors = executors
        self.items: list[ApprovalItem] = []

    def submit(self, kind: str, title: str, content: str, executor: str, phase: int,
               check: Callable[[str], "guard.Verdict"] | None = None) -> ApprovalItem:
        if kind not in KINDS:
            raise ValueError(f"unknown action kind {kind}")
        if executor not in self.executors:
            raise ValueError(f"unknown executor {executor}")
        v = (check or guard.check_output)(content)
        if not v.allowed:
            self.log.append(agent="guard", action="block_artifact", run_id=self.run_id,
                            outcome="blocked", detail=f"{title}: {v.reason}")
            raise PermissionError(f"guard blocked '{title}': {v.reason}")
        item = ApprovalItem(kind=kind, title=title, content=content, executor=executor, phase=phase)
        self.items.append(item)
        self.log.append(agent="approval", action=f"request_{kind}_approval", run_id=self.run_id,
                        outcome="pending", detail=title, item_id=item.id)
        return item

    def get(self, item_id: str) -> ApprovalItem:
        for i in self.items:
            if i.id == item_id:
                return i
        raise KeyError(item_id)

    def pending(self) -> list[ApprovalItem]:
        return [i for i in self.items if i.status == "pending"]

    def supersede(self, executor: str) -> None:
        """A newer draft replaces older pending ones, so the founder cannot approve a stale version."""
        for i in self.items:
            if i.status == "pending" and i.executor == executor:
                i.status = "superseded"
                self.log.append(agent="approval_queue", action="supersede", run_id=self.run_id,
                                outcome="superseded", detail=i.title, item_id=i.id)

    def decide(self, item_id: str, approve: bool, note: str | None = None) -> ApprovalItem:
        """Only the founder calls this, from the UI or the CLI prompt."""
        item = self.get(item_id)
        if item.status != "pending":
            raise ValueError(f"item {item_id} already {item.status}")
        item.status = "approved" if approve else "rejected"
        item.decided_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        item.note = note
        self.log.append(agent="founder", action=f"{'approve' if approve else 'reject'}_{item.kind}",
                        approved_by="founder" if approve else None, run_id=self.run_id,
                        outcome=item.status, detail=item.title, item_id=item.id)
        if approve:
            self.execute(item_id)
        return item

    def execute(self, item_id: str) -> str:
        item = self.get(item_id)
        if item.status != "approved":
            self.log.append(agent="approval", action="refuse_unapproved_action", run_id=self.run_id,
                            outcome="refused", detail=item.title, item_id=item.id)
            raise ApprovalRequired(f"'{item.title}' has not been approved by the founder")
        item.result = self.executors[item.executor](item)
        item.status = "executed"
        self.log.append(agent="executor", action=f"execute_{item.executor}", approved_by="founder",
                        run_id=self.run_id, outcome="executed", detail=item.result, item_id=item.id)
        return item.result

    def to_list(self) -> list[dict]:
        return [asdict(i) for i in self.items]

    def load(self, items: list[dict]) -> None:
        self.items = [ApprovalItem(**i) for i in items]
