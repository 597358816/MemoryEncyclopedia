from __future__ import annotations

from typing import Sequence


DEFAULT_SOLVER_MODEL = (
    "/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-4B/"
)


class QwenVLLM:
    def __init__(
        self,
        model_path: str = DEFAULT_SOLVER_MODEL,
        *,
        tensor_parallel_size: int = 1,
        dtype: str = "bfloat16",
        gpu_memory_utilization: float = 0.90,
        max_model_len: int = 32768,
        max_tokens: int = 8192,
        temperature: float = 0.6,
        top_p: float = 0.95,
        top_k: int = 20,
        seed: int = 0,
        enable_thinking: bool = True,
    ):
        from transformers import AutoTokenizer
        from vllm import LLM, SamplingParams

        self.model_path = model_path
        self.enable_thinking = enable_thinking
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
        )

        kwargs = dict(
            model=model_path,
            tensor_parallel_size=tensor_parallel_size,
            trust_remote_code=True,
            gpu_memory_utilization=gpu_memory_utilization,
            max_model_len=max_model_len,
        )
        if dtype != "auto":
            kwargs["dtype"] = dtype
        self.llm = LLM(**kwargs)

        sample_kwargs = dict(
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            seed=seed,
        )
        # Older vLLM versions support top_k, but keep compatibility defensive.
        try:
            self.params = SamplingParams(top_k=top_k, **sample_kwargs)
        except TypeError:
            self.params = SamplingParams(**sample_kwargs)

    def render(self, messages: list[dict[str, str]]) -> str:
        kwargs = {
            "tokenize": False,
            "add_generation_prompt": True,
        }
        try:
            return self.tokenizer.apply_chat_template(
                messages,
                enable_thinking=self.enable_thinking,
                **kwargs,
            )
        except TypeError:
            return self.tokenizer.apply_chat_template(messages, **kwargs)

    def generate(self, messages_batch: Sequence[list[dict[str, str]]]) -> list[str]:
        prompts = [self.render(m) for m in messages_batch]
        outputs = self.llm.generate(prompts, self.params)
        return [x.outputs[0].text for x in outputs]
