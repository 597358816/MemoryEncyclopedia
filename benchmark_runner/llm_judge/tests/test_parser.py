from benchmark_runner.llm_judge.parser import parse_judge_output

def test_plain():
    x=parse_judge_output('{"verdict":"correct","score":1,"confidence":0.9,"reason":"ok"}')
    assert x.verdict=="correct" and x.score==1.0

def test_fence():
    x=parse_judge_output('```json\n{"verdict":"incorrect","score":0,"confidence":0.8,"reason":"wrong"}\n```')
    assert x.verdict=="incorrect" and x.score==0.0

def test_extra_text():
    x=parse_judge_output('Result: {"verdict":"correct","score":1,"confidence":1,"reason":"equivalent"} done')
    assert x.verdict=="correct"

def test_binary_normalization():
    x=parse_judge_output('{"verdict":"incorrect","score":0.9,"confidence":0.7,"reason":"wrong"}')
    assert x.score==0.0
