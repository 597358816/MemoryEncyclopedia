#!/usr/bin/env python3
"""
Prefetch SWE-bench Pro Docker images to local Docker archive files.

Default archive directory:
  data/swebench_pro/docker/

For each missing task image, this script downloads with skopeo through the
current shell proxy and saves a Docker-compatible .tar archive.

Optionally, use --load to import each downloaded archive into the current
Docker daemon after download.

Examples
--------
# First 20 tasks -> data/swebench_pro/docker/*.tar
python data/swebench_pro/eval/prefetch_images.py --limit 20

# All tasks
python data/swebench_pro/eval/prefetch_images.py --all

# Download + load into Docker daemon
python data/swebench_pro/eval/prefetch_images.py --limit 20 --load

# Custom archive directory
python data/swebench_pro/eval/prefetch_images.py \
  --limit 20 \
  --archive-dir /vepfs-mlp2/c20250203/public/wc/Memory_encyclopedia/data/swebench_pro/docker

Environment
-----------
Honors:
  HTTP_PROXY / HTTPS_PROXY / http_proxy / https_proxy
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_TASKS = Path("data/swebench_pro/tasks.jsonl")
DEFAULT_ARCHIVE_DIR = Path("data/swebench_pro/docker")
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
    env = os.environ.copy()
    for upper, lower in (
        ("HTTP_PROXY", "http_proxy"),
        ("HTTPS_PROXY", "https_proxy"),
        ("NO_PROXY", "no_proxy"),
    ):
        if upper in env and lower not in env:
            env[lower] = env[upper]
        elif lower in env and upper not in env:
            env[upper] = env[lower]
    return env


def run(cmd: list[str], *, env=None, capture=False):
    return subprocess.run(
        cmd,
        env=env,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def image_exists(image: str) -> bool:
    return run(["docker", "image", "inspect", image], capture=True).returncode == 0


def normalize_image_ref(
    dockerhub_tag: str,
    registry: str,
    repository: str,
) -> tuple[str, str]:
    tag = str(dockerhub_tag).strip()
    if not tag:
        raise ValueError("empty dockerhub_tag")

    if tag.startswith("docker://"):
        source = tag
        local = tag[len("docker://"):]
        if local.startswith("docker.io/"):
            local = local[len("docker.io/"):]
        return source, local

    if "/" in tag:
        local = tag
        if local.startswith("docker.io/"):
            local = local[len("docker.io/"):]
        source_ref = tag if tag.startswith(registry + "/") else registry + "/" + tag
        return f"docker://{source_ref}", local

    local = f"{repository}:{tag}"
    return f"docker://{registry}/{local}", local


def safe_archive_name(image: str) -> str:
    """
    Produce a readable filesystem-safe archive name from an image ref.
    """
    name = image.replace("/", "__").replace(":", "__")
    if len(name) > 220:
        digest = hashlib.sha256(image.encode()).hexdigest()[:16]
        name = name[:190] + "__" + digest
    return name + ".tar"


def append_log(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def select_tasks(tasks, start, limit, repo):
    selected = tasks
    if repo:
        q = repo.lower()
        selected = [t for t in selected if q in str(t.get("repo", "")).lower()]
    if start:
        selected = selected[start:]
    if limit is not None:
        selected = selected[:limit]
    return selected


def preflight(env):
    missing = [x for x in ("skopeo",) if shutil.which(x) is None]
    if missing:
        raise RuntimeError(
            "Missing required command: skopeo\n"
            "Install with: apt-get update && apt-get install -y skopeo"
        )

    proxy = (
        env.get("HTTPS_PROXY")
        or env.get("https_proxy")
        or env.get("HTTP_PROXY")
        or env.get("http_proxy")
    )
    print(f"[proxy] {proxy or 'not set'}")


def copy_to_archive(source, local_image, archive_path, retries, env):
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = archive_path.with_suffix(archive_path.suffix + ".partial")
    if tmp_path.exists():
        tmp_path.unlink()

    cmd = [
        "skopeo",
        "copy",
        "--retry-times",
        str(retries),
        source,
        f"docker-archive:{tmp_path}:{local_image}",
    ]

    print("[cmd]", " ".join(cmd))
    p = run(cmd, env=env)

    if p.returncode != 0:
        if tmp_path.exists():
            tmp_path.unlink()
        return False, f"skopeo exited with code {p.returncode}"

    tmp_path.replace(archive_path)
    return True, ""


def load_archive(archive_path: Path) -> bool:
    p = run(["docker", "load", "-i", str(archive_path)])
    return p.returncode == 0


def main():
    ap = argparse.ArgumentParser(
        description="Prefetch SWE-bench Pro images as local Docker archives."
    )
    ap.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    ap.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    ap.add_argument("--start", type=int, default=0)

    g = ap.add_mutually_exclusive_group()
    g.add_argument("--limit", type=int)
    g.add_argument("--all", action="store_true")

    ap.add_argument("--repo")
    ap.add_argument("--retries", type=int, default=5)
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    ap.add_argument("--repository", default=DEFAULT_REPOSITORY)
    ap.add_argument("--log", type=Path, default=DEFAULT_LOG)
    ap.add_argument(
        "--load",
        action="store_true",
        help="After download, docker load each archive into current daemon.",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Redownload archive even if .tar already exists.",
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

    tasks = read_jsonl(args.tasks)
    selected = select_tasks(
        tasks,
        args.start,
        None if args.all else args.limit,
        args.repo,
    )

    args.archive_dir.mkdir(parents=True, exist_ok=True)

    print(f"[tasks] total    : {len(tasks)}")
    print(f"[tasks] selected : {len(selected)}")
    print(f"[archive-dir]    : {args.archive_dir.resolve()}")
    print()

    seen = set()
    items = []
    for task in selected:
        source, local_image = normalize_image_ref(
            task["dockerhub_tag"],
            args.registry,
            args.repository,
        )
        if local_image in seen:
            continue
        seen.add(local_image)

        archive = args.archive_dir / safe_archive_name(local_image)
        items.append((task, source, local_image, archive))

    downloaded = 0
    skipped = 0
    loaded = 0
    failed = 0

    for i, (task, source, local_image, archive) in enumerate(items, 1):
        iid = str(task.get("instance_id", ""))
        print("=" * 90)
        print(f"[{i}/{len(items)}] {iid}")
        print(f"[image]   {local_image}")
        print(f"[archive] {archive}")

        if archive.exists() and archive.stat().st_size > 0 and not args.force:
            print(f"[skip] archive already exists ({archive.stat().st_size / 1024**3:.2f} GiB)")
            skipped += 1
        else:
            t0 = time.time()
            ok, err = copy_to_archive(
                source,
                local_image,
                archive,
                args.retries,
                env,
            )
            elapsed = time.time() - t0

            if not ok:
                print(f"[FAIL] {err}")
                failed += 1
                append_log(
                    args.log,
                    {
                        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "instance_id": iid,
                        "image": local_image,
                        "archive": str(archive),
                        "status": "failed",
                        "error": err,
                    },
                )
                continue

            downloaded += 1
            print(
                f"[ok] downloaded: "
                f"{archive.stat().st_size / 1024**3:.2f} GiB "
                f"in {elapsed:.1f}s"
            )

        if args.load:
            if image_exists(local_image):
                print("[load] image already exists in Docker daemon; skip docker load")
            else:
                print("[load] importing archive into Docker daemon...")
                if load_archive(archive):
                    print("[load] ok")
                    loaded += 1
                else:
                    print("[load] FAILED")
                    failed += 1
                    continue

        append_log(
            args.log,
            {
                "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "instance_id": iid,
                "repo": task.get("repo"),
                "image": local_image,
                "archive": str(archive),
                "archive_bytes": archive.stat().st_size if archive.exists() else None,
                "status": "ready",
                "loaded_into_docker": image_exists(local_image) if shutil.which("docker") else False,
            },
        )

    print()
    print("=" * 90)
    print("[summary]")
    print(f"  unique images      : {len(items)}")
    print(f"  downloaded archives: {downloaded}")
    print(f"  skipped archives   : {skipped}")
    print(f"  docker loads       : {loaded}")
    print(f"  failed             : {failed}")
    print(f"  archive directory  : {args.archive_dir.resolve()}")

    if failed:
        sys.exit(2)


if __name__ == "__main__":
    main()
