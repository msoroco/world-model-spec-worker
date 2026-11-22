import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import (ORIGINALS, REVIEW_SOURCES, audit_attempt, audit_pair,
                            audit_reviewed_context, sha)
from test_analysis import fixture


def native_shaped_fixture(folder):
    folder = Path(folder)
    fixture(folder)
    context_path = folder / "intersection-context.json"
    context = json.loads(context_path.read_text())
    context["law_context"]["map_source"] = hashlib.sha256(b"map").hexdigest()
    for key, relative in REVIEW_SOURCES.items():
        source = folder / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("synthetic retained " + key)
        context["law_context"][key] = {"source_path": key + ".txt",
                                       "source_sha256": sha(source),
                                       "reviewer": "fixture",
                                       "source_citation": "fixture only"}
    reviewed = {key: context[key] for key in ("crossing", "law_context")}
    (folder / "reviewed-context.json").write_text(json.dumps(reviewed))
    context["reviewed_context_sha256"] = sha(folder / "reviewed-context.json")
    context_path.write_text(json.dumps(context))
    (folder / "road.xodr").write_text("map")
    for name in ("trace.jsonl", "video_frames.jsonl", "carla_recorder.log",
                 "controller-history.jsonl", "overview.mkv", "approach.mkv",
                 "reference_corner.mkv", "driver_reference.mkv"):
        (folder / name).write_text("diagnostic placeholder")
    (folder / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "reviewed_context_sha256": sha(folder / "reviewed-context.json")}))
    hashes = {name: sha(folder / name) for name in ORIGINALS}
    (folder / "acquisition.json").write_text(json.dumps({
        name: {"kind": "original_native", "sha256": value} for name, value in hashes.items()}))
    seal = {"format": "worker-sealed-capture", "events": [
        "capture_finished", "encoders_closed", "restoration_verified"],
        "restoration": {"restored": True},
        "encoder_exit_codes": {name.removesuffix(".mkv"): 0 for name in ORIGINALS if name.endswith(".mkv")},
        "sources": hashes}
    (folder / "capture-seal.json").write_text(json.dumps(seal))
    (folder / "native-exit.json").write_text(json.dumps({
        "event": "native_exit", "capture_seal_sha256": sha(folder / "capture-seal.json"),
        "native_process_exit_code": 0, "capture_command_failed": False}))


class DeliveryAuditTests(unittest.TestCase):
    def test_source_bound_diagnostic_shape_and_tamper_rejection(self):
        with TemporaryDirectory() as tmp:
            native_shaped_fixture(tmp)
            observed = audit_attempt(tmp, diagnostic=True)
            self.assertTrue(observed["measurements"]["other_entered_before_ego"])
            self.assertFalse(observed["physical_acceptance_claimed"])
            with self.assertRaisesRegex(ValueError, "original Native acquisition required"):
                audit_attempt(tmp)
            (Path(tmp) / "other-body-history.jsonl").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "source missing or changed"):
                audit_attempt(tmp, diagnostic=True)

    def test_pair_requires_realized_declared_difference(self):
        with TemporaryDirectory() as left, TemporaryDirectory() as right:
            native_shaped_fixture(left)
            native_shaped_fixture(right)
            with self.assertRaisesRegex(ValueError, "did not differ"):
                audit_pair(left, right, ["entry_order"], diagnostic=True)

    def test_reviewed_packet_cannot_be_reseated_on_another_map_or_scene(self):
        with TemporaryDirectory() as tmp:
            native_shaped_fixture(tmp)
            root = Path(tmp)
            self.assertEqual(audit_reviewed_context(root)["original_map_sha256"],
                             sha(root / "road.xodr"))
            context_path = root / "intersection-context.json"
            context = json.loads(context_path.read_text())
            context["law_context"]["public_access"] = False
            context_path.write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "differs from original scene"):
                audit_reviewed_context(root)
            context["law_context"]["public_access"] = True
            context_path.write_text(json.dumps(context))
            (root / "road.xodr").write_text("different map")
            with self.assertRaisesRegex(ValueError, "differs from original OpenDRIVE"):
                audit_reviewed_context(root)

    def test_retained_review_source_tamper_rejected(self):
        with TemporaryDirectory() as tmp:
            native_shaped_fixture(tmp)
            root = Path(tmp)
            source = root / REVIEW_SOURCES["device_inventory_source"]
            source.write_text("changed retained inventory")
            with self.assertRaisesRegex(ValueError, "device_inventory_source original bytes"):
                audit_reviewed_context(root)
            with self.assertRaisesRegex(ValueError, "original source missing or changed"):
                audit_attempt(root, diagnostic=True)


if __name__ == "__main__": unittest.main()
