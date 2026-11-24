"""Validate the exact canonical semantic chain against the current runtime."""
from __future__ import annotations

import json
import sys
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate


def main():
    assignment = json.loads((ROOT / 'inputs' / FOLDER.name / 'assignment.json').read_text())
    manifest = json.loads((FOLDER / 'execution-manifest.json').read_text())
    print(validate(FOLDER, assignment, manifest))


if __name__ == '__main__':
    main()
