"""Retain compact, source-bound witness proof receipts from ignored scratch."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_text(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text().rstrip() + "\n")
    return sha(target)


def main():
    manifest_path = HERE / "current-v2-witness-fallback-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    summary = {"format": "c110454-current-witness-cpu-proof-v3",
               "status": "unselected_diagnostic", "manifest_sha256": sha(manifest_path),
               "current_runtime_manifest_sha256": manifest["runtime_manifest_sha256"],
               "synthetic_fixture": True, "native_executed": False,
               "physical_or_legal_acceptance_claimed": False, "chains": []}
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        for candidate in [entry, *entry["candidates"]]:
            name = candidate["id"]
            base = SCRATCH / "c110454-current-fallbacks" / suffix
            compat = base / (name + "-compat-v4")
            offline = (SCRATCH / "c110454-current-profile" / ("offline-v2-" + suffix)
                       if name == "primary" else base / name)
            destination = HERE / "current-v3-witness-proofs" / suffix / name
            files = {}
            for source_name, target_name in (("compatibility.json", "compatibility.json"),
                                             ("compatibility-analysis.log", "compatibility-analysis.log"),
                                             ("negative-analysis.log", "negative-analysis.log")):
                files[target_name] = copy_text(compat / source_name, destination / target_name)
            files["offline.log"] = copy_text(offline / "offline.log", destination / "offline.log")
            receipt = json.loads((destination / "compatibility.json").read_text())
            assert receipt["passed"] is True and len(receipt["checks"]) == 11
            assert receipt["case_id"] == entry["case_id"] and receipt["candidate_id"] == name
            assert receipt["construction_sha256"] == candidate["construction_sha256"]
            assert receipt["negative_removed"] == "native_parking_history.json"
            summary["chains"].append({"case_id": entry["case_id"], "candidate_id": name,
                                       "construction_sha256": candidate["construction_sha256"],
                                       "fixture_recipe_sha256": receipt["fixture_recipe_sha256"],
                                       "checks_passed": len(receipt["checks"]),
                                       "negative_removed": receipt["negative_removed"],
                                       "files": {str((destination / key).relative_to(HERE)): value
                                                 for key, value in files.items()}})
    target = HERE / "current-v3-witness-cpu-proof.json"
    target.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"chains": len(summary["chains"]), "proof_sha256": sha(target)}))


if __name__ == "__main__":
    main()
