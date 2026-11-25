"""Exercise original-source audit with source-shaped CPU fixtures and negatives."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "native"))
import original_source_audit as audit_module
import native_request
import finalize


def save(folder, name, rows):
    path = folder / name
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject(action, text):
    try:
        action()
    except ValueError as exc:
        if text not in str(exc):
            raise AssertionError(f"unexpected rejection {exc}") from exc
        return str(exc)
    raise AssertionError("malformed original source accepted")


def main():
    scratch = ROOT / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        folder = Path(temporary)
        frames = [{"video_frame": i, "native_frame": i + 1000, "time_s": i / 20}
                  for i in range(600)]
        people = [{"native_frame": i + 1000, "time_s": i / 20,
                   "walker_id": 7, "center_xy_m": [-6 + 12 * min(1, max(0, (i - 100) / 240))] * 2,
                   "footprint_xy_m": [[-6 + 12 * min(1, max(0, (i - 100) / 240)) + dx,
                                       -6 + 12 * min(1, max(0, (i - 100) / 240)) + dy]
                                      for dx, dy in ((-.2, -.2), (.2, -.2), (.2, .2), (-.2, .2))],
                   "road_entry_proxy_observed": i == 100,
                   "road_boundary_review_pending": True}
                  for i in range(600)]
        devices = [{"native_frame": i + 1000, "time_s": i / 20,
                    "device_id": "c109166-diagonal-crossing-head",
                    "source_kind": "native_device_readback",
                    "displayed_instruction": "diagonal_dont_walk" if 100 <= i < 160 else "diagonal_walk",
                    "source_ref": f"device-face/{i}"}
                   for i in range(600)]
        cameras = [{"camera": camera["name"], "frame": i, "native_frame": i + 1000,
                    "time_s": i / 20, "width": camera["width"], "height": camera["height"],
                    "source_path": f"{camera['name']}/{i:06d}.png", "source_sha256": "a" * 64}
                   for camera in native_request.camera_plan() for i in range(600)]
        data = {"video_frames.jsonl": frames, "pedestrian-original.jsonl": people,
                "device-original.jsonl": devices, "camera-sources.jsonl": cameras}
        hashes = {name: save(folder, name, rows) for name, rows in data.items()}
        authority = {}
        for name in ("authorization", "official_status", "movement_applicability"):
            path = folder / (name + ".json")
            path.write_text(json.dumps({"synthetic_test_source": name}) + "\n")
            authority[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "device_id": "c109166-diagonal-crossing-head",
                               "movement_id": "c109166-diagonal-sw-ne",
                               "review_status": "pending_independent_review"}
        positive = audit_module.audit(folder, hashes, authority)
        assert positive["first_entry_video_frame"] == 100
        assert positive["official_status_verified"] is False
        (folder / 'authority-receipt.json').write_text(json.dumps(authority) + '\n')
        analysis = finalize.report(folder, 'training__C109166__NRS-484B-287-1e__pedestrian__controlled_2')
        assert analysis['measurements']['diagonal_first_entry_instruction']['value']['first_entry_instruction'] == 'diagonal_dont_walk'
        failures = {}
        bad = dict(hashes)
        del bad["device-original.jsonl"]
        failures["absent_hash"] = reject(lambda: audit_module.audit(folder, bad, authority), "all original")
        bad = dict(hashes, **{"device-original.jsonl": "0" * 64})
        failures["stale_device"] = reject(lambda: audit_module.audit(folder, bad, authority), "stale original")
        broken = [dict(row) for row in people]
        broken[100]["footprint_xy_m"] = []
        bad = dict(hashes, **{"pedestrian-original.jsonl": save(folder, "pedestrian-original.jsonl", broken)})
        failures["missing_body"] = reject(lambda: audit_module.audit(folder, bad, authority), "full pedestrian")
        save(folder, "pedestrian-original.jsonl", people)
        broken = [dict(row) for row in devices]
        broken[100]["source_kind"] = "authored_native_request"
        bad = dict(hashes, **{"device-original.jsonl": save(folder, "device-original.jsonl", broken)})
        failures["request_not_readback"] = reject(lambda: audit_module.audit(folder, bad, authority), "device readback")
        save(folder, "device-original.jsonl", devices)
        broken = [dict(row) for row in frames]
        broken[100]["native_frame"] += 1
        bad = dict(hashes, **{"video_frames.jsonl": save(folder, "video_frames.jsonl", broken)})
        failures["frame_join"] = reject(lambda: audit_module.audit(folder, bad, authority), "pedestrian body/frame")
        save(folder, "video_frames.jsonl", frames)
        bad_authority = json.loads(json.dumps(authority))
        bad_authority["authorization"]["sha256"] = "0" * 64
        failures["stale_authority"] = reject(lambda: audit_module.audit(folder, hashes, bad_authority), "authority source hash")
    proof = {"format": "c109166-original-source-structural-cpu-proof-v1",
             "audit_sha256": hashlib.sha256((HERE / "native/original_source_audit.py").read_bytes()).hexdigest(),
             "positive": positive, "analysis": analysis, "rejections": failures,
             "source_kind": "synthetic_test_fixture", "native_executed": False,
             "physical_completion_verified": False}
    (HERE / "original-source-audit-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"positive_frame_count": positive["frame_count"],
                      "rejections": len(failures), "native_executed": False}))


if __name__ == "__main__":
    main()
