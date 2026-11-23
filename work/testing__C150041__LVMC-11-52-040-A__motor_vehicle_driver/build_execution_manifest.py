"""Build six exact parking delivery constructions without fixture review bytes.

The construction is CPU-testable, but remains partial until a genuine reviewed
Native site packet replaces the compatibility fixture and delivery proofs pass.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parking_pose import REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    draft = json.loads((ROOT / "native-draft-manifest.json").read_text())
    compatibility = json.loads((ROOT / "cpu-compatibility-manifest.json").read_text())
    planned = json.loads((ROOT / "case-plan.json").read_text())
    expected = {ROOT.name + "__" + kind for kind in REQUESTS}
    drafts = {entry["case_id"]: entry for entry in draft["cases"]}
    contracts = {entry["case_id"]: entry for entry in compatibility["cases"]}
    if (set(drafts) != expected or set(contracts) != expected or
            {entry["case_id"] for entry in planned["cases"]} != expected):
        raise ValueError("six exact parking case inventories differ")
    previous_path = ROOT / "execution-manifest.json"
    previous = json.loads(previous_path.read_text()) if previous_path.is_file() else {}
    prior = {entry["case_id"]: entry for entry in previous.get("cases", [])}
    cases = []
    for kind in REQUESTS:
        case = ROOT.name + "__" + kind
        folder = ROOT / "diagnostic" / kind
        native, contract = drafts[case], contracts[case]
        constructions = []
        for candidate, name in ((native, "construction-delivery.json"),
                                (native["candidates"][0], "construction-delivery-fallback1.json")):
            source = ROOT / candidate["construction"]
            if sha(source) != candidate["construction_sha256"]:
                raise ValueError("Native draft changed: " + case)
            package = json.loads(source.read_text())
            files = package["files"]
            if not any(item["path"] == "runner.py" and
                       "parking_runner import main" in item["content"] for item in files):
                raise ValueError("Native parking runner missing: " + case)
            package["files"] = [item for item in files if
                                item["path"] != "reviewed-context.json" and
                                not item["path"].startswith("reviewed_sources/")]
            kind_arg = kind
            approach_arg = (', "--approach-distance-m", "6.0"'
                            if name.endswith("fallback1.json") else '')
            wrapper = ('"""External reviewed-packet Native parking entrypoint."""\n'
                       'import json\nfrom pathlib import Path\nimport sys\n'
                       'from parking_runner import check_materialized_package, main\n'
                       'if __name__ == "__main__":\n'
                       '    if "--check" in sys.argv:\n'
                       '        if Path("reviewed-context.json").exists():\n'
                       '            raise ValueError("delivery draft embeds a review packet")\n'
                       '        check_materialized_package(Path.cwd(), '
                       'json.loads(Path("scene.json").read_text()))\n'
                       '        print("external reviewed packet required for Native execution")\n'
                       '    else:\n'
                       '        sys.argv.extend(["--packet", "reviewed-context.json", '
                       '"--source-root", ".", "--case", "' + kind_arg + '"' +
                       approach_arg + '])\n'
                       '        main()\n')
            for item in package["files"]:
                if item["path"] == "runner.py":
                    item["content"] = wrapper
                if item["path"] == "tests/test_offline.py":
                    item["path"] = "tests/test_delivery_offline.py"
                    item["source"] = str((ROOT / "delivery_offline_test.py").relative_to(REPO))
                    item["content"] = (ROOT / "delivery_offline_test.py").read_text()
            package["source_kind"] = "worker_native_construction_pending_reviewed_site_packet"
            destination = folder / name
            write(destination, package)
            constructions.append(destination)
        primary, fallback = constructions
        entry = {"case_id": case, "kind": "delivery",
                 "construction": primary.relative_to(ROOT).as_posix(),
                 "construction_sha256": sha(primary),
                 "measurement_contract": contract["measurement_contract"],
                 "measurement_procedure": contract["measurement_procedure"],
                 "fixture_recipe": contract["fixture_recipe"],
                 "candidate_risk": native["candidate_risk"],
                 "candidates": [{**native["candidates"][0],
                                 "construction": fallback.relative_to(ROOT).as_posix(),
                                 "construction_sha256": sha(fallback)}],
                 "preparation_status": "partial_reviewed_site_and_delivery_pending"}
        old = prior.get(case, {})
        if old.get("construction_sha256") == entry["construction_sha256"]:
            for key in ("offline", "compatibility", "physical_preparation",
                        "post_capture", "delivery_acceptance", "acquisition", "native_handoff"):
                if key in old:
                    entry[key] = old[key]
            old_fallback = old.get("candidates", [{}])[0]
            if old_fallback.get("construction_sha256") == entry["candidates"][0]["construction_sha256"]:
                for key in ("offline", "compatibility"):
                    if key in old_fallback:
                        entry["candidates"][0][key] = old_fallback[key]
        cases.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": ROOT.name,
                "runtime_manifest_sha256": compatibility["runtime_manifest_sha256"],
                "preparation_status": "partial_reviewed_site_and_delivery_pending",
                "cases": cases}
    write(previous_path, manifest)
    return previous_path


if __name__ == "__main__":
    print(build())
