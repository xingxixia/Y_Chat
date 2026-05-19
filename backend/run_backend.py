from __future__ import annotations

import uvicorn

from y_chat.config import backend_host, backend_port


if __name__ == "__main__":
    uvicorn.run(
        "y_chat.main:app",
        host=backend_host(),
        port=backend_port(),
        reload=True,
    )
