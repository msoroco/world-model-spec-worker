"""Independent exact-case and changed-knob check for four camera fallbacks."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    manifest = json.loads((ROOT / "execution-manifest-draft.json").read_text())
    if len(manifest["cases"]) != 4:
        raise ValueError("Four exact officer cases required")
    for entry in manifest["cases"]:
        if len(entry.get("candidates", [])) != 1:
            raise ValueError("One source-triggered fallback required")
        candidate = entry["candidates"][0]
        if candidate["id"] != "fallback1":
            raise ValueError("Unknown officer fallback")
        primary_path = ROOT / entry["construction"]
        fallback_path = ROOT / candidate["construction"]
        if sha(primary_path) != entry["construction_sha256"] or sha(fallback_path) != candidate["construction_sha256"]:
            raise ValueError("Officer construction source changed")
        primary = json.loads(primary_path.read_text())
        fallback = json.loads(fallback_path.read_text())
        if primary["case_id"] != entry["case_id"] or fallback["case_id"] != entry["case_id"]:
            raise ValueError("Fallback selected another officer case")
        pfiles = {item["path"]: item["content"] for item in primary["files"]}
        ffiles = {item["path"]: item["content"] for item in fallback["files"]}
        if pfiles.keys() != ffiles.keys() or any(pfiles[name] != ffiles[name]
                                                 for name in pfiles if name != "config.json"):
            raise ValueError("Fallback altered non-configuration implementation")
        pconfig, fconfig = json.loads(pfiles["config.json"]), json.loads(ffiles["config.json"])
        if pconfig["selected_case_id"] != fconfig["selected_case_id"]:
            raise ValueError("Fallback changed case identity")
        p_mounts = pconfig.pop("camera_mounts")
        f_mounts = fconfig.pop("camera_mounts")
        if pconfig != fconfig or p_mounts == f_mounts:
            raise ValueError("Fallback changed invariant or did not change camera geometry")
        for name in p_mounts:
            if name not in ("approach", "reference_corner") and p_mounts[name] != f_mounts[name]:
                raise ValueError("Fallback changed an undeclared camera")
        if not all(candidate["trigger"].get(key) for key in
                   ("source", "metric", "failure_condition")):
            raise ValueError("Fallback lacks measurable physical trigger")
    return {"cases": 4, "source_bound_fallbacks": 4,
            "simulation_started": False, "physical_acceptance_claimed": False}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
