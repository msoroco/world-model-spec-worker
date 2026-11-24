"""Read an original, sealed C111125 attempt without starting CARLA.

This entry point only measures evidence. It never assigns a legal outcome or
promotes a diagnostic fixture to a physically accepted recording.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent
ASSIGNMENT_ID = "testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator"
SUFFIXES = {
    "two_cycles_failed_detection", "one_cycle", "signal_changes",
    "no_prior_stop", "fails_to_yield",
}


class SavedAttemptError(ValueError):
    pass


def _load_module():
    spec = importlib.util.spec_from_file_location("c111125_signal_trial_saved", BASE / "signal_trial.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_ref(root: Path, ref: dict) -> dict:
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not isinstance(ref.get("sha256"), str):
        raise SavedAttemptError("missing hashed source reference")
    path = (root / ref["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise SavedAttemptError("source outside attempt or missing")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise SavedAttemptError("saved source hash mismatch")
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise SavedAttemptError("saved source JSON invalid") from exc


def process_saved(attempt_root: Path, authority_root: Path, site: dict,
                  case_id: str, *, allow_diagnostic: bool = False) -> dict:
    """Verify an exact sealed attempt and return unresolved original measurements.

    ``attempt.json`` is a capture-time receipt. Its packet is separately hashed,
    and that packet hashes the original Native, device, detector and geometry
    streams. The authority root holds the source-hashed site packet.
    """
    attempt_root = Path(attempt_root).resolve()
    authority_root = Path(authority_root).resolve()
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise SavedAttemptError("wrong assignment case")
    suffix = case_id[len(ASSIGNMENT_ID) + 2:]
    if suffix not in SUFFIXES:
        raise SavedAttemptError("unknown exact case")
    receipt_path = attempt_root / "attempt.json"
    if not receipt_path.is_file():
        raise SavedAttemptError("sealed attempt receipt missing")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise SavedAttemptError("attempt receipt JSON invalid") from exc
    if receipt.get("format") != "c111125-native-attempt-v1" or receipt.get("case_id") != case_id:
        raise SavedAttemptError("attempt format or case identity mismatch")
    if receipt.get("diagnostic_fixture") is True and not allow_diagnostic:
        raise SavedAttemptError("diagnostic fixture cannot establish delivery evidence")
    if receipt.get("native_exit_code") != 0 or not isinstance(receipt.get("actor_id"), int):
        raise SavedAttemptError("Native completion or actor readback missing")
    if receipt.get("observed_blueprint_id") != site.get("ego_blueprint_id"):
        raise SavedAttemptError("observed bicycle blueprint changed")
    signal_trial = _load_module()
    plan = signal_trial.construct_plan(site, authority_root, suffix)
    policy = receipt.get("policy_receipt")
    if not isinstance(policy, dict) or policy.get("device_sha256") != plan["device_sha256"] or policy.get("detector_sha256") != plan["detector_sha256"]:
        raise SavedAttemptError("capture policy source binding missing")
    packet = _read_ref(attempt_root, receipt.get("packet_ref"))
    if packet.get("case_suffix") != suffix:
        raise SavedAttemptError("packet case differs from sealed attempt")
    if packet.get("actor_id") != receipt["actor_id"] or packet.get("observed_blueprint_id") != receipt["observed_blueprint_id"]:
        raise SavedAttemptError("packet actor readback differs from receipt")
    if packet.get("policy_receipt") != policy:
        raise SavedAttemptError("packet policy differs from receipt")
    try:
        measurement = signal_trial.measure_attempt(packet, attempt_root, plan)
    except signal_trial.SourceError as exc:
        raise SavedAttemptError(str(exc)) from exc
    if receipt.get("frame_count") != measurement["duration_frames"]:
        raise SavedAttemptError("sealed frame count differs from original traces")
    return {
        "format": "c111125-saved-measurement-v1",
        "assignment_id": ASSIGNMENT_ID,
        "case_id": case_id,
        "attempt_receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "packet_sha256": receipt["packet_ref"]["sha256"],
        "diagnostic_fixture": receipt.get("diagnostic_fixture") is True,
        "measurement": measurement,
        "physical_acceptance": False,
        "legal_verdict": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure a sealed C111125 Native attempt")
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-diagnostic", action="store_true")
    args = parser.parse_args()
    try:
        site = json.loads(args.site.read_text(encoding="utf-8"))
        result = process_saved(args.attempt, args.authority_root, site, args.case_id,
                               allow_diagnostic=args.allow_diagnostic)
        if args.output.resolve().is_relative_to(args.attempt.resolve()):
            raise SavedAttemptError("measurement output must be separate from sealed attempt")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (SavedAttemptError, ValueError, OSError) as exc:
        parser.exit(2, "saved attempt rejected: " + str(exc) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
