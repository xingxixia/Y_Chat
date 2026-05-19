from __future__ import annotations

import uvicorn

from test_atri.config import backend_host, backend_port


if __name__ == "__main__":
    uvicorn.run(
        "test_atri.main:app",
        host=backend_host(),
        port=backend_port(),
        reload=True,
    )
