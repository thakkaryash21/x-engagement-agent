from __future__ import annotations

import uvicorn
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.api import app
from dashboard.file_store import DashboardStore


def main() -> None:
    store = DashboardStore()
    port = int(store.app_config.get("dashboard_port", "8787"))
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
