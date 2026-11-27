"""Exercise fallback delivery and physical audit paths on CPU fixtures."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from physical_completion import assess
from prove_physical_preparation import EVENTS, capture, lifecycle
from selected_delivery_audit import audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c158208-owner-nov26b"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove() -> dict:
    manifest = json.loads((HERE / "execution-manifest.source-gated-draft.json").read_text())
    SCRATCH.joinpath("tmp").mkdir(parents=True, exist_ok=True)
    rows = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.rsplit("__", 1)[1]
        candidate = entry["candidates"][0]
        construction_sha = candidate["construction_sha256"]
        stage = SCRATCH / "deferred-compat-v6" / kind / "fallback1"
        checked = audit(stage, case_id=case_id, diagnostic_fixture=True)
        if checked["source_frames"] != 3 or checked["physical_acceptance_claimed"]:
            raise ValueError("fallback diagnostic delivery scope differs: " + kind)
        with tempfile.TemporaryDirectory(prefix=kind + "-negative-", dir=SCRATCH / "tmp") as tmp:
            missing = Path(tmp)
            for source in stage.iterdir():
                if source.is_file() and source.name != "overview.mkv":
                    (missing / source.name).symlink_to(source)
            try:
                audit(missing, case_id=case_id, diagnostic_fixture=True)
            except (FileNotFoundError, ValueError, KeyError):
                pass
            else:
                raise ValueError("fallback missing overview camera accepted: " + kind)
        physical = {}
        with tempfile.TemporaryDirectory(prefix=kind + "-motion-", dir=SCRATCH / "tmp") as tmp:
            for fixture, expected in (("complete", "met"), ("incomplete", "not_met"),
                                      ("missing", "unverified")):
                attempt = Path(tmp) / fixture
                attempt.mkdir()
                if fixture != "missing":
                    capture(attempt, incomplete=fixture == "incomplete")
                result = assess(attempt, case_id, construction_sha, diagnostic_fixture=True)
                status = result["physical_checks"]["maneuver"]["status"]
                if status != expected:
                    raise ValueError("fallback physical status differs: " + kind + " " + fixture)
                physical[fixture] = status
        lifecycle(EVENTS)
        try:
            lifecycle([event for event in EVENTS if event != "owner_released"])
        except ValueError:
            pass
        else:
            raise ValueError("fallback missing owner release accepted: " + kind)
        receipt = {"case_id": case_id, "candidate_id": "fallback1",
                   "construction_sha256": construction_sha,
                   "delivery_audit": checked, "missing_overview_rejected": True,
                   "physical_fixture_statuses": physical,
                   "missing_owner_release_rejected": True,
                   "scope": "synthetic_fixture_cpu_only", "physical_acceptance_claimed": False}
        target = HERE / "cases" / kind / "fallback1" / "audit-cpu.json"
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        rows.append({"case_id": case_id, "candidate_id": "fallback1",
                     "construction_sha256": construction_sha,
                     "receipt": str(target.relative_to(HERE)), "sha256": sha(target)})
    index = {"format": "c158208-fallback-audit-cpu-index-v1",
             "assignment_id": HERE.name, "scope": "synthetic_fixture_cpu_only",
             "draft_manifest_sha256": sha(HERE / "execution-manifest.source-gated-draft.json"),
             "cases": rows, "physical_acceptance_claimed": False,
             "legal_acceptance_claimed": False}
    output = HERE / "deferred-fallback-audit-index.json"
    output.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    return {"cases": len(rows), "index_sha256": sha(output), "scope": index["scope"]}


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
