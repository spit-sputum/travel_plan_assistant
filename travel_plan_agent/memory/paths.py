"""记忆模块的路径与配置（集中定义，便于整体拷贝/分发）。

默认值都指向 travel_plan_agent/memory_data/，随包带走、免安装数据库软件。
需要改位置时，二选一：
1. 环境变量：SHORT_TERM_DB_PATH / LONG_TERM_DB_PATH / EMBEDDING_MODEL_PATH
2. 包内 .env 文件写入同名变量
"""

from __future__ import annotations

import os
from pathlib import Path

from travel_plan_agent.config import BASE_DIR

try:  # python-dotenv 随 pydantic-settings 安装，缺失也不影响功能
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env", override=False)
except Exception:
    pass

MEMORY_DATA_DIR = BASE_DIR / "memory_data"
DEFAULT_SHORT_TERM_DB = MEMORY_DATA_DIR / "short_term_memory.db"
DEFAULT_LONG_TERM_DIR = MEMORY_DATA_DIR / "long_term_memory"
DEFAULT_COLLECTION_NAME = "long_term_memory"
DEFAULT_MODEL_DIRNAME = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384


def _absolute(path) -> Path:
    """相对路径统一按包目录解析，保证换机器后行为一致。"""
    p = Path(path)
    return p if p.is_absolute() else BASE_DIR / p


def resolve_path(path) -> Path:
    """对外暴露：把用户传入的路径解析为绝对路径。"""
    return _absolute(path)


def short_term_db_path() -> Path:
    return _absolute(os.getenv("SHORT_TERM_DB_PATH", "") or DEFAULT_SHORT_TERM_DB)


def long_term_db_dir() -> Path:
    return _absolute(os.getenv("LONG_TERM_DB_PATH", "") or DEFAULT_LONG_TERM_DIR)


def long_term_collection_name() -> str:
    return os.getenv("LONG_TERM_COLLECTION_NAME", "") or DEFAULT_COLLECTION_NAME


def embedding_model_dir() -> Path:
    """本地嵌入模型目录：优先环境变量，其次包内自带模型（离线可用）。"""
    return _absolute(os.getenv("EMBEDDING_MODEL_PATH", "") or DEFAULT_MODEL_DIRNAME)
