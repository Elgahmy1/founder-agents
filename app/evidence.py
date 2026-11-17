"""Evidence ledger: every market claim is either SOURCED (cites a retrieved
URL) or labelled ASSUMPTION. The rule is enforced here in code, not left to
the model: a citation to a source that was never retrieved, or to a source
whose text shares no key terms with the claim, is downgraded to ASSUMPTION.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from pydantic import BaseModel, Field

from app.research import Doc

_STOP = set(
    "the a an and or of to in for on with is are be by as at it this that from their they "
    "people users can will more most many some about into not no your you our we".split()
)


class RawClaim(BaseModel):
    """What the model returns for a claim."""
    text: str = Field(description="One factual statement about the market or customers")
    source_ids: list[str] = Field(default_factory=list, description="Ids like S1, S3 from the source list; empty if none")


@dataclass
class Claim:
    text: str
    status: str  # "SOURCED" or "ASSUMPTION"
    sources: list[str]
    note: str = ""

    def md(self) -> str:
        if self.status == "SOURCED":
            return f"{self.text} [source: {', '.join(self.sources)}]"
        return f"**ASSUMPTION:** {self.text}" + (f" _({self.note})_" if self.note else "")


def _terms(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", s.lower()) if w not in _STOP}


def resolve(raw: list[RawClaim], docs: list[Doc]) -> list[Claim]:
    by_id = {d.id: d for d in docs}
    out: list[Claim] = []
    for c in raw:
        ids = [i.strip().strip("[]") for i in c.source_ids]
        valid = [by_id[i] for i in ids if i in by_id]
        if not valid:
            note = "cited a source that was not retrieved" if ids else "no source"
            out.append(Claim(c.text, "ASSUMPTION", [], note))
            continue
        claim_terms = _terms(c.text)
        supported = [d for d in valid if d.origin == "founder" or claim_terms & _terms(d.title + " " + d.snippet)]
        if supported:
            out.append(Claim(c.text, "SOURCED", [d.url for d in supported]))
        else:
            out.append(Claim(c.text, "ASSUMPTION", [], "cited source does not mention this"))
    return out


def assumption_ids(ledger: list[dict]) -> list[tuple[str, str]]:
    """Stable IDs for every claim the run could not source, in the order they entered the ledger: ASM-01, ASM-02...
    They stay open across phases, and every later gate shows them before the founder chooses GO."""
    out = [c["text"] for c in ledger if c.get("status") == "ASSUMPTION"]
    return [(f"ASM-{i:02d}", t) for i, t in enumerate(dict.fromkeys(out), 1)]


def assumptions_md(ledger: list[dict], limit: int = 8) -> str:
    ids = assumption_ids(ledger)
    if not ids:
        return ""
    rows = [f"- **{i}** {t}" for i, t in ids[:limit]]
    more = [f"- ... and {len(ids) - limit} more in the run's evidence ledger"] if len(ids) > limit else []
    return "\n".join(["", "## Unproven assumptions before you choose GO", "",
                      f"{len(ids)} claim(s) in this run have no retrieved source yet. A GO keeps building on them:", *rows, *more, ""])


class Ledger:
    def __init__(self) -> None:
        self.claims: list[Claim] = []

    @staticmethod
    def _key(c: Claim) -> tuple:
        return (" ".join(re.findall(r"[a-z0-9]+", c.text.lower())), c.status, tuple(sorted(c.sources)))

    def add(self, claims: list[Claim]) -> list[Claim]:
        """The same claim with the same sources counts once, however often agents repeat it
        (for example once per opportunity), so the gates cannot pass on repetition."""
        seen = {self._key(c) for c in self.claims}
        for c in claims:
            if self._key(c) not in seen:
                seen.add(self._key(c))
                self.claims.append(c)
        return claims

    @property
    def sourced(self) -> list[Claim]:
        return [c for c in self.claims if c.status == "SOURCED"]

    @property
    def assumptions(self) -> list[Claim]:
        return [c for c in self.claims if c.status == "ASSUMPTION"]

    def urls(self) -> list[str]:
        return list(dict.fromkeys(u for c in self.sourced for u in c.sources))

    def to_list(self) -> list[dict]:
        return [asdict(c) for c in self.claims]

    @classmethod
    def from_list(cls, items: list[dict]) -> "Ledger":
        led = cls()
        led.claims = [Claim(**i) for i in items]
        return led
