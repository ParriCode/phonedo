"""Import each Reader layer independently of the Linux CLI bootstrap."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "libs", ROOT / "apps/reader", ROOT / "apps/reader/core/python",
             ROOT / "apps/reader/server/python"):
    sys.path.insert(0, str(path))
