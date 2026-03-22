from __future__ import annotations

import os


# Keep regression tests isolated from the live local control-plane state.
os.environ["APP_ENV"] = "test"
os.environ["STATE_STORE_BACKEND"] = "memory"
