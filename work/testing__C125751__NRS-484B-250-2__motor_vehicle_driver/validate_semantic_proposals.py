"""Recheck the source-hashed C125751 canonical stage chain without SQLite."""
import json
from pathlib import Path

from worker_exchange.semantic_delivery import validate


def main():
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    assignment = json.loads((repo / "inputs" / folder.name / "assignment.json").read_text())
    witness = json.loads((repo / "inputs" / folder.name / "witnesses.json").read_text())[0]["witness"]
    assignment["law"] = witness["law"]
    manifest = json.loads((folder / "diagnostic-execution-manifest.json").read_text())
    print(json.dumps(validate(folder, assignment, manifest), sort_keys=True))


if __name__ == "__main__":
    main()
