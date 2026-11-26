"""Build exact source-gated Native bundles without inventing a reviewed site.

The selected local operator must provide the reviewed source packet and its
SHA-256 at capture time. This builder does not select a delivery manifest.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_semantic_proposals import KINDS, recording_description


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
SOURCE_NAMES = (
    "branch_site_preflight.py", "carla_scene_adapter.py", "camera_sources.py",
    "delivery_audit.py", "native_attempt.py", "native_capture_finalize.py",
    "prepare_derived_media.py", "source_tick_capture.py",
    "statutory_branch_measurement.py", "through_traffic_control.py",
    "yield_control.py", "analysis.py", "saved_finalizer.py",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(kind: str, candidate: str = "primary") -> dict:
    if kind not in KINDS:
        raise ValueError("unknown exact statutory case")
    if candidate not in ("primary", "fallback1"):
        raise ValueError("unknown engineering candidate")
    case_id = ASSIGNMENT + "__" + kind
    donor = json.loads((HERE / ("construction-compatibility-" + kind + ".json")).read_text())
    if donor.get("case_id") != case_id or donor.get("diagnostic_only") is not True:
        raise ValueError("diagnostic source donor identity changed")
    files = {row["path"]: row["content"] for row in donor["files"]}
    files.pop("diagnostic-site.json", None)
    files.pop("review-context.json", None)
    files["runner.py"] = (HERE / "deferred_source_runner.py").read_text()
    files["case-plan.json"] = (HERE / "case-plan.json").read_text()
    for name in SOURCE_NAMES:
        files[name] = (HERE / name).read_text()
    config = json.loads(files["config.json"])
    config["selected_case_id"] = case_id
    config["case"]["kind"] = kind
    config["candidate_target_speed_mps"] = 4.0 if candidate == "primary" else 3.5
    files["config.json"] = json.dumps(config, indent=2, sort_keys=True) + "\n"
    scene = json.loads(files["scene.json"])
    scene.update({
        "case_id": case_id,
        "kind": kind,
        "source_kind": "local_review_required",
        "case_plan_sha256": _sha(files["case-plan.json"].encode()),
        "site_source_status": "local_source_hash_required_before_native_capture",
    })
    scene.pop("review_source", None)
    scene.pop("review_sha256", None)
    scene.pop("capture_geometry", None)
    files["scene.json"] = json.dumps(scene, indent=2, sort_keys=True) + "\n"
    test = '''import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner


class DeferredSourceBundleTests(TestCase):
    def test_bundle_identity(self):
        self.assertTrue(runner.check()["case_id"].endswith("__" +
                        runner.check()["kind"]))

    def test_original_source_required_before_carla_import(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "attempt"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "source-hashed reviewed"):
                    runner.main()
'''
    files["tests/test_bundle.py"] = test
    donor["diagnostic_only"] = False
    donor["recording_description"] = recording_description()
    donor["files"] = [{"path": name, "content": content}
                      for name, content in sorted(files.items())]
    target = HERE / "cases" / kind / (
        "construction-source-gated.json" if candidate == "primary" else
        "fallback1/construction-source-gated.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(donor, ensure_ascii=False, indent=2) + "\n").encode()
    if len(encoded) > 2 * 1024 * 1024:
        raise ValueError("source-gated construction exceeds returned file limit")
    target.write_bytes(encoded)
    return {"case_id": case_id, "candidate": candidate,
            "construction": str(target.relative_to(HERE)),
            "sha256": _sha(encoded), "bytes": len(encoded)}


if __name__ == "__main__":
    result = [build(kind, candidate) for kind in KINDS
              for candidate in ("primary", "fallback1")]
    print(json.dumps({"cases": len(KINDS), "candidates": len(result),
                      "constructions": result}, indent=2))
