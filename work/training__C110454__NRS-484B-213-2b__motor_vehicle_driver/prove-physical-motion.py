"""CPU proof of selected original-source motion checker; no Native acceptance."""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from physical_motion_audit import EXPECTED, audit, measure_rows


def require(ok, message):
    if not ok:
        raise ValueError(message)


def reject(name, action, rejected):
    try:
        action()
    except ValueError:
        rejected.append(name)
    else:
        raise AssertionError("Motion mutation accepted: " + name)


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    index = json.loads((HERE / "update019-selected-six-index.json").read_text())
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    require(index["manifest_sha256"] == digest and len(index["results"]) == 24,
            "Selected matrix receipt changed")
    expected = {(entry["case_id"], candidate)
                for entry in manifest["cases"] for candidate in
                ("primary", "fallback1", "fallback2", "fallback3")}
    require({(row["case_id"], row["candidate_id"]) for row in index["results"]} == expected,
            "Selected matrix coverage changed")
    outcomes = []
    for row in index["results"]:
        proof_path = HERE / row["proof"]
        require(hashlib.sha256(proof_path.read_bytes()).hexdigest() == row["sha256"],
                "Selected chain proof changed")
        entry = next(e for e in manifest["cases"] if e["case_id"] == row["case_id"])
        candidate = entry if row["candidate_id"] == "primary" else next(
            c for c in entry["candidates"] if c["id"] == row["candidate_id"])
        suffix = row["case_id"].removeprefix(HERE.name + "__")
        base = ROOT / ".runtime-work/c110454-update019-six-selected" / suffix / row["candidate_id"]
        attempt, processing = base / "compatibility", base / "saved/v0001/processing.json"
        result = audit(attempt, processing, row["case_id"], row["candidate_id"],
                       candidate["construction_sha256"], diagnostic=True)
        require(result["observed_relation"] == EXPECTED[suffix] and
                result["native_motion_status"] == "unverified" and
                result["physical_completion_verified"] is False and
                result["source_shaped_motion_status"] == "matched",
                "Diagnostic motion promoted or mismatched")
        outcomes.append({"case_id": row["case_id"], "candidate_id": row["candidate_id"],
                         "observed_relation": result["observed_relation"],
                         "source_sha256": result["source_sha256"]})
    first = manifest["cases"][0]
    suffix = first["case_id"].removeprefix(HERE.name + "__")
    base = ROOT / ".runtime-work/c110454-update019-six-selected" / suffix / "primary"
    attempt, processing = base / "compatibility", base / "saved/v0001/processing.json"
    samples = [json.loads(line) for line in (attempt / "native_samples.jsonl").read_text().splitlines()]
    survey = json.loads((attempt / "road_geometry.json").read_text())
    context = json.loads((attempt / "statutory_context.json").read_text())
    rejected = []
    reject("synthetic_as_original", lambda: audit(attempt, processing, first["case_id"],
           "primary", first["construction_sha256"], diagnostic=False), rejected)
    def damaged_sample(change):
        data = copy.deepcopy(samples)
        change(data)
        return measure_rows(data, survey, suffix, context)
    reject("missing_speed", lambda: damaged_sample(lambda data: data[10].pop("speed_m_s")), rejected)
    reject("mistimed_frame", lambda: damaged_sample(lambda data: data[10].update(time_s=99)), rejected)
    reject("missing_body", lambda: damaged_sample(lambda data: data[10].update(native_body_xy_m=[])), rejected)
    reject("wrong_road_designation", lambda: measure_rows(samples, {**survey, "one_way_native_readback": True},
                                                            suffix, context), rejected)
    reject("wrong_statutory_context", lambda: measure_rows(samples, survey, suffix,
                                                            {**context, "boundary_x_m": 99}), rejected)
    reject("unparked_endpoint", lambda: damaged_sample(lambda data: data[-1].update(speed_m_s=1.0)), rejected)
    proof = {"format": "c110454-selected-physical-motion-cpu-proof-v1",
             "manifest_sha256": digest, "selected_chains": len(outcomes),
             "selected_cases": len(manifest["cases"]),
             "source_shaped_matches": len(outcomes),
             "original_native_motion_verified": 0,
             "rejected_mutations": rejected, "outcomes": outcomes,
             "physical_or_legal_acceptance_claimed": False}
    (HERE / "update021-physical-motion-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({key: proof[key] for key in ("format", "selected_chains",
                                                 "source_shaped_matches", "original_native_motion_verified",
                                                 "rejected_mutations")}))


if __name__ == "__main__":
    main()
