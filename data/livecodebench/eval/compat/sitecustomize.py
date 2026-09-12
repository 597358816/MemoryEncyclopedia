"""
LiveCodeBench dataset compatibility shim v3.

Pin to an official historical HF commit that contains materialized Parquet
configs for both `v6` and `release_v6`, avoiding the legacy custom loader on
current main (which downloads all raw test*.jsonl files).

Pinned official dataset revision:
48d36ed304dca42cf8ab20e941262ccd096518a3
"""
import os

try:
    import datasets
    from huggingface_hub import HfApi, hf_hub_url

    _orig_load_dataset = datasets.load_dataset
    _REPO = "livecodebench/code_generation_lite"
    _PARQUET_REV = "48d36ed304dca42cf8ab20e941262ccd096518a3"
    _api = HfApi()
    _cache = {}

    def _files_for_config(tag: str):
        if tag in _cache:
            return _cache[tag]

        files = _api.list_repo_files(
            repo_id=_REPO,
            repo_type="dataset",
            revision=_PARQUET_REV,
        )

        prefix = f"{tag}/"
        matched = sorted(
            f for f in files
            if f.startswith(prefix)
            and f.endswith(".parquet")
            and f.split("/")[-1].startswith("test-")
        )

        if not matched:
            configs = sorted({
                f.split("/", 1)[0]
                for f in files
                if "/" in f and f.endswith(".parquet")
            })
            raise RuntimeError(
                f"LCB compat: no parquet files for config={tag!r} "
                f"at revision={_PARQUET_REV}. "
                f"Available configs: {configs}"
            )

        urls = [
            hf_hub_url(
                repo_id=_REPO,
                filename=f,
                repo_type="dataset",
                revision=_PARQUET_REV,
            )
            for f in matched
        ]
        _cache[tag] = urls

        if os.environ.get("LCB_COMPAT_VERBOSE") == "1":
            print(
                f"[LCB-COMPAT] config={tag} "
                f"revision={_PARQUET_REV} parquet_files={len(urls)}",
                flush=True,
            )
            for u in urls:
                print(f"[LCB-COMPAT]   {u}", flush=True)

        return urls

    def _lcb_load_dataset(path, *args, **kwargs):
        if path != _REPO:
            return _orig_load_dataset(path, *args, **kwargs)

        tag = kwargs.pop("version_tag", None)
        name = kwargs.pop("name", None)
        args = list(args)

        if tag is None and name is not None:
            tag = name
        if tag is None and args:
            tag = args.pop(0)
        if tag is None:
            tag = "release_v6"

        kwargs.pop("trust_remote_code", None)
        kwargs.pop("revision", None)

        urls = _files_for_config(tag)

        return _orig_load_dataset(
            "parquet",
            *args,
            data_files={"test": urls},
            **kwargs,
        )

    datasets.load_dataset = _lcb_load_dataset

except Exception as _e:
    if os.environ.get("LCB_COMPAT_VERBOSE") == "1":
        print(f"[LCB-COMPAT] init failed: {_e!r}", flush=True)

# Compatibility for old eager Anthropic imports in LiveCodeBench.
try:
    import anthropic
    if not hasattr(anthropic, "HUMAN_PROMPT"):
        anthropic.HUMAN_PROMPT = "\n\nHuman:"
    if not hasattr(anthropic, "AI_PROMPT"):
        anthropic.AI_PROMPT = "\n\nAssistant:"
except Exception:
    pass
