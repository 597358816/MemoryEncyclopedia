import argparse,importlib,os
from pathlib import Path
DEFAULT="/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-14B/"
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--model",default=DEFAULT); a=ap.parse_args()
    bad=0
    if Path(a.model).is_dir(): print("[ok] model:",a.model)
    else: print("[FAIL] missing model:",a.model); bad+=1
    for n in ["torch","transformers"]:
        try:
            m=importlib.import_module(n); print(f"[ok] {n}: {getattr(m,'__version__','?')}")
        except Exception as e: print(f"[FAIL] {n}: {e}"); bad+=1
    try:
        m=importlib.import_module("vllm"); print("[ok] vllm:",getattr(m,"__version__","?"))
    except Exception as e:
        print("[note] vllm unavailable:",e)
        print("[note] use --backend transformers if needed")
    print("[info] CUDA_VISIBLE_DEVICES=",os.environ.get("CUDA_VISIBLE_DEVICES"))
    if bad: raise SystemExit(1)
if __name__=="__main__": main()
