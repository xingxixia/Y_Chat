from __future__ import annotations

import os
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "runtime" / "models" / "hf"

MODELS = [
    (
        "vision_embedding",
        "openai/clip-vit-base-patch32",
        [
            "config.json",
            "merges.txt",
            "preprocessor_config.json",
            "pytorch_model.bin",
            "special_tokens_map.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.json",
        ],
    ),
    (
        "audio_asr",
        "Systran/faster-whisper-base",
        ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"],
    ),
    (
        "vision_vlm",
        "HuggingFaceTB/SmolVLM-256M-Instruct",
        [
            "*.json",
            "*.txt",
            "*.safetensors",
            "*.py",
        ],
    ),
    (
        "vision_vlm_qwen",
        "Qwen/Qwen2.5-VL-3B-Instruct",
        [
            "*.json",
            "*.txt",
            "*.safetensors",
            "*.py",
        ],
    ),
]

VISION_VLM_FILES = [
    "added_tokens.json",
    "chat_template.json",
    "config.json",
    "generation_config.json",
    "merges.txt",
    "model.safetensors",
    "preprocessor_config.json",
    "processor_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
]

VISION_VLM_QWEN_FILES = [
    "config.json",
    "generation_config.json",
    "merges.txt",
    "model.safetensors.index.json",
    "preprocessor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
    "model-00001-of-00002.safetensors",
    "model-00002-of-00002.safetensors",
]


def main() -> None:
    selected = set(sys.argv[1:])
    max_workers = int(os.environ.get("Y_CHAT_HF_MAX_WORKERS", "1"))
    os.environ.setdefault("HF_HOME", str(CACHE_DIR))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for kind, model_id, allow_patterns in MODELS:
        if selected and kind not in selected and model_id not in selected:
            continue
        print(f"[download:start] {kind} {model_id}", flush=True)
        print(f"[download:target] {CACHE_DIR / model_id.replace('/', '__')}", flush=True)
        print(f"[download:allow_patterns] {allow_patterns}", flush=True)
        print(f"[download:max_workers] {max_workers}", flush=True)
        if kind == "vision_vlm" and os.environ.get("Y_CHAT_HF_FILE_BY_FILE", "0") != "0":
            path = _download_files(model_id, VISION_VLM_FILES)
            print(f"[download:done] {kind} {model_id} -> {path}", flush=True)
            continue
        if kind == "vision_vlm_qwen" and os.environ.get("Y_CHAT_HF_FILE_BY_FILE", "1") != "0":
            path = _download_files(model_id, VISION_VLM_QWEN_FILES)
            print(f"[download:done] {kind} {model_id} -> {path}", flush=True)
            continue
        path = snapshot_download(
            repo_id=model_id,
            cache_dir=str(CACHE_DIR),
            local_dir=str(CACHE_DIR / model_id.replace("/", "__")),
            local_dir_use_symlinks=False,
            allow_patterns=allow_patterns,
            max_workers=max_workers,
            resume_download=True,
        )
        print(f"[download:done] {kind} {model_id} -> {path}", flush=True)
    print("[download:all_done]", flush=True)


def _download_files(model_id: str, filenames: list[str]) -> str:
    local_dir = CACHE_DIR / model_id.replace("/", "__")
    local_dir.mkdir(parents=True, exist_ok=True)
    for index, filename in enumerate(filenames, start=1):
        print(f"[download:file:start] {index}/{len(filenames)} {filename}", flush=True)
        path = hf_hub_download(
            repo_id=model_id,
            filename=filename,
            cache_dir=str(CACHE_DIR),
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        size = Path(path).stat().st_size if Path(path).exists() else 0
        print(f"[download:file:done] {filename} bytes={size}", flush=True)
    return str(local_dir)


if __name__ == "__main__":
    main()
