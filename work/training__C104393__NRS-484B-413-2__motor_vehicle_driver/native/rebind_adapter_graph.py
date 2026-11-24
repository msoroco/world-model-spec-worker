"""Rebind source-shaped diagnostic graph paths to the current JSON adapter format.

This changes graph serialization references only. Motion, pixels and legal facts
remain synthetic diagnostics and are never presented as original observations.
"""

import argparse
import json
from pathlib import Path


def rebind(source: dict) -> dict:
    result = dict(source)
    result["graphs"] = [
        {**graph, "path": graph["path"].replace(".pkl", ".adapter.json")}
        for graph in source["graphs"]
    ]
    files = dict(source["files"])
    rows = []
    for line in files["capture/native/frames.jsonl"].splitlines():
        row = json.loads(line)
        row["base"] = row["base"].replace(".pkl", ".adapter.json")
        row["abstract"] = row["abstract"].replace(".pkl", ".adapter.json")
        row["adapter_graph"] = row["base"]
        rows.append(json.dumps(row, separators=(",", ":")))
    files["capture/native/frames.jsonl"] = "\n".join(rows) + "\n"
    result["files"] = files
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = rebind(json.loads(args.source.read_text()))
    args.output.write_text(json.dumps(result, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
