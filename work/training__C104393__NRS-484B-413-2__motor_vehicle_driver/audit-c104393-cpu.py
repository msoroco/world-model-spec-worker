"""Independent frozen-law, exact-bundle and saved synthetic CPU receipt audit."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
ASSIGNMENT=HERE.name

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())

def audit():
    frozen=read(ROOT/"inputs"/ASSIGNMENT/"assignment.json")
    plan=read(HERE/"case-plan.json")
    manifest=read(HERE/"draft-execution-manifest.json")
    summary=read(HERE/"draft-offline-summary.json")
    result=read(HERE/"result.json")
    law=frozen["law_record"]["text"]
    assert law==plan["source_law_text"]
    assert "last 100 feet" in law and "last 300 feet" in law and "regardless of the weather" in law
    assert (frozen["cell"]["layout"],frozen["cell"]["maneuver"],frozen["cell"]["control"])==(
        "hill_crest","turn","other_vehicle")
    assert manifest["assignment_id"]==ASSIGNMENT and manifest["status"]=="draft_not_selected"
    assert len(manifest["cases"])==6 and len(summary["results"])==24
    assert summary["runtime_manifest_sha256"]==sha(ROOT/"runtime/pipeline/SOURCE-MANIFEST.json")
    expected={c["case_id"]:c["requested_setting"] for c in plan["cases"]}
    assert set(expected)=={c["case_id"] for c in manifest["cases"]}
    receipts={(r["case_id"],r["candidate_id"]):r for r in summary["results"]}
    assert len(receipts)==24
    for entry in manifest["cases"]:
        case_id=entry["case_id"];feet=expected[case_id]
        choices=[{"id":"primary","construction":entry["construction"],
            "construction_sha256":entry["construction_sha256"]}]+entry["candidates"]
        assert {c["id"] for c in choices}=={"primary","fallback1","fallback2","fallback3"}
        configs={}
        for choice in choices:
            candidate=choice["id"]
            path=HERE/choice["construction"]
            assert sha(path)==choice["construction_sha256"]
            bundle=read(path)
            assert bundle["case_id"]==case_id and bundle["entrypoint"]=="runner.py"
            files={f["path"]:f["content"] for f in bundle["files"]}
            assert {"runner.py","saved_measure.py","fallback_triggers.py",
                "tests/test_bundle.py","config.json"}<=set(files)
            config=json.loads(files["config.json"])
            assert (config["case_id"],config["candidate_id"])==(case_id,candidate)
            request=config["native_request"]
            assert request["signal_start_ft"]==feet
            assert abs((130-request["signal_start_station_m"])/.3048-feet)<1e-4
            assert (request["rate_hz"],request["duration_s"])==(20,42)
            assert request["area"]=="any_other_area"
            configs[candidate]=request
            receipt=receipts[(case_id,candidate)]
            assert receipt["exit_code"]==0 and receipt["construction_sha256"]==sha(path)
            assert sha(HERE/receipt["command_log"])==receipt["command_log_sha256"]
            assert sha(HERE/receipt["unit_log"])==receipt["unit_log_sha256"]
            assert "OK" in (HERE/receipt["unit_log"]).read_text()
        base=configs["primary"]
        expected_changed={"fallback1":{"candidate_id","turn_radius_m","map_sha256","route_sha256"},
            "fallback2":{"candidate_id","controller_lookahead_m"},
            "fallback3":{"candidate_id","camera_height_m","camera_fov_deg"}}
        for name,keys in expected_changed.items():
            changed={key for key in base if base[key]!=configs[name][key]}
            assert changed==keys,(name,changed)
    synthetic=read(HERE/"synthetic-saved-cpu-receipt.json")
    assert synthetic["passed"] is True and synthetic["provenance"]=="synthetic_cpu_fixture"
    assert synthetic["physical_success_claimed"] is False
    for item in synthetic["cases"]:
        source=HERE/item["source"]
        assert sha(source)==item["source_sha256"]
        rows=[json.loads(line) for line in source.read_text().splitlines()]
        assert len(rows)==840
        turn=next(i for i,row in enumerate(rows) if row["course_change"])
        start=turn
        while rows[start-1]["signal"]=="left":start-=1
        distance=sum(math.dist(rows[i-1]["ego_xy_m"],rows[i]["ego_xy_m"])
            for i in range(start+1,turn+1))/.3048
        assert abs(distance-item["measured_ft"])<1e-9
        assert abs(distance-item["target_ft"])<.5
        assert all(item["baseline_trigger_metrics"][key] is False
            for key in ("fallback1","fallback2","fallback3"))
        assert set(item["negative"])=={"source_hash_mismatch","missing_frame"}
        if item["target_ft"]==300:
            assert set(item["isolated_synthetic_crossings"])=={"fallback1","fallback2","fallback3"}
            for key,entry in item["isolated_synthetic_crossings"].items():
                assert entry["metric"][key] is True
                assert sum(entry["metric"][name] for name in
                    ("fallback1","fallback2","fallback3"))==1
                assert entry["metric"]["dispatchable_observation"] is False
    assert result["status"]=="blocked" and result["cases_selected"]==0
    assert result["recordings_accepted"]==0 and result["carla_executed"] is False
    return {"format":"c104393-independent-cpu-audit-v1","passed":True,
        "cases":6,"draft_bundles":24,"pinned_offline_passes":24,
        "synthetic_saved_cases":2,"isolated_synthetic_trigger_crossings":3,
        "native_executed":False,"delivery_ready":False,
        "source_hashes":{"frozen_assignment":sha(ROOT/"inputs"/ASSIGNMENT/"assignment.json"),
            "draft_manifest":sha(HERE/"draft-execution-manifest.json"),
            "offline_summary":sha(HERE/"draft-offline-summary.json"),
            "synthetic_saved":sha(HERE/"synthetic-saved-cpu-receipt.json")}}

if __name__=="__main__":
    receipt=audit()
    (HERE/"independent-cpu-audit.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt))
