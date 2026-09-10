"""Best-effort per-container daily request cap for the public demo.

Lambda containers are stateless across cold starts, so this bounds a single
warm container; the hard bound is the function's reserved concurrency. Once
the cap is hit for the current UTC day, /ask returns 429.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class DailyCapMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, cap: int, path: str = "/ask") -> None:
        super().__init__(app)
        self._cap = cap
        self._path = path
        self._day = -1
        self._count = 0

    async def dispatch(self, request, call_next):
        if request.url.path == self._path:
            today = int(time.time() // 86400)
            if today != self._day:
                self._day, self._count = today, 0
            if self._count >= self._cap:
                return JSONResponse(
                    {"error": "daily demo limit reached — try again tomorrow"},
                    status_code=429,
                )
            self._count += 1
        return await call_next(request)
