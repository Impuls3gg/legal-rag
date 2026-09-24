"""Генерация ответа через transformers (Qwen2.5-Instruct или другая chat-модель)."""
from __future__ import annotations

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .config import resolve_device, settings
from .models import SearchResult

_SYSTEM_PROMPT = (
    "Ты — юридический ассистент, который отвечает СТРОГО на основе "
    "предоставленных фрагментов законодательства РФ. Если в контексте нет "
    "ответа — так и скажи, не придумывай нормы. В конце каждого утверждения "
    "указывай ссылку на источник в формате [название акта, ст. N]."
)


class HFLLM:
    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or settings.llm_model
        self.device = device or resolve_device()
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        # fp16 вдвое экономит память относительно fp32: для 1.5B это 3 вместо
        # 6 ГБ. Не bf16: GTX 16xx / RTX 20xx (Turing, sm_75) его аппаратно не умеют.
        self.model = (
            AutoModelForCausalLM.from_pretrained(self.model_name, dtype=torch.float16)
            .to(self.device)
            .eval()
        )

    @torch.inference_mode()
    def answer(self, question: str, results: list[SearchResult]) -> str:
        context = "\n\n---\n\n".join(r.chunk.full_text() for r in results)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Контекст:\n{context}\n\nВопрос: {question}"},
        ]
        inputs = self.tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt", return_dict=True
        ).to(self.device)

        generate_kwargs = {"max_new_tokens": settings.llm_max_new_tokens}
        if settings.llm_temperature > 0:
            generate_kwargs.update(do_sample=True, temperature=settings.llm_temperature)
        else:
            generate_kwargs["do_sample"] = False

        output = self.model.generate(**inputs, **generate_kwargs)
        new_tokens = output[0, inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
