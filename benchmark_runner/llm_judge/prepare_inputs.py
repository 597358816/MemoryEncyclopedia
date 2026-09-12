import argparse,json
from pathlib import Path
from .io_utils import read_jsonl,get_path

def idx(rows,key):
    out={}
    for i,r in enumerate(rows):
        v=get_path(r,key)
        if v is None: raise ValueError(f"row {i}: missing {key}")
        s=str(v)
        if s in out: raise ValueError(f"duplicate id {s}")
        out[s]=r
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tasks",required=True); ap.add_argument("--predictions",required=True)
    ap.add_argument("--gold"); ap.add_argument("--output",required=True)
    ap.add_argument("--task-id-key",default="problem_id")
    ap.add_argument("--prediction-id-key",default="problem_id")
    ap.add_argument("--gold-id-key",default="problem_id")
    ap.add_argument("--problem-key",default="problem")
    ap.add_argument("--candidate-key",default="prediction")
    ap.add_argument("--reference-key",default="answer")
    ap.add_argument("--rubric-key")
    a=ap.parse_args()
    T=idx(read_jsonl(a.tasks),a.task_id_key)
    P=idx(read_jsonl(a.predictions),a.prediction_id_key)
    G=idx(read_jsonl(a.gold),a.gold_id_key) if a.gold else {}
    if set(T)!=set(P):
        raise SystemExit(f"ID mismatch: missing_predictions={len(set(T)-set(P))}, extra={len(set(P)-set(T))}")
    p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w") as f:
        for iid,t in T.items():
            pr=P[iid]; g=G.get(iid,{})
            row={
                "item_id":iid,
                "problem":get_path(t,a.problem_key),
                "candidate":get_path(pr,a.candidate_key),
                "reference":get_path(g,a.reference_key) if a.gold else None,
                "rubric":get_path(g,a.rubric_key) if a.rubric_key else None,
                "metadata":{"task":t.get("metadata"),"prediction":pr.get("metadata"),"gold":g.get("metadata")}
            }
            f.write(json.dumps(row,ensure_ascii=False)+"\n")
    print(f"[ok] wrote {len(T)} judge items -> {p}")

if __name__=="__main__":
    main()
