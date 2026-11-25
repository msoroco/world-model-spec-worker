"""Check selected electric comparison source rows without legal inference."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIELDS = ("sign_id", "machine_class", "road_id", "approach_lane_id")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    results = []
    for machine in ("electric_bicycle", "electric_scooter"):
        sources = {}
        rows = {}
        for behavior in ("obey", "turn", "dismount"):
            path = ROOT / "electric-drafts" / f"{machine}_{behavior}" / "rider_native_samples.jsonl"
            values = [json.loads(line) for line in path.read_text().splitlines()]
            if len(values) != 600 or [row["frame"] for row in values] != list(range(600)):
                raise ValueError("Electric comparison requires 600 ordered source frames")
            sources[behavior] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}
            rows[behavior] = values
        signatures = [tuple(row[field] for field in FIELDS)
                      for values in rows.values() for row in values]
        if len(set(signatures)) != 1 or signatures[0][1] != machine:
            raise ValueError("Electric comparison fixed source fields changed")
        obey_turn = [row for row in rows["obey"] if row["u_turn_active"]]
        turn_turn = [row for row in rows["turn"] if row["u_turn_active"]]
        walk_turn = [row for row in rows["dismount"] if row["u_turn_active"]]
        dismounted = [row for row in rows["dismount"] if not row["mounted"]]
        if (obey_turn or not turn_turn or not walk_turn or not dismounted or
                not all(row["mounted"] for row in turn_turn) or
                not all(row["walking_machine"] and not row["mounted"] for row in walk_turn) or
                min(row["frame"] for row in dismounted) >= min(row["frame"] for row in walk_turn)):
            raise ValueError("Electric requested-behavior comparison failed")
        results.append({"machine_class": machine, "sources": sources,
                        "fixed_source_fields": list(FIELDS),
                        "obey_turn_frames": len(obey_turn),
                        "mounted_turn_frames": len(turn_turn),
                        "dismounted_turn_frames": len(walk_turn),
                        "dismount_frame": min(row["frame"] for row in dismounted),
                        "first_dismounted_turn_frame": min(row["frame"] for row in walk_turn),
                        "passed": True})
    output = ROOT / "electric-drafts/comparison-cpu-audit.json"
    output.write_text(json.dumps({"format": "c104538-electric-comparison-source-audit-v1",
                                  "scope": "synthetic source behavior only",
                                  "physical_or_legal_acceptance_claimed": False,
                                  "comparisons": results}, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"comparisons": len(results), "sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
