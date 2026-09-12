#!/usr/bin/env python3
import shutil, subprocess, sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
print("[python]", sys.version.split()[0])
for cmd in ["harbor","docker"]:
    print(f"[{cmd}]", shutil.which(cmd) or "MISSING")

if shutil.which("docker"):
    p=subprocess.run(["docker","version"],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    print("[docker daemon]", "OK" if p.returncode==0 else "FAIL: "+p.stderr.strip()[:300])

src=root/"external"/"terminal-bench-2"
n=len(list(src.rglob("task.toml"))) if src.exists() else 0
print("[downloaded task.toml]", n)
print("[expected]", 89)
