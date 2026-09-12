#!/usr/bin/env python3
"""
Prefetch SWE-bench Pro Docker images with skopeo.

Why this exists
---------------
On some clusters, the Docker daemon cannot access Docker Hub directly, while
the current shell can access the Internet through HTTP(S)_PROXY. In that setup,
`docker pull` fails but `skopeo copy` works because skopeo uses the shell proxy.

This script:
  1. reads data/swebench_pro/tasks.jsonl
  2. checks whether each task image already exists locally
  3. skips cached images
  4. uses skopeo to copy missing images into the current Docker daemon
  5. records successes/failures in a JSONL log

Typical usage
-------------
# First 20 tasks
python data/swebench_pro/eval/prefetch_images.py --limit 20

# All public tasks
python data/swebench_pro/eval/prefetch_images.py --all

# Tasks 100..119
python data/swebench_pro/eval/prefetch_images.py --start 100 --limit 20

# Only one repository
python data/swebench_pro/eval/prefetch_images.py --repo NodeBB/NodeBB

# Retry failures more aggressively
python data/swebench_pro/eval/prefetch_images.py --limit 20 --retries 8

Environment
-----------
The script honors:
  HTTP_PROXY / HTTPS_PROXY / http_proxy / https_proxy

Example:
  export HTTP_PROXY=http://127.0.0.1:7898
  export HTTPS_PROXY=http://127.0.0.1:7898
  export http_proxy=$HTTP_PROXY
  export https_proxy=$HTTPS_PROXY

Dependencies
------------
  docker
  skopeo
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable


DEFAULT_TASKS = Path("data/swebench_pro/tasks.jsonl")
DEFAULT_LOG = Path("data/swebench_pro/eval/prefetch_images.log.jsonl")
DEFAULT_REGISTRY = "docker.io"
DEFAULT_REPOSITORY = "jefzda/sweap-images"


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise RuntimeError(f"{path}:{lineno}: invalid JSON: {e}") from e
    return rows


def ensure_proxy_env() -> dict[str, str]:
    """
    Return a copy of os.environ and mirror upper/lower-case proxy variables.

    Some tools honor upper-case names, some honor lower-case names.
    """
    env = os.environ.copy()

    pairs = [
        ("HTTP_PROXY", "http_proxy"),
        ("HTTPS_PROXY", "https_proxy"),
        ("NO_PROXY", "no_proxy"),
    ]
    for upper, lower in pairs:
        if upper in env and lower not in env:
            env[lower] = env[upper]
        elif lower in env and upper not in env:
            env[upper] = env[lower]

    return env


def run(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = False,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        env=env,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def image_exists(image: str) -> bool:
    p = run(
        ["docker", "image", "inspect", image],
        capture=True,
    )
    return p.returncode == 0


def normalize_image_ref(
    dockerhub_tag: str,
    registry: str,
    repository: str,
) -> tuple[str, str]:
    """
    Return:
      source ref for skopeo, e.g.
        docker://docker.io/jefzda/sweap-images:TAG

      local Docker ref, e.g.
        jefzda/sweap-images:TAG

    SWE-bench Pro commonly stores only the tag in `dockerhub_tag`.
    This also tolerates a full image reference.
    """
    tag = str(dockerhub_tag).strip()
    if not tag:
        raise ValueError("empty dockerhub_tag")

    # Already a full transport-prefixed skopeo source.
    if tag.startswith("docker://"):
        source = tag
        local = tag[len("docker://"):]
        if local.startswith("docker.io/"):
            local = local[len("docker.io/"):]
        return source, local

    # Full Docker image reference, e.g. jefzda/sweap-images:foo
    # or docker.io/jefzda/sweap-images:foo
    if "/" in tag:
        local = tag
        if local.startswith("docker.io/"):
            local = local[len("docker.io/"):]
        source = f"docker://{tag if tag.startswith(registry + '/') else registry + '/' + tag}"
        return source, local

    # Normal SWE-bench Pro case: tag only.
    local = f"{repository}:{tag}"
    source = f"docker://{registry}/{local}"
    return source, local


def append_log(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def select_tasks(
    tasks: list[dict],
    *,
    start: int,
    limit: int | None,
    repo: str | None,
    ids: set[str] | None,
) -> list[dict]:
    selected = tasks

    if repo:
        repo_lower = repo.lower()
        selected = [
            t for t in selected
            if str(t.get("repo", "")).lower() == repo_lower
            or repo_lower in str(t.get("repo", "")).lower()
        ]

    if ids is not None:
        selected = [
            t for t in selected
            if str(t.get("instance_id", "")) in ids
        ]

    if start:
        selected = selected[start:]

    if limit is not None:
        selected = selected[:limit]

    return selected


def read_ids(path: Path) -> set[str]:
    """
    Supports either:
      - one instance_id per line
      - JSONL rows containing instance_id
    """
    ids: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("{"):
                obj = json.loads(s)
                iid = obj.get("instance_id")
                if iid:
                    ids.add(str(iid))
            else:
                ids.add(s)
    return ids


def preflight(env: dict[str, str]) -> None:
    missing = [x for x in ("docker", "skopeo") if shutil.which(x) is None]
    if missing:
        raise RuntimeError(
            "Missing required command(s): "
            + ", ".join(missing)
            + "\nInstall skopeo, e.g. `apt-get install -y skopeo`."
        )

    docker = run(["docker", "info"], capture=True)
    if docker.returncode != 0:
        raise RuntimeError(
            "Docker daemon is not reachable.\n"
            + (docker.stderr or docker.stdout or "")
        )

    proxy = (
        env.get("HTTPS_PROXY")
        or env.get("https_proxy")
        or env.get("HTTP_PROXY")
        or env.get("http_proxy")
    )
    if proxy:
        print(f"[proxy] {proxy}")
    else:
        print(
            "[warning] no HTTP(S)_PROXY is set. "
            "If Docker Hub is blocked on this cluster, skopeo may also fail."
        )


def skopeo_copy(
    source: str,
    local_image: str,
    *,
    retries: int,
    env: dict[str, str],
) -> tuple[bool, str]:
    cmd = [
        "skopeo",
        "copy",
        "--retry-times",
        str(retries),
        source,
        f"docker-daemon:{local_image}",
    ]

    print("[cmd]", " ".join(cmd))
    p = run(cmd, env=env, capture=False)

    if p.returncode != 0:
        return False, f"skopeo exited with code {p.returncode}"

    if not image_exists(local_image):
        return False, "skopeo returned success but image is not visible via docker image inspect"

    return True, ""


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Prefetch SWE-bench Pro Docker images via skopeo."
    )
    ap.add_argument(
        "--tasks",
        type=Path,
        default=DEFAULT_TASKS,
        help=f"tasks.jsonl path (default: {DEFAULT_TASKS})",
    )
    ap.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start index after repo/id filtering (default: 0)",
    )

    group = ap.add_mutually_exclusive_group()
    group.add_argument(
        "--limit",
        type=int,
        help="Prefetch at most N selected tasks",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Prefetch all selected tasks",
    )

    ap.add_argument(
        "--repo",
        help="Only tasks whose repo matches this string, e.g. NodeBB/NodeBB",
    )
    ap.add_argument(
        "--ids-file",
        type=Path,
        help="Only instance IDs listed in this file",
    )
    ap.add_argument(
        "--retries",
        type=int,
        default=5,
        help="skopeo retry count per image (default: 5)",
    )
    ap.add_argument(
        "--registry",
        default=DEFAULT_REGISTRY,
        help=f"Registry host (default: {DEFAULT_REGISTRY})",
    )
    ap.add_argument(
        "--repository",
        default=DEFAULT_REPOSITORY,
        help=f"Docker Hub repository (default: {DEFAULT_REPOSITORY})",
    )
    ap.add_argument(
        "--log",
        type=Path,
        default=DEFAULT_LOG,
        help=f"JSONL status log (default: {DEFAULT_LOG})",
    )
    ap.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Re-copy even if the image is already present locally",
    )
    ap.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately when one image fails",
    )
    args = ap.parse_args()

    if args.start < 0:
        ap.error("--start must be >= 0")
    if args.limit is not None and args.limit <= 0:
        ap.error("--limit must be > 0")
    if args.retries < 0:
        ap.error("--retries must be >= 0")

    env = ensure_proxy_env()
    preflight(env)

    if not args.tasks.exists():
        raise FileNotFoundError(args.tasks)

    tasks = read_jsonl(args.tasks)
    ids = read_ids(args.ids_file) if args.ids_file else None

    selected = select_tasks(
        tasks,
        start=args.start,
        limit=None if args.all else args.limit,
        repo=args.repo,
        ids=ids,
    )

    if not selected:
        print("[done] no matching tasks")
        return

    print(f"[tasks] total dataset : {len(tasks)}")
    print(f"[tasks] selected      : {len(selected)}")
    print(f"[log]   {args.log}")

    seen_images: set[str] = set()
    unique_items: list[tuple[dict, str, str]] = []

    for task in selected:
        if "dockerhub_tag" not in task:
            raise KeyError(
                f"{task.get('instance_id', '<unknown>')}: missing dockerhub_tag"
            )
        source, local = normalize_image_ref(
            task["dockerhub_tag"],
            args.registry,
            args.repository,
        )

        # Several tasks may theoretically refer to the same image.
        if local in seen_images:
            continue
        seen_images.add(local)
        unique_items.append((task, source, local))

    print(f"[images] unique selected: {len(unique_items)}")
    print()

    ok_count = 0
    skip_count = 0
    fail_count = 0
    started = time.time()

    for idx, (task, source, local_image) in enumerate(unique_items, 1):
        iid = str(task.get("instance_id", ""))
        repo = str(task.get("repo", ""))

        print("=" * 90)
        print(f"[{idx}/{len(unique_items)}] {iid}")
        print(f"[repo]  {repo}")
        print(f"[image] {local_image}")

        if not args.no_skip_existing and image_exists(local_image):
            print("[skip] image already exists locally")
            append_log(
                args.log,
                {
                    "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "instance_id": iid,
                    "repo": repo,
                    "image": local_image,
                    "status": "skipped_existing",
                },
            )
            skip_count += 1
            continue

        t0 = time.time()
        try:
            success, error = skopeo_copy(
                source,
                local_image,
                retries=args.retries,
                env=env,
            )
        except KeyboardInterrupt:
            print("\n[interrupted]")
            raise
        except Exception as e:
            success = False
            error = repr(e)

        elapsed = round(time.time() - t0, 2)

        if success:
            print(f"[ok] ready in {elapsed:.1f}s")
            ok_count += 1
            status = "downloaded"
        else:
            print(f"[FAIL] {error}")
            fail_count += 1
            status = "failed"

        append_log(
            args.log,
            {
                "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "instance_id": iid,
                "repo": repo,
                "source": source,
                "image": local_image,
                "status": status,
                "elapsed_seconds": elapsed,
                "error": error if not success else None,
            },
        )

        if not success and args.fail_fast:
            break

    total_elapsed = time.time() - started

    print()
    print("=" * 90)
    print("[summary]")
    print(f"  selected unique images : {len(unique_items)}")
    print(f"  downloaded             : {ok_count}")
    print(f"  skipped existing       : {skip_count}")
    print(f"  failed                 : {fail_count}")
    print(f"  elapsed                : {total_elapsed / 60:.1f} min")
    print(f"  log                    : {args.log}")

    if fail_count:
        sys.exit(2)


if __name__ == "__main__":
    main()