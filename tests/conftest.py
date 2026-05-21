from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
TEST_RUNTIME = ROOT / "runtime" / "pytest"

os.environ.setdefault("Y_CHAT_RUNTIME_DIR", str(TEST_RUNTIME))

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
