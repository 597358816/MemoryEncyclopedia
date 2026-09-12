import json, re
from dataclasses import dataclass
from typing import Any

@dataclass
class ParsedJudgeOutput:
    verdict: str
    score: float
    confidence: float
    reason: str

def _obj(text: str):
    start = text.find("{")
    if start < 0:
        return None
    depth = 0; quoted = False; esc = False
    for i in range(start, len(text)):
        c = text[i]
        if quoted:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': quoted = False
            continue
        if c == '"': quoted = True
        elif c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: return text[start:i+1]
    return None

def _clip(v: Any, default: float):
    try: x = float(v)
    except Exception: return default
    return max(0.0, min(1.0, x))

def parse_judge_output(text: str):
    raw = text.strip()
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", raw, re.I|re.S)
    if m: raw = m.group(1)
    s = _obj(raw)
    if not s: raise ValueError("no JSON object")
    try: x = json.loads(s)
    except Exception as e: raise ValueError(f"invalid JSON: {e}") from e
    verdict = str(x.get("verdict","")).strip().lower()
    aliases = {
        "true":"correct","yes":"correct","pass":"correct","1":"correct",
        "false":"incorrect","no":"incorrect","fail":"incorrect","0":"incorrect",
        "unknown":"invalid","unjudgeable":"invalid","cannot_judge":"invalid"
    }
    verdict = aliases.get(verdict, verdict)
    if verdict not in {"correct","incorrect","invalid"}:
        raise ValueError(f"bad verdict: {verdict!r}")
    score = 1.0 if verdict == "correct" else 0.0
    confidence = _clip(x.get("confidence"), 0.5)
    reason = str(x.get("reason","")).strip() or "No reason provided."
    return ParsedJudgeOutput(verdict, score, confidence, reason)
