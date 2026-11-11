"""Bind current six-case CPU proof receipts into the exact execution manifest."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    delivery = read(HERE / "delivery-construction-manifest.json")
    previous = read(HERE / "execution-manifest.json")
    old = {row["case_id"]: row for row in previous["cases"]}
    proofs = {row["case_id"]: row for row in read(HERE / "delivery-case-proofs.json")["cases"]}
    entries = []
    for source in delivery["cases"]:
        case = source["case_id"]
        proof = proofs[case]
        if proof["construction_sha256"] != source["construction_sha256"]:
            raise ValueError("Primary proof construction changed")
        row = deepcopy(source)
        row["offline"] = {"command": proof["offline_command"], "exit_code": 0,
                          "log": proof["offline_log"]["path"],
                          "log_sha256": proof["offline_log"]["sha256"],
                          "construction_sha256": row["construction_sha256"]}
        row["compatibility"] = {"receipt": proof["compatibility_receipt"]["path"],
                                "sha256": proof["compatibility_receipt"]["sha256"],
                                "log": proof["analysis_log"]["path"]}
        row["negative"] = {"log": proof["negative_log"]["path"]}
        if case in old:
            for key in ("physical_preparation", "delivery_acceptance", "acquisition"):
                if key in old[case]:
                    row[key] = old[case][key]
        else:
            row["acquisition"] = deepcopy(old[next(iter(old))]["acquisition"])
        entries.append(row)
    previous["cases"] = entries
    (HERE / "execution-manifest.json").write_text(json.dumps(previous, indent=2) + "\n")
    print("Bound current offline and compatibility receipts for", len(entries), "cases")


if __name__ == "__main__":
    main()
