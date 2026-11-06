"""Independent source and exact-bundle audit; does not confer delivery readiness."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
    if assignment["law_record"]["source"] != "NRS 484B.450(1)(c)":
        raise ValueError("Statutory source differs")
    if assignment["cell"]["layout"] != "intersection" or assignment["cell"]["maneuver"] != "park":
        raise ValueError("Frozen cell differs")
    manifest = json.loads((HERE / "draft-execution-manifest.json").read_text())
    if manifest["assignment_id"] != HERE.name or len(manifest["cases"]) != 2:
        raise ValueError("Draft case set differs")
    proof = {}
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        if suffix not in ("probe_a", "probe_b") or len(entry["candidates"]) != 3:
            raise ValueError("Case or fallback cardinality differs")
        refs = [{"id": entry["id"], "construction": entry["construction"],
                 "construction_sha256": entry["construction_sha256"]}] + entry["candidates"]
        knobs = []
        for ref in refs:
            path = HERE / ref["construction"]
            if sha(path) != ref["construction_sha256"]:
                raise ValueError("Construction hash differs")
            construction = json.loads(path.read_text())
            files = {row["path"]: row["content"] for row in construction["files"]}
            if construction["case_id"] != entry["case_id"] or construction["entrypoint"] != "runner.py":
                raise ValueError("Construction identity differs")
            if not {"runner.py", "geometry.py", "engineering.py", "measure.py",
                    "finalize.py", "road.xodr", "config.json"} <= files.keys():
                raise ValueError("Executable bundle incomplete")
            config = json.loads(files["config.json"])
            if config["candidate_id"] != ref["id"] or config["case_suffix"] != suffix or \
               config["law_id"] != "NRS-484B-450-1c" or config["cell_id"] != "C110454":
                raise ValueError("Bundled config differs")
            if config["duration_s"] * config["rate_hz"] != 480:
                raise ValueError("Bundled capture cardinality differs")
            knobs.append(config["engineering_knobs"])
        primary = knobs[0]
        changed = [{k for k in primary if row[k] != primary[k]} for row in knobs[1:]]
        if changed != [{"route_lookahead_m"}, {"parking_brake_margin_m"},
                       {"overview_fov_deg"}]:
            raise ValueError("Fallbacks are not three distinct independent knobs")
        for ref in entry["candidates"]:
            if not ref["trigger"].get("source") or not ref["trigger"].get("metric"):
                raise ValueError("Fallback trigger lacks measured source")
        proof[suffix] = {"primary_plus_fallbacks": 4,
                         "distinct_knobs": [sorted(c) for c in changed]}
    print(json.dumps({"passed": True, "scope": "independent exact draft audit",
                      "assignment_sha256": sha(REPO / "inputs" / HERE.name / "assignment.json"),
                      "cases": proof, "ready": False}, indent=2))


if __name__ == "__main__": main()
