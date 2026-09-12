import json
from pathlib import Path

ID_KEYS=["id","question_id","problem_id","task_id","instance_id","sample_id"]
PROBLEM_KEYS=["problem","question","prompt","instruction","question_content","problem_description","problem_description_main"]
CANDIDATE_KEYS=["prediction","response","output","candidate","model_output","generated_answer","answer","code"]
REFERENCE_KEYS=["reference","reference_answer","gold","ground_truth","target","expected_answer","answer"]
RUBRIC_KEYS=["rubric","grading_rubric","judge_rubric"]

def get_path(obj, path):
    if path is None: return None
    cur=obj
    for p in path.split("."):
        if isinstance(cur,dict) and p in cur: cur=cur[p]
        else: return None
    return cur

def resolve(row, explicit, fallbacks):
    if explicit: return get_path(row, explicit)
    for k in fallbacks:
        v=get_path(row,k)
        if v is not None: return v
    return None

def stringify(v):
    if v is None: return None
    return v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,sort_keys=True)

def read_jsonl(path):
    rows=[]
    with Path(path).open() as f:
        for n,line in enumerate(f,1):
            if not line.strip(): continue
            x=json.loads(line)
            if not isinstance(x,dict): raise ValueError(f"{path}:{n}: expected object")
            rows.append(x)
    return rows

def append_jsonl(path, rows):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a") as f:
        for x in rows: f.write(json.dumps(x,ensure_ascii=False)+"\n")
