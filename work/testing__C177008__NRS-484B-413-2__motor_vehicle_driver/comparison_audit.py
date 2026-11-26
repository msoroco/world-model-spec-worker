"""Independent exact comparison audit from saved signal source bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from signal_measure import measure, compare
from source_audit import audit as audit_source

ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(comparison_id: str, attempts: list[str | Path], *,
          diagnostic_fixture: bool = False) -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    selected = [item for item in plan["comparisons"] if item["comparison_id"] == comparison_id]
    if len(selected) != 1 or len(attempts) != len(selected[0]["case_ids"]):
        raise ValueError("selected comparison case count differs")
    measured = []
    configs = []
    for case_id, path in zip(selected[0]["case_ids"], attempts):
        root = Path(path)
        signal = root / "original-turn-signal.json"
        site = root / "original-site.json"
        acquisition = json.loads((root / "acquisition.json").read_text())
        diagnostic_path = root / "fixture-provenance.json"
        diagnostic = (diagnostic_path.is_file() and
                      json.loads(diagnostic_path.read_text()).get("diagnostic_fixture") is True)
        if diagnostic and not diagnostic_fixture:
            raise ValueError("diagnostic fixture rejected in production comparison")
        if not diagnostic_fixture:
            source_result = audit_source(root, case_id)
            if source_result.get("source_decode_passed") is not True:
                raise ValueError("original four-camera source audit failed")
        for name in ("original-turn-signal.json", "original-site.json"):
            if not diagnostic and acquisition.get(name, {}).get("sha256") != sha(root / name):
                raise ValueError("missing or stale original comparison source: " + name)
        packet = json.loads(signal.read_text())
        if packet.get("source_kind") != ("diagnostic_fixture" if diagnostic else "original_native"):
            raise ValueError("comparison source provenance differs")
        if packet.get("site_sha256") != sha(site):
            raise ValueError("fixed original site hash differs")
        config = json.loads((root / "config.json").read_text())
        if config.get("selected_case_id") != case_id:
            raise ValueError("selected comparison case identity differs")
        configs.append(config)
        measured.append(measure(signal, case_id))
    common = ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras",
              "course", "required_atoms", "source_packets")
    if any({key: config.get(key) for key in common} !=
           {key: configs[0].get(key) for key in common} for config in configs[1:]):
        raise ValueError("fixed comparison construction differs")
    result = compare(measured[0], measured[1], comparison_id,
                     measured[2] if len(measured) == 3 else None)
    return {"format": "worker-signal-comparison-audit", "comparison_id": comparison_id,
            "case_ids": selected[0]["case_ids"], "fixed_conditions": selected[0]["fixed_conditions"],
            "deliberate_differences": selected[0]["deliberate_differences"],
            "measurement_source_sha256": [item["source_sha256"] for item in measured],
            "measured_continuous_ft": [item["continuous_distance_ft"] for item in measured],
            "software_measurement_passed": result["software_measurement_passed"],
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt", action="append", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true",
                        help="test-only: compare explicitly marked diagnostic fixtures")
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.attempt,
                           diagnostic_fixture=args.diagnostic_fixture), sort_keys=True))
