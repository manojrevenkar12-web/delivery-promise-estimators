"""Print the day index the next training run trains through: the day after the last day in the lake."""
from __future__ import annotations

import json
import os
from pathlib import Path


def next_day(lake: Path) -> int:
    meta = json.loads((lake / "meta.json").read_text())
    return max(int(d) for d in meta["days"]) + 1


if __name__ == "__main__":
    print(next_day(Path(os.environ.get("DPE_LAKE", "data/lake"))))
