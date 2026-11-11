"""Independent CPU audit of retained C125714 source media and measurements."""
import hashlib
import json
import math
from pathlib import Path

from camera_setup import SIZES
from worker_exchange.media import audit as audit_video
from worker_exchange.measurement_contract import validate, verify_report

CAMERAS = tuple(name + ".mkv" for name in SIZES)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_delivery(attempt, package, expected_frames=1100, receipt_dir=None):
    attempt, package = Path(attempt), Path(package)
    if type(expected_frames) is not int or expected_frames != 1100:
        raise ValueError("Exact 1100-frame C125714 delivery duration required")
    mapping_path = attempt / "video_frames.jsonl"
    if not mapping_path.is_file():
        raise ValueError("Missing original video frame map")
    mapping = [json.loads(line) for line in mapping_path.read_text().splitlines() if line.strip()]
    if len(mapping) != expected_frames:
        raise ValueError("Full original frame-map duration required")
    previous_frame, previous_time = -1, float("-inf")
    for index, row in enumerate(mapping):
        frame, time = row.get("carla_frame"), row.get("time_s")
        if row.get("video_frame") != index or type(frame) is not int or frame <= previous_frame or type(time) not in (int, float) or not math.isfinite(time) or time <= previous_time:
            raise ValueError("Nonmonotone original video frame/time join")
        if index and abs(time - previous_time - 0.05) > 1e-3:
            raise ValueError("Original source frames are not 20 Hz")
        previous_frame, previous_time = frame, time
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id")
    if config.get("law_id") != "NRS-484B-250-1" or config.get("cell_id") != "C125714" or config.get("rate_hz") != 20 or config.get("duration_s") != 55:
        raise ValueError("Exact C125714 law, cell and duration required")
    plan = json.loads((package / "case-plan.json").read_text())
    contract = json.loads((package / "measurement-contract.json").read_text())
    validate(contract, plan["requirement_dispositions"],
             (package / "finalizer.py").read_text(), case_id)
    analysis_path = attempt / "analysis-report.json"
    analysis = json.loads(analysis_path.read_text())
    verified = verify_report(contract, analysis, attempt)
    if len(verified) != 5:
        raise ValueError("Five selected source-hashed measurements required")
    if receipt_dir is not None:
        receipt_dir = Path(receipt_dir)
        receipt_dir.mkdir(parents=True, exist_ok=True)
    for name in CAMERAS:
        if not (attempt / name).is_file():
            raise ValueError("Missing source camera: " + name)
    decodes = {}
    for index, name in enumerate(CAMERAS):
        path = attempt / name
        receipt = audit_video(path, expected_frames, mapping_sha256=_sha(mapping_path),
                              receipt=(receipt_dir / f"camera-{index}.json") if receipt_dir else None)
        if receipt["dimensions"] != list(SIZES[name.removesuffix(".mkv")]):
            raise ValueError("Source camera dimensions differ: " + name)
        decodes[name] = {"video_sha256": receipt["video_sha256"],
                         "decoded_frames": receipt["frames"]}
    return {"format": "worker-c125714-independent-delivery-audit",
            "case_id": case_id, "expected_frames": expected_frames,
            "original_frame_map_sha256": _sha(mapping_path),
            "analysis_sha256": _sha(analysis_path),
            "verified_measurements": sorted(verified),
            "source_decodes": decodes,
            "software_audit_passed": True,
            "physical_acceptance_claimed": False,
            "legal_conclusion": "unresolved"}
