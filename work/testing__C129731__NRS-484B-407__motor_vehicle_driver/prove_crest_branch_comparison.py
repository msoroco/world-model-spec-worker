"""Run positive and source-tampering negatives for four crest diagnostics."""

import hashlib
import json
import tempfile
import argparse
from pathlib import Path

from crest_branch_comparison import NAMES, REQUIRED, PROBES, audit, names_for, required_for

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ATTEMPTS = {name: ROOT / ".runtime-work" /
            ("c129731-" + name + "-compat-" + ("v5" if name == "approach-b" else "v2"))
            for name in NAMES}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clone_text_sources(source, target, required=REQUIRED):
    target.mkdir(parents=True)
    for name in required:
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.symlink_to((source / name).resolve())
    (target / "result.json").write_bytes((source / "result.json").read_bytes())


def expect_rejection(attempts, fragment, probe="short_of_500ft"):
    try:
        audit(attempts, probe)
    except ValueError as error:
        if fragment not in str(error):
            raise ValueError("Wrong negative comparison rejection: " + str(error)) from error
        return str(error)
    raise ValueError("Tampered crest source was accepted")


def main(probe="short_of_500ft"):
    suffix = PROBES[probe][0]
    names = names_for(probe)
    attempts = ATTEMPTS if suffix == "short" else {
        name: ROOT / ".runtime-work" / ("c129731-" + name + "-compat-v1")
        for name in names}
    positive = audit(attempts, probe)
    if not (positive["software_checks_passed"] is True and positive["passed"] is False and
            positive["physical_acceptance_claimed"] is False):
        raise ValueError("Diagnostic comparison made an acceptance claim")
    negative = {}
    with tempfile.TemporaryDirectory(prefix="c129731-crest-comparison-", dir=ROOT / ".runtime-work") as temp:
        altered = Path(temp) / "camera"
        clone_text_sources(attempts[names[1]], altered, required_for(probe))
        (altered / "config.json").unlink()
        config = json.loads((attempts[names[1]] / "config.json").read_text())
        config["cameras"][0]["width"] -= 1
        (altered / "config.json").write_text(json.dumps(config) + "\n")
        result = json.loads((altered / "result.json").read_text())
        result["source_evidence_hashes"]["config.json"] = sha(altered / "config.json")
        (altered / "result.json").write_text(json.dumps(result) + "\n")
        negative["changed_fixed_camera"] = expect_rejection(
            {**attempts, names[1]: altered}, "Unrelated fixed source condition differs: fixed_config", probe)

        altered = Path(temp) / "missing_ray"
        clone_text_sources(attempts[names[3]], altered, required_for(probe))
        source = altered / "capture/evidence.jsonl"
        source.unlink()
        lines = (attempts[names[3]] / "capture/evidence.jsonl").read_text().splitlines()
        row = json.loads(lines[0])
        row["visibility"]["approaches"] = row["visibility"]["approaches"][:1]
        lines[0] = json.dumps(row, separators=(",", ":"))
        source.write_text("\n".join(lines) + "\n")
        result = json.loads((altered / "result.json").read_text())
        result["source_evidence_hashes"]["capture/evidence.jsonl"] = sha(source)
        (altered / "result.json").write_text(json.dumps(result) + "\n")
        negative["missing_direction_ray"] = expect_rejection(
            {**attempts, names[3]: altered}, "Both original approach rays required", probe)
    report = {"format": "worker-crest-branch-comparison-proof",
              "positive": positive, "negative_rejections": negative,
              "auditor_sha256": sha(HERE / "crest_branch_comparison.py"),
              "software_checks_passed": True, "passed": False,
              "physical_acceptance_claimed": False}
    proof_path = HERE / ("crest-branch-comparison-proof.json" if suffix == "short" else
                         "crest-" + suffix + "-branch-comparison-proof.json")
    proof_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"alternatives": len(names), "probe": probe,
                      "negative_rejections": sorted(negative),
                      "software_checks_passed": True, "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", choices=tuple(PROBES), default="short_of_500ft")
    main(parser.parse_args().probe)
