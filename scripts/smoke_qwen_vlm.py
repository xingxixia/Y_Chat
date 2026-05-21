from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "runtime" / "models" / "hf" / "Qwen__Qwen2.5-VL-3B-Instruct"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a gated local Qwen VLM smoke test.")
    parser.add_argument("--image", required=True, help="Local image path used only for this gated smoke test.")
    parser.add_argument("--max-new-tokens", type=int, default=96)
    args = parser.parse_args()

    started = time.perf_counter()
    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"image not found: {image_path}")
    required = [
        "config.json",
        "model.safetensors.index.json",
        "model-00001-of-00002.safetensors",
        "model-00002-of-00002.safetensors",
        "tokenizer.json",
        "preprocessor_config.json",
    ]
    missing = [name for name in required if not (MODEL_DIR / name).exists()]
    if missing:
        raise SystemExit(f"missing qwen files: {', '.join(missing)}")

    print("[qwen-smoke] importing torch/transformers", flush=True)
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    print("[qwen-smoke] loading processor", flush=True)
    processor = AutoProcessor.from_pretrained(str(MODEL_DIR), local_files_only=True)

    kwargs = {"local_files_only": True, "device_map": "auto"}
    if torch.cuda.is_available():
        kwargs["torch_dtype"] = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    else:
        kwargs["torch_dtype"] = torch.float32
        kwargs["device_map"] = "cpu"

    print(f"[qwen-smoke] loading model kwargs={kwargs}", flush=True)
    load_started = time.perf_counter()
    model = AutoModelForImageTextToText.from_pretrained(str(MODEL_DIR), **kwargs)
    model.eval()
    load_elapsed = time.perf_counter() - load_started
    print(f"[qwen-smoke] model_loaded seconds={load_elapsed:.2f}", flush=True)

    prompt = (
        "What is visible in this screenshot? Describe the UI layout, windows, "
        "text areas, and any visible objects. Answer concisely."
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    with Image.open(image_path) as image:
        inputs = processor(text=[text], images=[image.convert("RGB")], return_tensors="pt")
    device = getattr(model, "device", None)
    if device is not None:
        inputs = {key: value.to(device) if hasattr(value, "to") else value for key, value in inputs.items()}

    print("[qwen-smoke] generating", flush=True)
    generate_started = time.perf_counter()
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
    generated = generated_ids[:, inputs["input_ids"].shape[1] :]
    content = processor.batch_decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
    generate_elapsed = time.perf_counter() - generate_started

    result = {
        "ok": True,
        "image": image_path.name,
        "model_dir": MODEL_DIR.name,
        "load_seconds": round(load_elapsed, 2),
        "generate_seconds": round(generate_elapsed, 2),
        "total_seconds": round(time.perf_counter() - started, 2),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_memory_allocated": int(torch.cuda.memory_allocated()) if torch.cuda.is_available() else 0,
        "cuda_memory_reserved": int(torch.cuda.memory_reserved()) if torch.cuda.is_available() else 0,
        "content": content.strip(),
    }
    print("[qwen-smoke:result]" + json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
