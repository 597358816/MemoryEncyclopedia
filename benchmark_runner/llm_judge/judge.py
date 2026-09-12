from __future__ import annotations
import argparse, json
from pathlib import Path
from .backends import make_backend
from .io_utils import (
    ID_KEYS,PROBLEM_KEYS,CANDIDATE_KEYS,REFERENCE_KEYS,RUBRIC_KEYS,
    resolve,stringify,read_jsonl,append_jsonl
)
from .parser import parse_judge_output
from .prompts import build_messages
from .schema import JudgeItem, JudgeResult

DEFAULT_MODEL="/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-14B/"

def make_item(row,i,args):
    iid=resolve(row,args.id_key,ID_KEYS)
    if iid is None: iid=str(i)
    problem=resolve(row,args.problem_key,PROBLEM_KEYS)
    candidate=resolve(row,args.candidate_key,CANDIDATE_KEYS)
    reference=resolve(row,args.reference_key,REFERENCE_KEYS)
    rubric=args.rubric_text if args.rubric_text else resolve(row,args.rubric_key,RUBRIC_KEYS)
    if problem is None:
        raise ValueError(f"row {i} ({iid}): missing problem; use --problem-key")
    if candidate is None:
        raise ValueError(f"row {i} ({iid}): missing candidate; use --candidate-key")
    return JudgeItem(str(iid),stringify(problem) or "",stringify(candidate) or "",
                     stringify(reference),stringify(rubric),args.benchmark,
                     row.get("metadata") if isinstance(row.get("metadata"),dict) else None)

def summarize(rows):
    c={"correct":0,"incorrect":0,"invalid":0}
    conf=0.0
    for x in rows:
        v=x.get("verdict","invalid")
        if v not in c: v="invalid"
        c[v]+=1
        try: conf+=float(x.get("confidence",0))
        except Exception: pass
    n=len(rows); valid=c["correct"]+c["incorrect"]
    return {
        "n_total":n,"n_correct":c["correct"],"n_incorrect":c["incorrect"],
        "n_invalid":c["invalid"],
        "accuracy_all":c["correct"]/n if n else None,
        "accuracy_valid_only":c["correct"]/valid if valid else None,
        "mean_confidence":conf/n if n else None,
    }

def main():
    ap=argparse.ArgumentParser("Local Qwen3 LLM-as-Judge")
    ap.add_argument("--input",required=True); ap.add_argument("--output",required=True)
    ap.add_argument("--summary"); ap.add_argument("--benchmark")
    ap.add_argument("--id-key"); ap.add_argument("--problem-key"); ap.add_argument("--candidate-key")
    ap.add_argument("--reference-key"); ap.add_argument("--rubric-key"); ap.add_argument("--rubric-text")
    ap.add_argument("--model",default=DEFAULT_MODEL)
    ap.add_argument("--backend",choices=["vllm","transformers"],default="vllm")
    ap.add_argument("--tensor-parallel-size",type=int,default=1)
    ap.add_argument("--dtype",default="bfloat16")
    ap.add_argument("--gpu-memory-utilization",type=float,default=.90)
    ap.add_argument("--max-model-len",type=int,default=32768)
    ap.add_argument("--max-tokens",type=int,default=512)
    ap.add_argument("--temperature",type=float,default=0.0)
    ap.add_argument("--seed",type=int,default=0)
    ap.add_argument("--enable-thinking",action="store_true")
    ap.add_argument("--batch-size",type=int,default=32)
    ap.add_argument("--retry-invalid",type=int,default=1)
    ap.add_argument("--resume",action="store_true")
    args=ap.parse_args()

    rows=read_jsonl(args.input)
    items=[make_item(r,i,args) for i,r in enumerate(rows)]
    outp=Path(args.output)
    done=set()
    if args.resume and outp.exists():
        done={str(x["item_id"]) for x in read_jsonl(outp) if "item_id" in x}
    elif outp.exists():
        outp.unlink()
    pending=[x for x in items if x.item_id not in done]
    print(json.dumps({
        "n_input":len(items),"n_done":len(done),"n_pending":len(pending),
        "judge_model":args.model,"backend":args.backend,
        "enable_thinking":args.enable_thinking
    },ensure_ascii=False,indent=2),flush=True)

    if pending:
        backend=make_backend(
            args.backend,args.model,tp=args.tensor_parallel_size,dtype=args.dtype,
            gpu_memory=args.gpu_memory_utilization,max_model_len=args.max_model_len,
            max_tokens=args.max_tokens,temperature=args.temperature,seed=args.seed,
            enable_thinking=args.enable_thinking
        )
        for start in range(0,len(pending),args.batch_size):
            batch=pending[start:start+args.batch_size]
            prompts=[backend.render(build_messages(x)) for x in batch]
            raws=backend.generate(prompts)
            outs=[]
            for item,prompt,raw in zip(batch,prompts,raws):
                parsed=None; err=None; last=raw
                for attempt in range(args.retry_invalid+1):
                    try:
                        parsed=parse_judge_output(last); break
                    except Exception as e:
                        err=str(e)
                        if attempt>=args.retry_invalid: break
                        last=backend.generate([prompt+"\n\nReturn ONLY the required valid JSON object."])[0]
                if parsed is None:
                    res=JudgeResult(item.item_id,"invalid",0.0,0.0,
                        "Judge output could not be parsed.",args.model,item.benchmark,last,err)
                else:
                    res=JudgeResult(item.item_id,parsed.verdict,parsed.score,parsed.confidence,
                        parsed.reason,args.model,item.benchmark,last,None)
                outs.append(res.to_dict())
            append_jsonl(outp,outs)
            print(f"[judge] {min(start+len(batch),len(pending))}/{len(pending)}",flush=True)

    allrows=read_jsonl(outp) if outp.exists() else []
    s=summarize(allrows)
    s.update({"benchmark":args.benchmark,"judge_model":args.model,"backend":args.backend})
    sp=Path(args.summary or (str(outp)+".summary.json"))
    sp.parent.mkdir(parents=True,exist_ok=True)
    sp.write_text(json.dumps(s,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(s,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
