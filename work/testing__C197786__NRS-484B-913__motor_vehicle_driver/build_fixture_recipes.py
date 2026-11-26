"""Build exact synthetic software fixtures with distinct source-hashed hose facts."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
TEMPLATE = REPO / "work/testing__C229439__NRS-484B-450-1o__motor_vehicle_driver/cases/park_effective/diagnostic.json"


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    base = json.loads(TEMPLATE.read_text())
    if len(base["graphs"]) != 900 or any(v["frames"] != 900 for v in base["videos"]):
        raise ValueError("diagnostic Native skeleton must be 900 frames")
    for case in plan["cases"]:
        cid = case["case_id"]
        short = cid.removeprefix(ROOT.name + "__")
        folder = ROOT / "cases" / short
        folder.mkdir(parents=True, exist_ok=True)
        spec = json.loads(json.dumps(base))
        capture_manifest = json.loads(spec["files"]["capture/manifest.json"])
        capture_manifest["case_id"] = cid
        spec["files"]["capture/manifest.json"] = encoded(capture_manifest)
        facts = {
            "private_way": {"owner": "diagnostic private owner", "permitted_access": ["diagnostic owner"],
                            "ego_route_xy": [[0, -2], [0, 2]] if case["planned_hose_crossing"]
                            else [[2, -2], [2, 2]]},
            "hose": {"blueprint_id": "static.prop.firehose", "segment_xy": [[-1, 0], [1, 0]],
                     "fire_department_affiliation": True, "protection": case["hose_protection"]},
            "incident": {"purpose": case["incident_purpose"]},
            "official": {"identity": "diagnostic captain", "in_command": True},
            "consent": {"status": case["command_consent"]},
            "vehicle": {"ordinary_motor_vehicle": True, "human_driver": True},
        }
        if case["command_consent"] == "given":
            facts["consent"].update(official_identity="diagnostic captain", frame=100,
                                     scope="diagnostic hose crossing")
        bindings = {}
        for role, fact in facts.items():
            path = f"original-context/{role}.json"
            text = encoded(fact)
            spec["files"][path] = text
            bindings["road" if role == "private_way" else "command_official" if role == "official" else role] = {
                "source_path": path, "sha256": sha(text), **fact}
        bindings["road"]["private_way_owner"] = facts["private_way"]["owner"]
        rows = []
        for i in range(900):
            y = 0 if i == 500 and case["planned_hose_crossing"] else -2
            x = 0 if case["planned_hose_crossing"] else 2
            rows.append({"frame": i + 1, "elapsed_seconds": i / 20,
                         "ego_xy": [x, y],
                         "ego_body_corners_xy": [[x - .2, y - .2], [x + .2, y - .2],
                                                 [x + .2, y + .2], [x - .2, y + .2]]})
        frames = "".join(encoded(row) for row in rows)
        spec["files"]["frames.jsonl"] = frames
        seal = {"case_id": cid, "frame_count": 900, "rate_hz": 20,
                "frames_sha256": sha(frames), "physical_completion": "unreviewed",
                "diagnostic_fixture": True}
        seal_text = encoded(seal)
        spec["files"]["seal.json"] = seal_text
        packet = {"case_id": cid,
                  "native": {"result_sha256": sha(seal_text), "source_path": "frames.jsonl",
                             "source_sha256": sha(frames), "frames": rows}, **bindings}
        spec["files"]["saved-packet.json"] = encoded(packet)
        path = folder / "diagnostic.json"
        path.write_text(encoded(spec))
        note = folder / "diagnostic-source-note.json"
        note.write_text(encoded({"case_id": cid, "diagnostic_fixture": True,
                                 "original_source_claimed": False}))
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": note.name,
                               "source": str(note.relative_to(REPO)),
                               "sha256": sha(note.read_text())}],
                  "generator": {"source": str(path.relative_to(REPO)),
                                "sha256": sha(path.read_text())}}
        (folder / "fixture-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
        if path.stat().st_size > 2097152:
            raise ValueError("diagnostic specification exceeds worker file limit")
        print(short, path.stat().st_size)


if __name__ == "__main__":
    build()
