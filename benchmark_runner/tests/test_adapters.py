from pathlib import Path
import json
import tempfile

from benchmark_runner.adapters import (
    extract_code,
    load_arxivmath,
    load_livecodebench,
)


def put_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x) + "\n" for x in rows))


def test_extract_code():
    x = "<think>abc</think>\n```python\nprint(1)\n```"
    assert extract_code(x) == "print(1)\n"


def test_arxiv_prompt():
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        b = r / "data" / "arxivmath"
        put_jsonl(b / "data.jsonl", [{"problem":"P","answer":"A"}])
        put_jsonl(b / "metadata.jsonl", [{"id":"x","release":"2026-05"}])
        items = load_arxivmath(r)
        assert len(items) == 1
        assert items[0].item_id == "x"
        assert "\\boxed{}" in items[0].messages[0]["content"]


def test_livecode_prompt():
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        b = r / "data" / "livecodebench"
        put_jsonl(b / "tasks.jsonl", [{
            "question_id":"q1",
            "question_title":"T",
            "question_content":"Do X",
            "starter_code":"",
            "difficulty":"easy",
            "platform":"x",
            "release":"release_v6"
        }])
        items = load_livecodebench(r)
        assert items[0].item_id == "q1"
        assert "Python 3" in items[0].messages[0]["content"]
