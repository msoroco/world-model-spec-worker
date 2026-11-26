"""Materialize the canonical seven-case source-gated rider root bundle."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    first = plan["cases"][0]["case_id"]
    name = first.removeprefix(HERE.name + "__")
    selected = json.loads((HERE / ("construction-" + name + ".json")).read_text())
    files = {entry["path"]: entry["content"] for entry in selected["files"]}
    config = json.loads(files["config.json"])
    config["cameras"] = [
        {"name": camera, "width": width, "height": height, "fov_deg": 75,
         "pose_strategy": coverage["subject"]}
        for camera, (width, height), coverage in zip(
            ("overview", "approach", "reference_corner", "driver_reference"),
            ((1920, 1080), (1280, 720), (1280, 720), (1280, 720)),
            plan["camera_plan"]["coverage"])]
    config["frame_count"] = 900
    config["supported_case_ids"] = [case["case_id"] for case in plan["cases"]]
    config["plan_sha256"] = sha(HERE / "case-plan.json")
    write(HERE / "config.json", config)
    (HERE / "runner.py").write_text(files["runner.py"])
    (HERE / "tests/test_bundle.py").write_text(
        '"""Root exact source-gated bundle preflight."""\n'
        'import sys\nfrom pathlib import Path\n'
        'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n'
        'from runner import check\n\n'
        'def test_bundle():\n'
        '    case_id, device, facility, condition = check()\n'
        '    assert case_id.endswith("__" + device + "__" + facility + "__" + condition + "_path")\n')
    construction = {key: selected[key] for key in (
        "law_id", "cell_id", "actor", "case_id", "entrypoint",
        "recording_description", "measurement_plan", "static_checks",
        "termination_rules", "mechanisms")}
    paths = ("runner.py", "source_deferred_runner.py", "source_site.py",
             "path_route.py", "path_observation.py", "analysis.py",
             "config.json", "tests/test_bundle.py")
    construction["files"] = [{"path": path, "content": (HERE / path).read_text()}
                             for path in paths]
    write(HERE / "construction.json", construction)


if __name__ == "__main__":
    main()
