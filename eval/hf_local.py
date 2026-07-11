"""Pinned, traceable Hugging Face inference for the APUSH GPU evaluator.

Heavy GPU dependencies are imported lazily so local unit tests can import this
module without installing PyTorch, Transformers, PEFT, or bitsandbytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Iterable


EMPTY_THINK_RE = re.compile(r"<think>\s*</think>\s*", re.I | re.S)


def strip_empty_think_block(text: str) -> str:
    return EMPTY_THINK_RE.sub("", text)


class HFLocalEngine:
    """Load one pinned base plus adapter and return a trace for every sequence."""

    def __init__(
        self,
        *,
        base_model_id: str,
        base_model_revision: str,
        adapter_id: str,
        adapter_revision: str,
        load_in_4bit: bool = False,
        keep_no_think_prefill: bool = True,
        force_json_array_prefix: bool = False,
        use_no_think_soft_switch: bool = False,
        stopping_enabled: bool = True,
    ) -> None:
        self.base_model_id = base_model_id
        self.base_model_revision = base_model_revision
        self.adapter_id = adapter_id
        self.adapter_revision = adapter_revision
        self.load_in_4bit = load_in_4bit
        self.keep_no_think_prefill = keep_no_think_prefill
        self.force_json_array_prefix = force_json_array_prefix
        self.use_no_think_soft_switch = use_no_think_soft_switch
        self.stopping_enabled = stopping_enabled
        self.loaded = False
        self.tokenizer = None
        self.model = None
        self.dtype_name = None

    def load(self) -> None:
        if self.loaded:
            return
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        token = os.environ.get("HF_TOKEN") or None
        common = {"token": token, "trust_remote_code": True}
        # Base and tuned paths must render byte-identical prompts. Adapter-hosted
        # tokenizer assets are deliberately excluded from matched inference.
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.base_model_id,
            revision=self.base_model_revision,
            **common,
        )
        if self.tokenizer.pad_token_id is None and self.tokenizer.eos_token_id is not None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        torch.backends.cuda.matmul.allow_tf32 = True
        try:
            torch.set_float32_matmul_precision("high")
        except Exception:
            pass
        dtype = (
            torch.bfloat16
            if torch.cuda.is_available() and torch.cuda.get_device_capability(0)[0] >= 8
            else torch.float16
        )
        self.dtype_name = str(dtype)
        model_kwargs = {"device_map": "auto", "torch_dtype": dtype, **common}
        if self.load_in_4bit:
            from transformers import BitsAndBytesConfig

            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=dtype,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
        print("loading base:", self.base_model_id, "@", self.base_model_revision)
        base = AutoModelForCausalLM.from_pretrained(
            self.base_model_id,
            revision=self.base_model_revision,
            **model_kwargs,
        )
        print("attaching adapter:", self.adapter_id, "@", self.adapter_revision)
        self.model = PeftModel.from_pretrained(
            base,
            self.adapter_id,
            revision=self.adapter_revision,
            token=token,
        )
        self.model.eval()
        self.loaded = True
        print("loaded model")

    def render_prompt(self, system: str, user: str, *, think: bool = False) -> str:
        self.load()
        if not think and self.use_no_think_soft_switch and "/no_think" not in user:
            user = user.rstrip() + "\n\n/no_think"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            rendered = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=think,
            )
        except TypeError:
            rendered = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        if not think and not self.keep_no_think_prefill:
            rendered = strip_empty_think_block(rendered)
        return rendered

    @staticmethod
    def _runtime_classes(torch):
        from transformers import LogitsProcessor, StoppingCriteria

        class PerRowSeededSampler(LogitsProcessor):
            """Apply top-p sampling with one independent generator per batch row."""

            def __init__(self, generators, temperature: float, top_p: float) -> None:
                self.generators = generators
                self.temperature = temperature
                self.top_p = top_p

            def __call__(self, input_ids, scores):
                scaled = scores / self.temperature
                sorted_scores, sorted_indices = torch.sort(scaled, descending=True, dim=-1)
                probabilities = torch.softmax(sorted_scores, dim=-1)
                cumulative = torch.cumsum(probabilities, dim=-1)
                remove = cumulative > self.top_p
                remove[:, 1:] = remove[:, :-1].clone()
                remove[:, 0] = False
                sorted_scores = sorted_scores.masked_fill(remove, float("-inf"))
                probabilities = torch.softmax(sorted_scores, dim=-1)
                selected = []
                for row_idx, generator in enumerate(self.generators):
                    sampled_sorted = torch.multinomial(
                        probabilities[row_idx],
                        num_samples=1,
                        generator=generator,
                    )
                    selected.append(sorted_indices[row_idx, sampled_sorted])
                selected_ids = torch.cat(selected)
                forced = torch.full_like(scores, float("-inf"))
                forced.scatter_(1, selected_ids.unsqueeze(1), 0.0)
                return forced

        class StopAfterCompleteJsonArray(StoppingCriteria):
            def __init__(self, tokenizer, prompt_length: int, forced_prefix: str) -> None:
                self.tokenizer = tokenizer
                self.prompt_length = prompt_length
                self.forced_prefix = forced_prefix
                self.finished = None
                self.completion_lengths: dict[int, int] = {}

            def __call__(self, input_ids, scores, **kwargs):
                batch_size = input_ids.shape[0]
                if self.finished is None or len(self.finished) != batch_size:
                    self.finished = [False] * batch_size
                for row_idx in range(batch_size):
                    if self.finished[row_idx]:
                        continue
                    last_token = int(input_ids[row_idx, -1].item())
                    if "]" not in self.tokenizer.decode(
                        [last_token], skip_special_tokens=True
                    ):
                        continue
                    generated = self.forced_prefix + self.tokenizer.decode(
                        input_ids[row_idx, self.prompt_length :],
                        skip_special_tokens=True,
                    )
                    try:
                        parsed = json.loads(generated.strip())
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if isinstance(parsed, list):
                        self.finished[row_idx] = True
                        self.completion_lengths[row_idx] = (
                            input_ids.shape[1] - self.prompt_length
                        )
                return torch.tensor(
                    self.finished,
                    dtype=torch.bool,
                    device=input_ids.device,
                )

        return PerRowSeededSampler, StopAfterCompleteJsonArray

    def generate_repetitions(
        self,
        system: str,
        user: str,
        *,
        tuned: bool,
        seeds: Iterable[int],
        temperature: float = 0.2,
        max_new_tokens: int = 768,
        top_p: float = 0.95,
    ) -> list[dict]:
        import torch
        from transformers import LogitsProcessorList, StoppingCriteriaList

        seeds = [int(seed) for seed in seeds]
        if not seeds:
            return []
        self.load()
        prompt_text = self.render_prompt(system, user, think=False)
        forced_prefix = "[" if self.force_json_array_prefix else ""
        prompt_text = prompt_text.rstrip() + forced_prefix
        device = next(self.model.parameters()).device
        encoded = self.tokenizer(prompt_text, return_tensors="pt").to(device)
        prompt_length = int(encoded["input_ids"].shape[-1])
        repetitions = len(seeds)
        inputs = {
            key: value.repeat(repetitions, 1)
            for key, value in encoded.items()
        }
        generators = [
            torch.Generator(device=device).manual_seed(seed)
            for seed in seeds
        ]
        do_sample = temperature is not None and float(temperature) > 0
        PerRowSeededSampler, StopAfterCompleteJsonArray = self._runtime_classes(torch)
        logits_processors = LogitsProcessorList()
        if do_sample:
            logits_processors.append(
                PerRowSeededSampler(generators, float(temperature), float(top_p))
            )
        stopper = StopAfterCompleteJsonArray(
            self.tokenizer,
            prompt_length,
            forced_prefix,
        )
        stopping_criteria = (
            StoppingCriteriaList([stopper])
            if self.stopping_enabled
            else StoppingCriteriaList()
        )
        pad_token_id = (
            self.tokenizer.pad_token_id
            if self.tokenizer.pad_token_id is not None
            else self.tokenizer.eos_token_id
        )
        generation_kwargs = {
            "max_new_tokens": max_new_tokens,
            # Sampling is performed by the per-row processor so generation can
            # remain batched without shared RNG state.
            "do_sample": False,
            "use_cache": True,
            "pad_token_id": pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
            "logits_processor": logits_processors,
            "stopping_criteria": stopping_criteria,
            "return_dict_in_generate": True,
        }

        if torch.cuda.is_available():
            torch.cuda.synchronize()
        started = time.time()
        with torch.inference_mode():
            if tuned:
                generated = self.model.generate(**inputs, **generation_kwargs)
            else:
                with self.model.disable_adapter():
                    generated = self.model.generate(**inputs, **generation_kwargs)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        elapsed = max(time.time() - started, 1e-6)

        traces = []
        eos_token_id = self.tokenizer.eos_token_id
        for row_idx, sequence in enumerate(generated.sequences):
            new_tokens = sequence[prompt_length:]
            if row_idx in stopper.completion_lengths:
                generated_token_count = stopper.completion_lengths[row_idx]
                finish_reason = "json_stop"
            else:
                token_ids = new_tokens.tolist()
                eos_index = token_ids.index(eos_token_id) if eos_token_id in token_ids else None
                if eos_index is not None:
                    generated_token_count = eos_index + 1
                    finish_reason = "eos"
                elif len(token_ids) >= max_new_tokens:
                    generated_token_count = max_new_tokens
                    finish_reason = "max_new_tokens"
                else:
                    generated_token_count = len(token_ids)
                    finish_reason = "unknown"
            used_tokens = new_tokens[:generated_token_count]
            raw = forced_prefix + self.tokenizer.decode(
                used_tokens,
                skip_special_tokens=True,
            ).strip()
            traces.append({
                "raw": raw,
                "seed": seeds[row_idx],
                "generated_token_count": int(generated_token_count),
                "prompt_token_count": prompt_length,
                "finish_reason": finish_reason,
                "rendered_prompt_sha256": hashlib.sha256(
                    prompt_text.encode("utf-8")
                ).hexdigest(),
            })
        total_generated = sum(trace["generated_token_count"] for trace in traces)
        print(
            f"gen_stats tuned={tuned} batch={repetitions} "
            f"prompt_tok={prompt_length} generated_tok={total_generated} "
            f"aggregate_tok_s={total_generated / elapsed:.1f}"
        )
        return traces

    def generate(
        self,
        system: str,
        user: str,
        *,
        tuned: bool,
        seed: int,
        temperature: float = 0.2,
        max_new_tokens: int = 768,
    ) -> dict:
        return self.generate_repetitions(
            system,
            user,
            tuned=tuned,
            seeds=[seed],
            temperature=temperature,
            max_new_tokens=max_new_tokens,
        )[0]
