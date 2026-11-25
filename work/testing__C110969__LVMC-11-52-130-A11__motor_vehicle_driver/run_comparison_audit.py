"""Audit seven independent original Native attempts against saved comparison sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import ASSIGNMENT, SUFFIXES, audit as audit_comparisons
from saved_delivery import audit as audit_original


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_original(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Comparison source must be a regular original file")
    return json.loads(path.read_text())


def run(attempts: dict[str, Path], output: Path, source_audit=audit_original) -> dict:
    if set(attempts) != set(SUFFIXES):
        raise ValueError("Seven independent exact attempts required")
    roots = {suffix: (path.parent if path.name == "attempt.json" else path).resolve()
             for suffix, path in attempts.items()}
    if len(set(roots.values())) != 7:
        raise ValueError("Each comparison case requires an independent attempt")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    packet = {"assignment_id": ASSIGNMENT, "cases": []}
    for suffix in SUFFIXES:
        root = roots[suffix]
        attempt = root / "attempt.json"
        source = source_audit(attempt, allow_diagnostic=False)
        case_id = ASSIGNMENT + "__" + suffix
        if source.get("case_id") != case_id or source.get("native_source") is not True or not source.get("original_pixels_decoded"):
            raise ValueError("Original Native source audit did not prove this exact case")
        measurement = _load_original(root / "comparison-measurement.json")
        context = _load_original(root / "comparison-context.json")
        observation = _load_original(root / "comparison-observation.json")
        if measurement.get("case_id") != case_id or context.get("case_id") != case_id:
            raise ValueError("Comparison source selects another case")
        if context.get("diagnostic_fixture") is not False:
            raise ValueError("Diagnostic comparison context rejected")
        original_hashes = {name: _sha(root / name) for name in
                           ("attempt.json", "comparison-measurement.json", "comparison-context.json", "comparison-observation.json")}
        case_dir = output / suffix
        case_dir.mkdir(parents=True, exist_ok=True)
        observation_path = case_dir / "observation.json"
        observation_path.write_text(json.dumps(observation, sort_keys=True) + "\n")
        context["observation_source"] = {"path": str(observation_path.relative_to(output)), "sha256": _sha(observation_path)}
        context["original_source_hashes"] = original_hashes
        measurement_path = case_dir / "measurement.json"
        context_path = case_dir / "context.json"
        measurement_path.write_text(json.dumps(measurement, sort_keys=True) + "\n")
        context_path.write_text(json.dumps(context, sort_keys=True) + "\n")
        packet["cases"].append({"case_id": case_id,
                                "measurement_source": {"path": str(measurement_path.relative_to(output)), "sha256": _sha(measurement_path)},
                                "context_source": {"path": str(context_path.relative_to(output)), "sha256": _sha(context_path)}})
    packet_path = output / "comparison-sources.json"
    packet_path.write_text(json.dumps(packet, indent=2) + "\n")
    receipt = audit_comparisons(packet_path)
    receipt["scope"] = "original Native source comparison; legal necessity and physical acceptance remain unresolved"
    receipt["packet_sha256"] = _sha(packet_path)
    (output / "comparison-audit.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for suffix in SUFFIXES:
        parser.add_argument("--" + suffix.replace("_", "-"), required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = run({suffix: getattr(args, suffix) for suffix in SUFFIXES}, args.output)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
