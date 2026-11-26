"""Bind tested independent audit commands to exact selected cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "execution-manifest.json"
CHECKS = ("native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    script = ROOT / "native/delivery_audit.py"
    for entry in manifest["cases"]:
        case = entry["case_id"]
        tag = case.rsplit("_", 1)[-1]
        positive = ROOT / ("delivery-" + tag + "-positive.log")
        negative = ROOT / ("delivery-" + tag + "-negative.log")
        if not (positive.is_file() and negative.is_file()):
            raise ValueError("Independent audit CPU logs missing")
        expected = "Original source inventory incomplete"
        if expected not in negative.read_text():
            raise ValueError("Missing-source negative did not reject")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-train"], "checks": list(CHECKS),
            "script": "native/delivery_audit.py", "script_sha256": sha(script),
            "command": ".venv-cpu/bin/python work/" + ROOT.name +
                "/native/delivery_audit.py --case " + case +
                " --attempt $ATTEMPT --review $INDEPENDENT_REVIEW",
            "test_exit_code": 0, "test_log": positive.name,
            "test_log_sha256": sha(positive),
            "negative_command": ".venv-cpu/bin/python work/" + ROOT.name +
                "/native/delivery_audit.py --case " + case +
                " --attempt $DIAGNOSTIC_ATTEMPT --review $DIAGNOSTIC_MISSING_SOURCE_REVIEW --structure-only",
            "negative_exit_code": 1, "negative_expected_error": expected,
            "negative_log": negative.name, "negative_log_sha256": sha(negative)}
        entry["delivery_readiness"] = "cpu_prepared_original_pixel_review_pending"
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": len(manifest["cases"]), "manifest_sha256": sha(MANIFEST)}))


if __name__ == "__main__":
    main()
