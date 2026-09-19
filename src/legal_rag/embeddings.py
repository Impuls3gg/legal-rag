"""Эмбеддинги через transformers: модель грузится в процесс, без внешнего сервера."""
from __future__ import annotations

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from .config import settings


class HFEmbedder:
    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self.device = device or settings.device
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name).to(self.device).eval()

    @property
    def dim(self) -> int:
        return self.model.config.hidden_size

    @torch.inference_mode()
    def embed(self, texts: list[str]) -> np.ndarray:
        parts: list[np.ndarray] = []
        step = settings.embedding_batch_size
        for i in range(0, len(texts), step):
            batch = self.tokenizer(
                texts[i : i + step],
                padding=True,
                truncation=True,
                max_length=settings.embedding_max_tokens,
                return_tensors="pt",
            ).to(self.device)
            # Dense-эмбеддинг bge-m3 — нормализованный вектор [CLS]-токена.
            cls = self.model(**batch).last_hidden_state[:, 0]
            parts.append(torch.nn.functional.normalize(cls, dim=-1).float().cpu().numpy())
        return np.concatenate(parts).astype("float32")
