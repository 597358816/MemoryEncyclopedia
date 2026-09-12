class VLLMBackend:
    def __init__(self, model_path, tp=1, dtype="bfloat16", gpu_memory=0.90,
                 max_model_len=32768, max_tokens=512, temperature=0.0,
                 seed=0, enable_thinking=False):
        from transformers import AutoTokenizer
        from vllm import LLM, SamplingParams
        self.enable_thinking=enable_thinking
        self.tokenizer=AutoTokenizer.from_pretrained(model_path,trust_remote_code=True)
        kwargs=dict(model=model_path,tensor_parallel_size=tp,trust_remote_code=True,
                    gpu_memory_utilization=gpu_memory,max_model_len=max_model_len)
        if dtype!="auto": kwargs["dtype"]=dtype
        self.llm=LLM(**kwargs)
        self.params=SamplingParams(temperature=temperature,top_p=1.0,
                                   max_tokens=max_tokens,seed=seed)
    def render(self,messages):
        kw=dict(tokenize=False,add_generation_prompt=True)
        try:
            return self.tokenizer.apply_chat_template(messages,enable_thinking=self.enable_thinking,**kw)
        except TypeError:
            return self.tokenizer.apply_chat_template(messages,**kw)
    def generate(self,prompts):
        return [o.outputs[0].text for o in self.llm.generate(list(prompts),self.params)]

class TransformersBackend:
    def __init__(self, model_path, max_tokens=512, enable_thinking=False, **_):
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        self.enable_thinking=enable_thinking; self.max_tokens=max_tokens
        self.tokenizer=AutoTokenizer.from_pretrained(model_path,trust_remote_code=True)
        self.model=AutoModelForCausalLM.from_pretrained(
            model_path,torch_dtype="auto",device_map="auto",trust_remote_code=True)
        self.model.eval()
    def render(self,messages):
        kw=dict(tokenize=False,add_generation_prompt=True)
        try:
            return self.tokenizer.apply_chat_template(messages,enable_thinking=self.enable_thinking,**kw)
        except TypeError:
            return self.tokenizer.apply_chat_template(messages,**kw)
    def generate(self,prompts):
        import torch
        out=[]
        for p in prompts:
            x=self.tokenizer(p,return_tensors="pt",add_special_tokens=False)
            x={k:v.to(self.model.device) for k,v in x.items()}
            n=x["input_ids"].shape[1]
            with torch.inference_mode():
                y=self.model.generate(**x,max_new_tokens=self.max_tokens,do_sample=False,
                    pad_token_id=self.tokenizer.eos_token_id)
            out.append(self.tokenizer.decode(y[0,n:],skip_special_tokens=True))
        return out

def make_backend(name, model_path, **kw):
    if name=="vllm": return VLLMBackend(model_path,**kw)
    if name=="transformers": return TransformersBackend(model_path,**kw)
    raise ValueError(name)
