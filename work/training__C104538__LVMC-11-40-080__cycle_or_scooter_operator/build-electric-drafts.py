"""Create exact, unselected electric-class case constructions for CPU checks.

The Native capture requires an operator-supplied, source-hashed asset review.
These drafts make no claim that such an asset or original pixels exist.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
CLASSES = ("electric_bicycle", "electric_scooter")
BEHAVIORS = (("controlled_1", "obey"), ("controlled_2", "turn"),
             ("controlled_3", "dismount"))


def replace_once(value: str, old: str, new: str) -> str:
    count = value.count(old)
    if count != 1:
        raise ValueError(f"Expected one occurrence of {old!r}; found {count}")
    return value.replace(old, new)


def build(machine_class: str, source_case: str, behavior: str,
          candidate: str = "primary") -> dict:
    if candidate == "fallback1":
        name = {"controlled_1": "mounted_obey", "controlled_2": "mounted_turn",
                "controlled_3": "dismounted_turn"}[source_case]
        source = ROOT / "current-candidates" / name / "fallback1/construction.json"
    elif candidate == "primary":
        source = ROOT / ("cases" if source_case != "controlled_1" else "")
        source = source / (source_case if source_case != "controlled_1" else "") / "construction.json"
    else:
        raise ValueError("Unknown candidate")
    construction = json.loads(source.read_text())
    old_case_id = construction["case_id"]
    new_case_id = f"{ASSIGNMENT}__{machine_class}_{behavior}"
    file_map = {item["path"]: item for item in construction["files"]}
    runner = file_map["runner.py"]["content"]
    runner = replace_once(runner, "import math\n", "import math\nimport os\n")
    runner = replace_once(runner, "from controller import PathController\n",
                          "from controller import PathController\nfrom electric_asset import spawn_reviewed_electric\n")
    runner = runner.replace("'machine_class': 'bicycle'", f"'machine_class': '{machine_class}'")
    old_spawn = """        blueprint = world.get_blueprint_library().find('vehicle.bh.crossbike')
        blueprint.set_attribute('role_name', 'c104538_lvmc_bicycle')
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=engineering['start_x_m'], y=4, z=.5), carla.Rotation(yaw=0)))"""
    new_spawn = f"""        review_path_text = os.environ.get('C104538_ELECTRIC_ASSET_REVIEW')
        if not review_path_text:
            raise RuntimeError('Supply reviewed electric asset source path')
        review_path = Path(review_path_text).resolve()
        if not review_path.is_file():
            raise RuntimeError('Reviewed electric asset source is absent')
        asset_evidence = json.loads(review_path.read_text())
        ego, asset_binding = spawn_reviewed_electric(
            world, '{machine_class}', asset_evidence, review_path.parent,
            carla.Transform(carla.Location(x=engineering['start_x_m'], y=4, z=.5),
                            carla.Rotation(yaw=0)))
        shutil.copyfile(review_path, output / 'electric-asset-review.json')
        for relative, expected_sha in asset_binding['review_source_sha256'].items():
            source = review_path.parent / relative
            destination = output / 'electric-asset-sources' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if hashlib.sha256(destination.read_bytes()).hexdigest() != expected_sha:
                raise RuntimeError('Reviewed electric asset source changed while copying')
        _write_json_new(output / 'electric-asset-binding.json', asset_binding)"""
    runner = replace_once(runner, old_spawn, new_spawn)
    runner = runner.replace("'bicycle_blueprint': ego.type_id", "'reviewed_machine_blueprint': ego.type_id")
    runner = runner.replace("'ru.bicycle': {'native_actor_id': ego.id, 'native_blueprint': ego.type_id,\n                                   'native_body_xy_m': body},",
                            "'ru.bicycle': {'native_actor_id': ego.id, 'native_blueprint': ego.type_id,\n                                   'selected_class': False, 'native_body_xy_m': body},")
    selected = f"'ru.{machine_class}': {{'native_actor_id': ego.id,\n                                            'native_blueprint': ego.type_id,\n                                            'selected_class': False}}"
    runner = replace_once(runner, selected, selected.replace("'selected_class': False", "'selected_class': True"))
    file_map["runner.py"]["content"] = runner
    file_map["electric_asset.py"] = {"path": "electric_asset.py", "content": (ROOT / "native/electric_asset.py").read_text()}
    file_map["tests/test_electric_asset_source.py"] = {"path": "tests/test_electric_asset_source.py", "content": f'''import hashlib
import tempfile
import unittest
from pathlib import Path
from electric_asset import bind_reviewed_asset

MACHINE = "{machine_class}"
LEGAL = {list(__import__('runpy').run_path(str(ROOT / 'native/electric_asset.py'))['LEGAL_CLASS_SOURCES'][machine_class])!r}

class Blueprint:
    id = "vehicle.example.reviewed_electric"

class Library:
    def filter(self, value):
        return [Blueprint()] if value == Blueprint.id else []

class AssetSource(unittest.TestCase):
    def test_exact_review_and_source_hash(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            source = Path(folder) / "survey.json"
            source.write_text('{{"device_class": "reviewed fixture"}}\\n')
            evidence = {{"machine_class": MACHINE, "blueprint_id": Blueprint.id,
                        "source_kind": "reviewed_native_asset", "reviewer": "fixture reviewer",
                        "class_review": {{"legal_sources": LEGAL, "reviewer": "fixture reviewer",
                                         "conclusion": MACHINE}},
                        "source_refs": [{{"path": source.name,
                                         "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}}]}}
            bound = bind_reviewed_asset(Library(), MACHINE, evidence, Path(folder))
            self.assertTrue(bound["classification_review_pending"])
            self.assertFalse(bound["legal_verdict_claimed"])
            source.write_text('changed\\n')
            with self.assertRaises(ValueError):
                bind_reviewed_asset(Library(), MACHINE, evidence, Path(folder))
            evidence["blueprint_id"] = "vehicle.bh.crossbike"
            with self.assertRaises(ValueError):
                bind_reviewed_asset(Library(), MACHINE, evidence, Path(folder))
'''}

    config = json.loads(file_map["config.json"]["content"])
    config["case_id"] = new_case_id
    config["selected_case_id"] = new_case_id
    config["case"]["case_id"] = new_case_id
    config["supported_case_ids"] = [new_case_id]
    config["machine_class"] = machine_class
    config["mandatory_channels"] = [f"ru.{machine_class}", "ru.rider_posture"]
    # The pinned Core adapter has no acquisition path for either electric atom.
    # Keep the class in mandatory source channels and saved measurements instead.
    config["required_atoms"] = [a for a in config["required_atoms"] if a != "ru.bicycle"]
    config["asset_review_source"] = "C104538_ELECTRIC_ASSET_REVIEW"
    config["physical_asset_status"] = "reviewed_source_required_at_native_capture"
    for channel in config["recording_description"]["channels"]:
        if channel["name"] == "ru.bicycle":
            channel["method"] = "Reviewed electric asset source and original pixels leave ordinary bicycle unselected"
        elif channel["name"] == f"ru.{machine_class}":
            channel["method"] = f"Reviewed exact Native {machine_class} asset, actor identity and original machine pixels"
        elif channel["name"] in ("ru.electric_bicycle", "ru.electric_scooter"):
            channel["method"] = f"Class review and original pixels leave this alternative unselected in the {machine_class} case"
    config["recording_description"]["limitations"] = [
        "Reviewed exact electric asset is required at Native capture",
        "Asset identity alone does not prove mounted rider posture or original class pixels",
        "Requested turn does not prove physical movement or a legal outcome",
    ]
    file_map["config.json"]["content"] = json.dumps(config, indent=2, sort_keys=True) + "\n"
    finalizer = file_map["finalize.py"]["content"]
    finalizer = finalizer.replace('r["machine_class"] != "bicycle"',
                                  'r["machine_class"] != config["machine_class"]')
    finalizer = finalizer.replace('"blueprint": "vehicle.bh.crossbike"',
                                  '"blueprint": "reviewed_class_specific_native_asset"')
    finalizer = finalizer.replace('"mounted bicycle turns through authored no-U-turn region"',
                                  f'"mounted {machine_class} turns through authored no-U-turn region"')
    finalizer = finalizer.replace('"""Saved-only C104538 mounted-bicycle diagnostic; never a legal finding."""',
                                  f'"""Saved-only C104538 {machine_class} diagnostic; never a legal finding."""')
    asset_check = '''    asset_review = root / "electric-asset-review.json"
    asset_binding = root / "electric-asset-binding.json"
    for source in (asset_review, asset_binding):
        if seal.get("sources", {}).get(source.name) != sha(source):
            raise ValueError("Original reviewed electric asset seal differs")
    bound = json.loads(asset_binding.read_text())
    review_asset = json.loads(asset_review.read_text())
    if (bound.get("machine_class") != config["machine_class"] or
            bound.get("blueprint_id") != review_asset.get("blueprint_id") or
            bound.get("classification_review_record_bound") is not True or
            bound.get("legal_verdict_claimed") is not False or
            review_asset.get("source_kind") != "reviewed_native_asset" or
            not review_asset.get("reviewer")):
        raise ValueError("Reviewed electric class binding differs")
    for relative, expected_sha in bound.get("review_source_sha256", {}).items():
        source = root / "electric-asset-sources" / relative
        if (seal.get("sources", {}).get(str(source.relative_to(root))) != sha(source) or
                sha(source) != expected_sha):
            raise ValueError("Reviewed electric asset evidence source differs")
    if not bound.get("review_source_sha256"):
        raise ValueError("Reviewed electric asset evidence missing")
'''
    finalizer = replace_once(finalizer, '    from measure_geometry import measure\n',
                             asset_check + '    from measure_geometry import measure\n')
    finalizer = finalizer.replace('"blueprint": "reviewed_class_specific_native_asset"',
                                  '"blueprint": (json.loads((root / "electric-asset-binding.json").read_text())["blueprint_id"] if original_mode else "synthetic_class_join_only")')
    finalizer = finalizer.replace('"body_xy_m": n["native_body_xy_m"]}',
                                  '"body_xy_m": n["native_body_xy_m"], "selected_class": False}', 1)
    finalizer = replace_once(finalizer, '    if original_mode:\n        report["review_source_sha256"]',
                             '    observation = "dismounted_turn_observation" if kind == "dismounted_turn" else "mounted_turn_observation"\n'
                             '    report["measurements"][observation]["value"]["machine_class"] = config["machine_class"]\n'
                             '    report["measurements"][observation]["value"]["reviewed_electric_asset_bound"] = original_mode\n'
                             '    if original_mode:\n        report["review_source_sha256"]')
    file_map["finalize.py"]["content"] = finalizer
    construction["files"] = list(file_map.values())
    construction["case_id"] = new_case_id
    construction["recording_description"] = config["recording_description"]
    construction["measurement_plan"]["method"] = (
        f"reviewed Native {machine_class} asset and original rider/sign/geometry review")
    construction["measurement_plan"]["status"] = "unselected_asset_and_original_native_pending"
    construction["mechanisms"] = [f"reviewed exact {machine_class} blueprint at Native capture"
                                   if mechanism == "exact bicycle blueprint" else mechanism
                                   for mechanism in construction["mechanisms"]]
    construction["status"] = "unselected_electric_native_capture_draft"
    return construction


def main() -> None:
    entries = []
    for machine_class in CLASSES:
        for source_case, behavior in BEHAVIORS:
            selected = {}
            for candidate in ("primary", "fallback1"):
                construction = build(machine_class, source_case, behavior, candidate)
                destination = ROOT / "electric-drafts" / f"{machine_class}_{behavior}"
                if candidate != "primary":
                    destination = destination / candidate
                destination.mkdir(parents=True, exist_ok=True)
                path = destination / "construction.json"
                path.write_text(json.dumps(construction, indent=2, sort_keys=True) + "\n")
                selected[candidate] = {"construction": str(path.relative_to(ROOT / "electric-drafts")),
                                       "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            entries.append({"case_id": construction["case_id"], **selected["primary"],
                            "candidates": [{"id": "fallback1", **selected["fallback1"]}]})
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "cases": entries, "scope": "unselected_cpu_electric_asset_contract"}
    (ROOT / "electric-drafts/manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
