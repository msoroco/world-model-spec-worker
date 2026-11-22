"""Reject a post-materialization OpenDRIVE change for each exact case."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from bus_route import ROUTES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def main():
    for kind in ROUTES:
        materialized = REPO / ".runtime-work" / "c147332-offline-v9" / kind / "primary"
        if not materialized.is_dir():
            raise ValueError("positive offline materialization missing: " + kind)
        road = materialized / "road.xodr"
        original = road.read_text()
        try:
            road.write_text(original.replace('a="3.6"', 'a="3.7"', 1))
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run([sys.executable, "runner.py", "--check"],
                                    cwd=materialized, env=env, capture_output=True,
                                    text=True, timeout=30)
            if result.returncode == 0 or "map source differs" not in result.stderr:
                raise ValueError("changed map not rejected: " + kind + " " + result.stderr)
            print(json.dumps({"case_id": ASSIGNMENT + "__" + kind,
                              "changed_map_rejected": True, "exit_code": result.returncode}))
        finally:
            road.write_text(original)


if __name__ == "__main__":
    main()
