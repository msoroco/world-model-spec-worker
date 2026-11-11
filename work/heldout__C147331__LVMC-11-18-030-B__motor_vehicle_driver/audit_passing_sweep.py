"""Check exact passing sweep controls and retained diagnostic measurement links."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from audit_saved_comparisons import load_packet, version_from_proof

HERE = Path(__file__).resolve().parent
POINTS = {"passing_excursion-0000": .4,
          "passing_excursion-0001": .6,
          "passing_excursion-0002": .8}


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = read(HERE / "execution-manifest.json")
    saved = {row["case_id"]: row for row in read(HERE / "delivery-saved-proofs.json")["cases"]}
    source = {row["case_id"]: row for row in read(HERE / "delivery-source-audit-proofs.json")["cases"]}
    rows, fixed = [], None
    for suffix, fraction in POINTS.items():
        case = manifest["assignment_id"] + "__" + suffix
        entry = next(row for row in manifest["cases"] if row["case_id"] == case)
        construction = read(HERE / entry["construction"])
        if digest(HERE / entry["construction"]) != entry["construction_sha256"]:
            raise ValueError("Sweep construction hash changed")
        config = json.loads(next(row["content"] for row in construction["files"]
                                 if row["path"] == "config.json"))
        if config["engineering"].get("crossing_fraction") != fraction:
            raise ValueError("Exact sweep path control differs")
        normalized = json.loads(json.dumps(config))
        normalized.pop("selected_case_id")
        normalized["case"].pop("case_id")
        normalized["engineering"].pop("crossing_fraction")
        if fixed is None:
            fixed = normalized
        elif normalized != fixed:
            raise ValueError("Sweep changed a fixed construction field")
        packet = load_packet(version_from_proof(saved[case]), case)
        audit = source[case]
        if (audit["receipt_sha256"] != digest(HERE / audit["receipt"])
                or packet["source_sha256"] != read(HERE / audit["receipt"])["source_hashes"]["marked_lane_sources.jsonl"]):
            raise ValueError("Sweep source audit lost original-source binding")
        rows.append({"case_id": case, "requested_crossing_fraction": fraction,
                     "construction_sha256": entry["construction_sha256"],
                     "saved_source_sha256": packet["source_sha256"],
                     "minimum_diagnostic_clearance_m": min(
                         row["minimum_corner_clearance_m"] for row in packet["frames"]),
                     "source_audit_sha256": audit["receipt_sha256"]})
    report = {"format": "worker-passing-sweep-construction-audit",
              "comparison_id": "passing_excursion_sweep", "passed": True,
              "fixed_construction_fields_sha256": sha256(json.dumps(
                  fixed, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
              "cases": rows, "diagnostic_fixture_only": True,
              "physical_clearance_trend_claimed": False,
              "legal_exception_decided": False}
    (HERE / "delivery-passing-sweep-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Audited", len(rows), "exact passing sweep constructions and source links")


if __name__ == "__main__":
    main()
