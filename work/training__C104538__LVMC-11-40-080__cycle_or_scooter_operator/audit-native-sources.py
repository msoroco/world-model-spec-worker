"""Independent raw-row audit for the unselected C104538 rider proposal."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
source = ROOT/"draft-native-source-manifest.json"
manifest = json.loads(source.read_text())
assert manifest["format"] == "c104538-lvmc-1140080-synthetic-source-v1"
sign_path = ROOT/manifest["sign_path"]
assert hashlib.sha256(sign_path.read_bytes()).hexdigest() == manifest["sign_sha256"]
sign = json.loads(sign_path.read_text())
assert sign["code"] == "no_u_turn" and sign["governs_road"] == 1
assert sign["governs_lane"] == -1 and sign["authorization_proven"] is False
assert len(manifest["entries"]) == 12
observed = {}
negative_count = 0
for entry in manifest["entries"]:
    p = ROOT/entry["path"]
    assert hashlib.sha256(p.read_bytes()).hexdigest() == entry["sha256"]
    rows = [json.loads(x) for x in p.read_text().splitlines()]
    assert len(rows) == 480
    assert [r["frame"] for r in rows] == list(range(480))
    assert all(r["time_s"] == r["frame"]/20 for r in rows)
    assert all(r["sign_id"] == sign["id"] and r["road_id"] == 1
               and r["approach_lane_id"] == -1 for r in rows)
    assert all(r["actor_id"] == "rider-1" and r["machine_id"] == "bicycle-1"
               and r["machine_class"] == "bicycle" for r in rows)
    assert all(r["walking_machine"] is not r["mounted"] for r in rows)
    turns = [r for r in rows if r["u_turn_active"]]
    m = entry["measurement"]
    assert len(turns) == m["turn_frames"]
    assert sum(r["mounted"] for r in turns) == m["mounted_turn_frames"]
    assert sum(not r["mounted"] for r in turns) == m["dismounted_turn_frames"]
    assert (turns[0]["frame"] if turns else None) == m["first_turn_frame"]
    dismount = next((r["frame"] for r in rows if not r["mounted"]), None)
    assert dismount == m["dismount_frame"]
    if entry["kind"] == "dismounted_turn":
        assert dismount == 200 and m["mounted_turn_frames"] == 0
        assert m["first_turn_frame"] > dismount
    elif entry["kind"] == "mounted_turn":
        assert dismount is None and m["mounted_turn_frames"] == 81
    else:
        assert dismount is None and not turns
    assert m["runway_trigger_under_35m"] == (m["approach_runway_m"] < 35)
    assert m["release_trigger_over_3_frames"] == (m["release_error_frames"] > 3)
    assert m["visibility_trigger_below_0_95"] == (m["scripted_visibility"] < .95)
    assert m["original_native_observed"] is False and m["legal_outcome"] == "unresolved"
    observed[entry["kind"], entry["variant"]] = (rows, m)
    # Each altered source must fail one independent join or count check.
    changed = [dict(r) for r in rows]
    changed[0]["sign_id"] = "other-sign"
    assert not all(r["sign_id"] == sign["id"] for r in changed)
    negative_count += 1
    changed = [dict(r) for r in rows]
    changed[17]["frame"] = 18
    assert [r["frame"] for r in changed] != list(range(480))
    negative_count += 1
    changed = [dict(r) for r in rows]
    changed[200]["mounted"] = not changed[200]["mounted"]
    assert any(r["walking_machine"] is r["mounted"] for r in changed)
    negative_count += 1

for variant in ("primary", "fallback1", "fallback2", "fallback3"):
    obey, _ = observed["mounted_obey", variant]
    mounted, _ = observed["mounted_turn", variant]
    dismounted, _ = observed["dismounted_turn", variant]
    assert all(obey[i] == mounted[i] == dismounted[i] for i in range(200))
    assert [r["x_m"] for r in mounted[:220]] == [r["x_m"] for r in obey[:220]]
    assert [r["y_m"] for r in mounted[:220]] == [r["y_m"] for r in obey[:220]]
    assert mounted[-1]["y_m"] == dismounted[-1]["y_m"] == -4.0
    assert obey[-1]["y_m"] == 4.0

for kind in ("mounted_obey", "mounted_turn", "dismounted_turn"):
    base = observed[kind, "primary"][1]
    f1 = observed[kind, "fallback1"][1]
    f2 = observed[kind, "fallback2"][1]
    f3 = observed[kind, "fallback3"][1]
    assert (base["approach_runway_m"], f1["approach_runway_m"]) == (27.0, 42.0)
    assert (base["release_error_frames"], f2["release_error_frames"]) == (0, 5)
    assert (base["scripted_visibility"], f3["scripted_visibility"]) == (.9, 1.0)
    for key in ("release_error_frames", "scripted_visibility"):
        assert f1[key] == base[key]
    for key in ("approach_runway_m", "scripted_visibility"):
        assert f2[key] == base[key]
    for key in ("approach_runway_m", "release_error_frames"):
        assert f3[key] == base[key]

receipt = {"passed": True, "scope": "synthetic raw rows only", "source_count": 12,
           "negative_rejections": negative_count, "controlled_triplets": 4,
           "fallback_trigger_sets": 3, "manifest_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
           "original_native_observed": False, "sign_authorized": False,
           "legal_outcome": "unresolved"}
(ROOT/"draft-native-source-audit.json").write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n")
print(json.dumps(receipt))
