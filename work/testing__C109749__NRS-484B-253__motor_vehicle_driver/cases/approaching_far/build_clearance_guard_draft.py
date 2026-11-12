"""Stage the clearance-guarded exact construction for primary and fallbacks.

This writes an isolated candidate manifest. Canonical selection and its receipt
bindings are deliberately left unchanged until saved processing is reproved.
"""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parents[1]
STAGE = HERE / "clearance_guard"
LABELS = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    policy = (ASSIGNMENT / "hazard_sweep_policy.py").read_text()
    if "self.hazard_seen" not in policy or "oncoming_cleared" not in policy:
        raise ValueError("Candidate source lacks measured-clearance guard")
    STAGE.mkdir(exist_ok=True)
    manifest = json.loads((ASSIGNMENT / "execution-manifest.json").read_text())
    case = next(row for row in manifest["cases"]
                if row["case_id"].endswith("__approaching_far"))
    manifest["cases"] = [case]
    for label in LABELS:
        old = HERE / ("construction.json" if label == "primary" else label + "-construction.json")
        bundle = json.loads(old.read_text())
        found = [f for f in bundle["files"] if f["path"] == "hazard_sweep_policy.py"]
        if len(found) != 1:
            raise ValueError("Exact bundle needs one policy source")
        found[0]["content"] = policy
        target = STAGE / ("construction.json" if label == "primary" else label + "-construction.json")
        write(target, bundle)
        row = case if label == "primary" else next(x for x in case["candidates"] if x["id"] == label)
        row["construction"] = str(target.relative_to(ASSIGNMENT))
        row["construction_sha256"] = sha(target)
    manifest["canonical_selection"] = False
    manifest["saved_source_proved"] = False
    manifest["comparison_proved"] = False
    manifest_path = ASSIGNMENT / "clearance-guard-draft-manifest.json"
    write(manifest_path, manifest)
    return {"case_id": case["case_id"], "candidate_count": len(LABELS),
            "policy_sha256": sha(ASSIGNMENT / "hazard_sweep_policy.py"),
            "manifest_sha256": sha(manifest_path),
            "canonical_selection": False}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
