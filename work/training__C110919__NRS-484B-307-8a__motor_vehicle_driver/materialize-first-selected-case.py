"""Materialize the first exact selected package as the root CPU entrypoint."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((HERE / "update058-selected-ordinary-manifest.json").read_text())
    entry = manifest["cases"][0]
    if entry["case_id"] != HERE.name + "__reference":
        raise ValueError("First selected exact case changed")
    construction = json.loads((HERE / entry["construction"]).read_text())
    for item in construction["files"]:
        destination = HERE / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(item["content"])
    (HERE / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
    print(json.dumps({"root_case": entry["case_id"],
                      "materialized_files": len(construction["files"])}))


if __name__ == "__main__":
    main()
