from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class JudgeItem:
    item_id: str
    problem: str
    candidate: str
    reference: str | None = None
    rubric: str | None = None
    benchmark: str | None = None
    metadata: dict[str, Any] | None = None

@dataclass
class JudgeResult:
    item_id: str
    verdict: str
    score: float
    confidence: float
    reason: str
    judge_model: str
    benchmark: str | None = None
    raw_judge_output: str | None = None
    parse_error: str | None = None
    def to_dict(self):
        return asdict(self)
