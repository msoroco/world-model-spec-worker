"""Independent retained-source audit for eight synthetic rider package probes."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
index_path = HERE/"draft-package-durable-index.json"
index = json.loads(index_path.read_text())
manifest_path = HERE/"draft-exact-execution-manifest.json"
manifest = json.loads(manifest_path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


assert index["format"] == "c104538-lvmc-synthetic-package-index-v1"
assert index["positive_count"] == index["negative_count"] == 8
assert not index["original_native_capture_executed"] and not index["selected"]
seen = {}
for item in index["results"]:
    path = HERE/item["receipt"]
    assert sha(path) == item["sha256"]
    proof = json.loads(path.read_text())
    folder = path.parent
    kind, candidate = proof["kind"], proof["candidate_id"]
    assert kind in ("mounted_obey", "mounted_turn")
    assert candidate in ("primary", "fallback1", "fallback2", "fallback3")
    assert proof["positive_passed"] and proof["negative_rejected"]
    assert not proof["original_native_capture_executed"] and not proof["selected"]
    for name, digest in proof["retained_sha256"].items():
        assert sha(folder/name) == digest
    assert "Missing required source: rider_native_samples.jsonl" in (folder/"negative.log").read_text()
    source = json.loads((folder/"rider-source-manifest.json").read_text())
    sign = json.loads((folder/"authored-sign.json").read_text())
    assert source["source_kind"] == "synthetic_native_shaped_diagnostic"
    assert source["case_suffix"] == kind and source["candidate_id"] == candidate
    assert source["rider_samples_sha256"] == sha(folder/"rider_native_samples.jsonl")
    assert source["sign_sha256"] == sha(folder/"authored-sign.json")
    assert sign["code"] == "no_u_turn" and sign["authorization_proven"] is False
    road = ET.fromstring((folder/"road.xodr").read_text()).find("road")
    assert road is not None and road.attrib["id"] == "1"
    assert road.find("signals/signal").attrib["id"] == "1140080"
    rider = rows(folder/"rider_native_samples.jsonl")
    native = rows(folder/"native_samples.jsonl")
    mapping = rows(folder/"video_frames.jsonl")
    assert len(rider) == len(native) == len(mapping) == 480
    assert [r["frame"] for r in rider] == list(range(480))
    assert all(r["actor_id"] == "rider-1" and r["machine_class"] == "bicycle" and
               r["mounted"] and not r["walking_machine"] and r["sign_id"] == sign["id"]
               for r in rider)
    assert all(r["time_s"] == n["time_s"] == m["time_s"] and
               n["native_center_xy_m"] == [r["x_m"],r["y_m"]] and
               m["native_frame"] == n["native_frame"] and m["video_frame"] == i
               for i,(r,n,m) in enumerate(zip(rider,native,mapping)))
    turns = sum(r["u_turn_active"] for r in rider)
    assert turns == (0 if kind == "mounted_obey" else 81)
    report = json.loads((folder/"analysis-report.json").read_text())
    result = json.loads((folder/"result.json").read_text())
    compatibility = json.loads((folder/"compatibility.json").read_text())
    assert report["turn_frames"] == turns and report["mounted_turn_frames"] == turns
    assert not report["accepted"] and not report["original_native_capture_executed"]
    assert not result["accepted"] and not result["legal_verdict_claimed"]
    assert compatibility["format"] == "worker-package-compatibility-v1" and compatibility["passed"]
    assert compatibility["construction_sha256"] == proof["construction_sha256"]
    assert {"actual_analysis","native_validation","mandatory_observations","lean_decoder",
            "render","final_decode","acquisition_unchanged"}.issubset(compatibility["checks"])
    assert json.loads((folder/"final-decode.json").read_text())["passed"]
    expected_entry = next(e for e in manifest["cases"] if e["case_id"] == proof["case_id"])
    ref = expected_entry if candidate == "primary" else next(x for x in expected_entry["candidates"] if x["id"] == candidate)
    assert proof["construction_sha256"] == ref["construction_sha256"] == sha(HERE/ref["construction"])
    seen[kind,candidate] = rider

assert len(seen) == 8
for candidate in ("primary","fallback1","fallback2","fallback3"):
    obey = seen["mounted_obey",candidate]
    turn = seen["mounted_turn",candidate]
    assert obey[:200] == turn[:200]
    assert obey[-1]["y_m"] == 4.0 and turn[-1]["y_m"] == -4.0
for kind in ("mounted_obey","mounted_turn"):
    base = seen[kind,"primary"]
    f1 = seen[kind,"fallback1"]
    f2 = seen[kind,"fallback2"]
    f3 = seen[kind,"fallback3"]
    assert (base[0]["x_m"], f1[0]["x_m"]) == (-35.0,-50.0)
    assert next(r["frame"] for r in base if r["x_m"] == 0) == 220
    assert next(r["frame"] for r in f2 if r["x_m"] == 0) == 225
    assert (base[0]["scripted_visibility"], f3[0]["scripted_visibility"]) == (.9,1.0)
    assert all(base[i]["scripted_visibility"] == f1[i]["scripted_visibility"] == f2[i]["scripted_visibility"]
               for i in range(480))

receipt = {"passed": True, "scope": "retained synthetic v1 package sources and receipts",
    "positives": 8, "changed_source_rejections": 8, "controlled_pairs": 4,
    "fallback_trigger_sets": 2, "index_sha256": sha(index_path),
    "exact_manifest_sha256": sha(manifest_path), "original_native_capture_executed": False,
    "legal_verdict_claimed": False, "selected": False}
(HERE/"draft-package-audit-v1.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
print(json.dumps(receipt))
