"""Select speed constructions only after current CPU receipts bind."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    primary_path = HERE / "execution-manifest.json"
    speed_path = HERE / "speed-sweep-manifest.draft.json"
    primary = json.loads(primary_path.read_text())
    speed = json.loads(speed_path.read_text())
    comparison = json.loads((HERE / "cpu-speed-comparison-diagnostics.json").read_text())
    if len(primary["cases"]) != 4 or len(speed["cases"]) != 3:
        raise ValueError("expected four selected and three staged cases")
    if comparison.get("diagnostic_as_original_rejected") is not True or \
            comparison.get("realized_original_difference_claimed") is not False:
        raise ValueError("independent comparison proof missing")
    if set(comparison["case_ids"]) != {row["case_id"] for row in speed["cases"]}:
        raise ValueError("speed comparison case identity differs")
    for row in speed["cases"]:
        if sha(HERE / row["construction"]) != row["construction_sha256"]:
            raise ValueError("primary construction hash differs")
        if sha(HERE / row["candidates"][0]["construction"]) != row["candidates"][0]["construction_sha256"]:
            raise ValueError("fallback construction hash differs")
        for candidate in (row, row["candidates"][0]):
            offline = candidate["offline"]
            compatibility = candidate["compatibility"]
            if offline["exit_code"] != 0 or sha(HERE / offline["log"]) != offline["log_sha256"]:
                raise ValueError("offline receipt differs")
            if sha(HERE / compatibility["receipt"]) != compatibility["sha256"] or \
                    json.loads((HERE / compatibility["receipt"]).read_text())["passed"] is not True:
                raise ValueError("compatibility receipt differs")
        if sha(HERE / row["saved_diagnostic"]["receipt"]) != row["saved_diagnostic"]["sha256"]:
            raise ValueError("saved receipt differs")
        delivery = row["delivery_acceptance"]
        if sha(HERE / delivery["test_log"]) != delivery["test_log_sha256"] or \
                sha(HERE / delivery["negative_log"]) != delivery["negative_log_sha256"]:
            raise ValueError("delivery audit logs differ")
    primary["cases"].extend(speed["cases"])
    primary_path.write_text(json.dumps(primary, indent=2, sort_keys=True) + "\n")
    print("selected seven exact CPU-proven constructions; original acceptance unresolved")


if __name__ == "__main__":
    main()
