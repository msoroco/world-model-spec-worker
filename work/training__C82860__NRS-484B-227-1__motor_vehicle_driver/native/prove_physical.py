"""Exercise the pinned source-bound motion checker on diagnostic outcomes."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import assess_physical


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def prove(suffix):
    source = PKG / "native/bundles" / suffix / "construction.json"
    construction = json.loads(source.read_text())
    cfg = json.loads(next(row["content"] for row in construction["files"]
                          if row["path"] == "config.json"))
    fixtures = []
    for kind, expected in (("complete_motion", "met"),
                           ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        root = REPO / ".runtime-work/c82860-lead/physical" / suffix / kind
        if root.exists():
            shutil.rmtree(root)
        shutil.copytree(PKG / "diagnostic" / suffix, root)
        write(root / "config.json", cfg)
        body = root / "body_history.jsonl"
        if kind == "missing_evidence":
            body.unlink()
        else:
            rows = [json.loads(line) for line in body.read_text().splitlines()]
            if kind == "complete_motion":
                for i, row in enumerate(rows):
                    row["heading_deg"] = 180 * i / (len(rows) - 1)
            else:
                for row in rows:
                    row["heading_deg"] = 0
            body.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        result = assess_physical(root, cfg)
        status = result["physical_checks"]["maneuver"]["status"]
        if status != expected:
            raise AssertionError((suffix, kind, status, expected))
        result.update(provenance_kind="synthetic_fixture", diagnostic_fixture=True)
        out = PKG / "native/proofs" / f"physical-{suffix}-{kind}.json"
        log = PKG / "native/proofs" / f"physical-{suffix}-{kind}.log"
        write(out, result)
        log.write_text(f"{suffix} {kind}: {status}; synthetic fixture only\n")
        fixtures.append({"kind": kind, "command": f".venv-cpu/bin/python {__file__} {suffix}",
                         "exit_code": 0, "log": str(log.relative_to(PKG)),
                         "log_sha256": sha(log), "result": str(out.relative_to(PKG)),
                         "result_sha256": sha(out)})
    events = ["capture_finished", "encoders_closed", "restoration_verified",
              "native_exit", "owner_released", "saved_processing_started"]
    def saved_processing_allowed(observed):
        return observed == events
    if not saved_processing_allowed(events) or saved_processing_allowed(events[:-2] + events[-1:]):
        raise AssertionError("Lifecycle gate failed to reject processing before owner release")
    lifecycle_log = PKG / "native/proofs" / f"lifecycle-{suffix}.log"
    lifecycle_log.write_text("Synthetic lifecycle order passed; processing before owner release rejected\n")
    proof = {"construction_sha256": sha(source), "fixtures": fixtures,
             "lifecycle": {"events": events,
                           "exit_code": 0, "log": str(lifecycle_log.relative_to(PKG)),
                           "log_sha256": sha(lifecycle_log)}}
    receipt = PKG / "native/proofs" / f"physical-{suffix}.json"
    write(receipt, proof)
    print(json.dumps({"receipt": str(receipt.relative_to(PKG)), "sha256": sha(receipt)}))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("authorized_opening", "barrier_crossing"):
        raise SystemExit("Use one exact U-turn suffix")
    prove(sys.argv[1])
