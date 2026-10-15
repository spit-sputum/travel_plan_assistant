"""长期记忆的嵌入（Embedding）函数。

原则：**优先使用包内自带的本地模型，全程离线，不向 HuggingFace 下载任何文件**，
这样把程序包发给别人时，对方只需 `pip install` 依赖即可直接运行。
若本地模型目录被误删，则自动退化为确定性的哈希嵌入（纯标准库实现），
保证长期记忆功能依然可用。
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from travel_plan_agent.memory.paths import EMBEDDING_DIM, embedding_model_dir

logger = logging.getLogger(__name__)


class HashEmbeddingFunction:
    """无依赖兜底嵌入：字符 n-gram 哈希 + L2 归一化（语义较弱，但保证离线可用）。"""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    # chroma 通过方法签名识别 EmbeddingFunction 协议
    def __call__(self, input: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in input]

    def name(self) -> str:  # chroma >= 1.5 用于持久化 embedding function 配置
        return "travel_plan_agent_hash"

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> HashEmbeddingFunction:
        return HashEmbeddingFunction(dim=int(config.get("dim", EMBEDDING_DIM)))

    def get_config(self) -> dict[str, Any]:
        return {"dim": self.dim}

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> list[str]:
        return ["cosine", "l2", "ip"]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        tokens = re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE)
        grams = list(tokens)
        for i in range(len(tokens) - 1):
            grams.append(tokens[i] + tokens[i + 1])
        if not grams:
            grams = [""]
        for gram in grams:
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            vector[0] = 1.0
            return vector
        return [v / norm for v in vector]


@lru_cache(maxsize=1)
def get_embedding_function() -> Any:
    """返回可用的嵌入函数：本地模型优先，失败则用哈希兜底。"""
    model_dir = embedding_model_dir()
    if model_dir.is_dir():
        try:
            from chromadb.utils.embedding_functions import (
                SentenceTransformerEmbeddingFunction,
            )

            return SentenceTransformerEmbeddingFunction(
                model_name=str(model_dir),
                device="cpu",
                normalize_embeddings=True,
            )
        except Exception as exc:  # pragma: no cover - 依赖环境相关
            logger.warning("本地嵌入模型加载失败（%s），退化为哈希嵌入。", exc)
    else:
        logger.warning("未找到本地模型目录 %s，使用哈希嵌入兜底。", model_dir)
    return HashEmbeddingFunction()


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """便捷函数：直接得到文本向量（调试/测试用）。"""
    return list(get_embedding_function()(list(texts)))
