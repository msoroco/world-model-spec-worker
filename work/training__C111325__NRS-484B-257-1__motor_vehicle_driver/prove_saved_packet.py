"""Exercise saved-source byte binding with disposable diagnostic packets."""

import hashlib
import json
import tempfile
from pathlib import Path

from measure_saved_packet import inspect
from measure_statutory import SOURCE_NAMES
from prove_statutory_measurement import packet
from stop_yield_scene import CASES


def rejects(root, case, fragment):
    try:
        inspect(root, case)
    except ValueError as error:
        if fragment not in str(error):
            raise AssertionError(str(error)) from error
        return
    raise AssertionError("Invalid source packet passed")


def write_packet(root, slug):
    context, rows = packet(slug)
    source_dir = root / "source"
    source_dir.mkdir()
    source_files = {}
    for name in SOURCE_NAMES:
        path = source_dir / (name + ".json")
        path.write_text(json.dumps({"synthetic_diagnostic": True, "name": name}) + "\n")
        context[name + "_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        source_files[name] = "source/" + path.name
    context["source_files"] = source_files
    (root / "stop_yield_context.json").write_text(json.dumps(context, indent=2) + "\n")
    (root / "stop_yield_motion.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    return context, source_dir


def main():
    repo = Path(__file__).resolve()
    while not (repo / "batch.json").is_file():
        repo = repo.parent
    scratch = repo / ".runtime-work" / "nrs257-saved-packet-tests"
    scratch.mkdir(parents=True, exist_ok=True)
    case = "training__C111325__NRS-484B-257-1__motor_vehicle_driver__complete_stop_then_yield"
    for slug in sorted(CASES - {"complete_stop_then_yield"}):
        with tempfile.TemporaryDirectory(prefix="packet-", dir=scratch) as directory:
            root = Path(directory)
            context, _ = write_packet(root, slug)
            observed = inspect(root, context["case_id"])
            assert observed["sample_count"] == 600 and observed["legal_verdict"] is None
    with tempfile.TemporaryDirectory(prefix="packet-", dir=scratch) as directory:
        root = Path(directory)
        context, source_dir = write_packet(root, "complete_stop_then_yield")
        observed = inspect(root, case)
        assert observed["packet_sources"]["source_files"]["map"] == context["map_sha256"]
        assert observed["legal_verdict"] is None and observed["sample_count"] == 600
        (source_dir / "sign.json").write_text("changed source\n")
        rejects(root, case, "SHA-256 differs")
        (source_dir / "sign.json").write_text(json.dumps({"synthetic_diagnostic": True, "name": "sign"}) + "\n")
        (source_dir / "through_body.json").unlink()
        rejects(root, case, "source file missing")
        (source_dir / "through_body.json").write_text(json.dumps({"synthetic_diagnostic": True, "name": "through_body"}) + "\n")
        rejects(root, case + "__wrong", "Exact case")
        context["source_files"]["sign"] = "../../batch.json"
        (root / "stop_yield_context.json").write_text(json.dumps(context, indent=2) + "\n")
        rejects(root, case, "outside attempt")
    print("twelve saved packet byte bindings and four missing/changed/wrong-case/path negatives passed")


if __name__ == "__main__":
    main()
