"""下载长期记忆所需的本地嵌入模型（通常只需运行一次）。

用法（在仓库根目录）：
    python scripts/download_model.py              # 从 HuggingFace 官方下载
    python scripts/download_model.py --mirror     # 使用国内镜像 hf-mirror.com
    python scripts/download_model.py --force      # 已存在也重新下载

说明：
- 只下载"运行必需"的文件（约 470MB），不含 onnx / openvino / tensorflow 等冗余格式
  （完整仓库约 4.4GB，本项目用不到）。
- 纯标准库实现，无需安装任何额外依赖。
- **不下载也能运行**：程序找不到模型目录时会自动退化为哈希嵌入
  （长期记忆仍可用，只是语义检索效果较弱）。
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MIRROR_HOST = "hf-mirror.com"
OFFICIAL_HOST = "huggingface.co"

# 模型目录：<仓库根>/travel_plan_agent/paraphrase-multilingual-MiniLM-L12-v2
TARGET_DIR = (
    Path(__file__).resolve().parents[1]
    / "travel_plan_agent"
    / "paraphrase-multilingual-MiniLM-L12-v2"
)

# sentence-transformers 用 PyTorch 后端，只需 safetensors 权重 + 配置 + 分词器
FILES = [
    "config.json",
    "config_sentence_transformers.json",
    "configuration.json",
    "modules.json",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "sentencepiece.bpe.model",
    "unigram.json",
    "model.safetensors",
    "1_Pooling/config.json",
]


def build_url(host: str, filename: str) -> str:
    return f"https://{host}/{REPO_ID}/resolve/main/{filename}"


def download_one(host: str, filename: str, force: bool) -> bool:
    """下载单个文件（带 .part 临时文件，中断不会留下半成品）。"""
    dest = TARGET_DIR / filename
    if dest.is_file() and dest.stat().st_size > 0 and not force:
        print(f"  [已存在] {filename}")
        return True

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    url = build_url(host, filename)
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310 - 固定 https
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with open(tmp, "wb") as fp:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    fp.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = done * 100 / total
                        sys.stdout.write(
                            f"\r  [下载中] {filename}  {pct:5.1f}%  "
                            f"({done / 1048576:.0f}/{total / 1048576:.0f} MB)"
                        )
                        sys.stdout.flush()
        tmp.replace(dest)
        size_mb = dest.stat().st_size / 1048576
        sys.stdout.write(
            f"\r  [完成]   {filename}  ({size_mb:.1f} MB)" + " " * 20 + "\n"
        )
        return True
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        tmp.unlink(missing_ok=True)
        sys.stdout.write("\n")
        print(f"  [失败]   {filename}: {exc}")
        return False


def check_model_loadable() -> bool:
    """下载后尝试真正加载一次，确保可用。"""
    try:
        from chromadb.utils.embedding_functions import (  # noqa: PLC0415
            SentenceTransformerEmbeddingFunction,
        )

        fn = SentenceTransformerEmbeddingFunction(
            model_name=str(TARGET_DIR), device="cpu", normalize_embeddings=True
        )
        vector = fn(["测试 embedding 是否可用"])
        ok = bool(vector) and len(vector[0]) > 0
        print(f"\n[自检] 模型加载成功，向量维度 = {len(vector[0])}")
        return ok
    except ImportError:
        print("\n[自检] 未安装 chromadb/sentence-transformers，跳过加载测试。")
        print("       安装依赖后即可使用：pip install -r travel_plan_agent/requirements.txt")
        return True
    except Exception as exc:  # noqa: BLE001 - 自检失败只提醒，不影响下载结果
        print(f"\n[自检] 模型加载失败：{type(exc).__name__}: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="下载本地嵌入模型")
    parser.add_argument(
        "--mirror", action="store_true", help=f"使用国内镜像 {MIRROR_HOST}"
    )
    parser.add_argument("--force", action="store_true", help="已存在也重新下载")
    args = parser.parse_args()

    host = MIRROR_HOST if args.mirror else OFFICIAL_HOST
    print("嵌入模型下载")
    print(f"  来源：https://{host}/{REPO_ID}")
    print(f"  目标：{TARGET_DIR}")
    print(f"  文件：{len(FILES)} 个（约 470MB）\n")

    failed = [name for name in FILES if not download_one(host, name, args.force)]

    if failed:
        print(f"\n有 {len(failed)} 个文件下载失败：{', '.join(failed)}")
        print("可重试：python scripts/download_model.py --mirror")
        return 1

    print("\n全部文件下载完成。")
    check_model_loadable()
    if shutil.which("du") is None:  # Windows 下给个体积提示
        total = sum((TARGET_DIR / f).stat().st_size for f in FILES if (TARGET_DIR / f).is_file())
        print(f"模型目录占用：{total / 1048576:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
