"""Source-bound route comparisons; engineering contrasts do not decide legal duty."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parent
AXES = {"alternate_choice": "route_choice", "alternate_restriction": "alternate_declared",
        "controlled_access": "controlled_access", "impediment_sweep": "ego_speed_mps",
        "route_possibility_sweep": "alternate_entry_lead_m"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(comparison_id: str, attempts: list[Path], *, diagnostic_fixture: bool = False) -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    selected = [row for row in plan["comparisons"] if row["comparison_id"] == comparison_id]
    if len(selected) != 1 or comparison_id not in AXES or len(attempts) != len(selected[0]["case_ids"]):
        raise ValueError("selected route comparison case count differs")
    axis = AXES[comparison_id]
    values = []
    source_hashes = []
    configs = []
    results = []
    for case_id, attempt in zip(selected[0]["case_ids"], attempts):
        root = Path(attempt)
        site = root / "original-site.json"
        packet = json.loads((root / "original-route-motion.json").read_text())
        if packet.get("case_id") != case_id or packet.get("site_sha256") != sha(site):
            raise ValueError("route site hash differs")
        diagnostic = packet.get("source_kind") == "diagnostic_fixture"
        if diagnostic and not diagnostic_fixture:
            raise ValueError("diagnostic fixture rejected in original route comparison")
        if not diagnostic and packet.get("source_kind") != "original_native":
            raise ValueError("original route source kind missing")
        config = json.loads((root / "config.json").read_text())
        if config.get("selected_case_id") != case_id:
            raise ValueError("route comparison exact case differs")
        rows = packet["samples"]
        if not rows or any(row.get("ego_id") != rows[0].get("ego_id") or
                           row.get("follower_id") != rows[0].get("follower_id") for row in rows):
            raise ValueError("route comparison participant identity missing")
        target = config["case"]["target"]
        values.append(target[axis])
        source_hashes.append(sha(root / "original-route-motion.json"))
        configs.append(config)
        results.append(json.loads((root / "analysis-report.json").read_text()))
    fixed = ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras",
             "required_atoms", "source_packets")
    if any({name: config[name] for name in fixed} != {name: configs[0][name] for name in fixed}
           for config in configs[1:]):
        raise ValueError("fixed route comparison capture contract differs")
    targets = [config["case"]["target"] for config in configs]
    if any({name: value for name, value in target.items() if name != axis} !=
           {name: value for name, value in targets[0].items() if name != axis}
           for target in targets[1:]):
        raise ValueError("route comparison changed a non-axis control")
    if len(set(values)) != len(values):
        raise ValueError("route comparison axis stations not distinct")
    measured = [result["measurements"] for result in results]
    return {"format": "worker-route-comparison-audit", "comparison_id": comparison_id,
            "case_ids": selected[0]["case_ids"], "fixed_conditions": selected[0]["fixed_conditions"],
            "deliberate_differences": selected[0]["deliberate_differences"],
            "axis": axis, "requested_values": values,
            "observed_route": [item["alternate_route_measurement"]["value"]["terminal_actual_route"]
                               for item in measured],
            "observed_mean_ego_speed_mps": [item["following_motion_measurement"]["value"]["mean_ego_speed_mps"]
                                            for item in measured],
            "source_sha256": source_hashes, "software_measurement_passed": True,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", choices=tuple(AXES), required=True)
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh route comparison output required")
    result = audit(args.comparison, args.attempt,
                   diagnostic_fixture=args.diagnostic_fixture)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
