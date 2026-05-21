from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from PIL import ImageGrab


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--quality", type=int, default=70)
    parser.add_argument("--max-width", type=int, default=640)
    args = parser.parse_args()

    started = time.perf_counter()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    image = ImageGrab.grab()
    source_width, source_height = image.size
    if args.max_width > 0 and image.width > args.max_width:
        target_height = max(1, round(image.height * (args.max_width / image.width)))
        image = image.resize((args.max_width, target_height))

    quality = max(1, min(100, int(args.quality)))
    image.save(output, "JPEG", quality=quality)
    data = output.read_bytes()
    print(
        json.dumps(
            {
                "ok": True,
                "path": str(output),
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
                "width": image.width,
                "height": image.height,
                "source_display_width": source_width,
                "source_display_height": source_height,
                "capture_ms": round((time.perf_counter() - started) * 1000),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
