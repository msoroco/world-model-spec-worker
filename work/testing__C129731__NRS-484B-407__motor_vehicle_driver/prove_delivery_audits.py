"""Run full diagnostic delivery-auditor positive/negative CPU proofs per case."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess

from build_execution_manifest import CASES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")
EXPECTED = "Sealed original source changed: capture/evidence.jsonl"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return str(Path(path).relative_to(HERE))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v5")
    args = parser.parse_args()
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    for slug, *_ in CASES:
        case_id = next(e["case_id"] for e in manifest["cases"]
                       if e["case_id"].endswith("__" + ("crest" if slug.startswith("crest") else "curve") +
                                                "__" + ("short_of_500ft" if slug.endswith("short") else
                                                       "at_500ft" if slug.endswith("at") else "beyond_500ft")))
        folder = HERE / "delivery-proofs" / slug
        folder.mkdir(parents=True, exist_ok=True)
        positive_root = ROOT / ".runtime-work" / ("c129731-delivery-diagnostic-" + slug + "-" + args.version)
        negative_root = ROOT / ".runtime-work" / ("c129731-delivery-diagnostic-" + slug + "-negative-" + args.version)
        base = [str(ROOT / ".venv-cpu/bin/python"), str(HERE / "delivery_fixture_proof.py"),
                "--case", case_id, "--output-root"]
        positive = base + [str(positive_root)]
        negative = base + [str(negative_root), "--negative-source-root", str(positive_root),
                           "--negative-missing-source"]
        pos = subprocess.run(positive, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, timeout=240)
        pos_log = folder / "positive.log"
        pos_log.write_text(pos.stdout)
        if pos.returncode:
            raise ValueError("Diagnostic delivery positive failed: " + case_id + " " + pos.stdout[-800:])
        audit_source = positive_root / "attempt/diagnostic-audit.json"
        audit = json.loads(audit_source.read_text())
        if (audit.get("format") != "worker-delivery-audit-diagnostic" or audit.get("passed") is not False or
                audit.get("software_checks_passed") is not True or audit.get("diagnostic_fixture") is not True or
                not all(audit.get("checks", {}).get(key) is True for key in CHECKS)):
            raise ValueError("Diagnostic audit does not prove all software branches")
        neg = subprocess.run(negative, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, timeout=90)
        neg_log = folder / "negative.log"
        neg_log.write_text(neg.stdout)
        if neg.returncode == 0 or EXPECTED not in neg.stdout:
            raise ValueError("Diagnostic delivery negative failed to reject missing rays: " + case_id)
        audit_copy = folder / "diagnostic-audit.json"
        decode_copy = folder / "source-decode.json"
        shutil.copyfile(audit_source, audit_copy)
        shutil.copyfile(positive_root / "source-decode.json", decode_copy)
        acceptance = {"case_id": case_id, "sets": ["demo-test", "full-test"], "checks": list(CHECKS),
                      "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
                      "command": shlex.join(positive), "test_exit_code": 0,
                      "test_log": rel(pos_log), "test_log_sha256": sha(pos_log),
                      "negative_command": shlex.join(negative), "negative_exit_code": neg.returncode,
                      "negative_expected_error": EXPECTED,
                      "negative_log": rel(neg_log), "negative_log_sha256": sha(neg_log),
                      "scope": "20-frame synthetic software audit only; no Native actor pixels or legal acceptance",
                      "diagnostic_audit": rel(audit_copy), "diagnostic_audit_sha256": sha(audit_copy),
                      "diagnostic_decode_receipt": rel(decode_copy),
                      "diagnostic_decode_receipt_sha256": sha(decode_copy)}
        acceptance_path = folder / "acceptance.json"
        acceptance_path.write_text(json.dumps(acceptance, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"case_id": case_id, "positive": sha(pos_log), "negative": sha(neg_log),
                          "diagnostic_audit": sha(audit_copy)}))


if __name__ == "__main__":
    main()
