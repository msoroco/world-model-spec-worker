"""Build explicit 600-frame synthetic source recipes for exact software checks.

Graph and trace scaffolding comes from an existing CPU fixture. Rider-arm and
roadway packets are generated independently and remain diagnostic only.
"""
import hashlib
import json
from pathlib import Path
import tempfile

from test_audit_arm_cases import case_fixture
from road import open_drive


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent
REFERENCE = REPO / "work/training__C230328__NRS-484B-777-3__cycle_or_scooter_operator/diagnostic-controlled_1-primary.json"
SCRATCH = REPO / ".runtime-work/c229831-temp"
AID = FOLDER.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Returned diagnostic specification exceeds 2 MiB")


def main():
    base = json.loads(REFERENCE.read_text())
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for label, method in (("a", "right_horizontal"),
                          ("b", "none"), ("c", "left_upward")):
        case_id = AID + "__probe_" + label
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            case_fixture(root, method)
            spec = {"files": dict(base["files"]),
                    "graphs": base["graphs"], "videos": base["videos"]}
            spec["files"]["road.xodr"] = open_drive()
            for name in ("rider_arm.jsonl", "camera_frames.jsonl",
                         "road_context.json", "capture-seal.json"):
                spec["files"][name] = (root / name).read_text()
            spec["files"]["video_frames.jsonl"] = "".join(
                json.dumps({"video_frame": frame, "native_frame": frame + 1000,
                    "carla_frame": frame + 1000, "time_s": frame / 20,
                    "camera_native_frames": {name: frame + 1000 for name in
                        ("overview", "approach", "reference_corner", "driver_reference")}}) + "\n"
                for frame in range(600))
            capture_manifest = json.loads(spec["files"]["capture/manifest.json"])
            capture_manifest["case_id"] = case_id
            capture_manifest["sources"]["road.xodr"] = hashlib.sha256(
                spec["files"]["road.xodr"].encode()).hexdigest()
            spec["files"]["capture/manifest.json"] = json.dumps(capture_manifest) + "\n"
            path = FOLDER / ("diagnostic-probe-" + label + ".json")
            dump(path, spec)
            source = path.relative_to(REPO).as_posix()
            recipe = {"format": "worker-fixture-recipe",
                      "sources": [{"path": "diagnostic-input.json",
                                   "source": source, "sha256": sha(path)}],
                      "generator": {"source": source, "sha256": sha(path)}}
            dump(FOLDER / ("diagnostic-probe-" + label + "-recipe.json"), recipe)
    print(json.dumps({"diagnostic_recipes": 3, "synthetic_only": True}))


if __name__ == "__main__":
    main()
