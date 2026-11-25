"""CPU proof of fail-closed original-device acquisition interfaces."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULE = HERE / "native/native_request.py"
spec = importlib.util.spec_from_file_location("native_request", MODULE)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def reject(fn, fragment):
    try:
        fn()
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"wrong rejection: {exc}") from exc
        return str(exc)
    raise AssertionError("malformed original source accepted")


class Controller:
    def __init__(self):
        self.commanded = None
        self.observed = None

    def command(self, device_id, state):
        self.commanded = device_id, state

    def observe(self, device_id):
        return self.observed


def main():
    controller = Controller()
    row = native.request("probe_02", 100)
    controller.observed = {
        "source_kind": "native_device_readback", "device_id": row["device_id"],
        "displayed_instruction": row["device_display_request"],
        "native_frame": 100, "source_ref": "device-face-camera/frame-100",
    }
    observed = native.apply_device_and_readback(controller, "probe_02", 100)
    assert controller.commanded == (row["device_id"], "diagonal_dont_walk")
    assert observed["official_status_verified"] is False
    failures = {}
    for label, change, fragment in (
        ("request_echo", {"source_kind": "authored_native_request"}, "original Native"),
        ("wrong_head", {"device_id": "other"}, "identity differs"),
        ("wrong_display", {"displayed_instruction": "diagonal_walk"}, "instruction differs"),
        ("stale_frame", {"native_frame": 99}, "frame/source"),
        ("missing_source", {"source_ref": ""}, "frame/source"),
    ):
        controller.observed = dict(controller.observed, **change)
        failures[label] = reject(lambda: native.apply_device_and_readback(controller, "probe_02", 100), fragment)
        controller.observed = dict(controller.observed, **{key: observed.get(key, row.get(key)) for key in change})
        controller.observed.update({"native_frame": 100, "source_ref": "device-face-camera/frame-100",
                                    "device_id": row["device_id"], "displayed_instruction": row["device_display_request"],
                                    "source_kind": "native_device_readback"})
    scratch = ROOT / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        folder = Path(temp)
        receipt = {}
        for name in ("authorization", "official_status", "movement_applicability"):
            path = folder / (name + ".json")
            path.write_text(json.dumps({"synthetic_test_source": name}) + "\n")
            receipt[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "device_id": "c109166-planned-diagonal-head",
                             "movement_id": "c109166-287-1d-diagonal-sw-ne",
                             "review_status": "pending_independent_review"}
        proof = native.verify_authority_sources(folder, receipt)
        assert not any(v for k, v in proof.items() if k.endswith("verified"))
        trial = json.loads(json.dumps(receipt))
        del trial["authorization"]
        failures["missing_authorization"] = reject(lambda: native.verify_authority_sources(folder, trial), "three independent")
        trial = json.loads(json.dumps(receipt))
        trial["official_status"]["sha256"] = "0" * 64
        failures["stale_source_hash"] = reject(lambda: native.verify_authority_sources(folder, trial), "hash differs")
        trial = json.loads(json.dumps(receipt))
        trial["movement_applicability"]["device_id"] = "other"
        failures["wrong_device"] = reject(lambda: native.verify_authority_sources(folder, trial), "another device")
        trial = json.loads(json.dumps(receipt))
        trial["authorization"]["path"] = "../outside.json"
        failures["escaping_path"] = reject(lambda: native.verify_authority_sources(folder, trial), "escapes attempt")
        trial = json.loads(json.dumps(receipt))
        trial["authorization"]["review_status"] = "verified"
        failures["self_asserted_authority"] = reject(lambda: native.verify_authority_sources(folder, trial), "cannot assert")
        trial = json.loads(json.dumps(receipt))
        trial["authorization"]["path"] = trial["official_status"]["path"]
        trial["authorization"]["sha256"] = trial["official_status"]["sha256"]
        failures["reused_source_bytes"] = reject(lambda: native.verify_authority_sources(folder, trial), "identical bytes")
        failures["synthetic_capture_gate"] = reject(
            lambda: native.authorize_native_capture(folder, receipt, "candidate-unverified-203"),
            "original independently reviewed")
        claims = {"authorization": "diagonal_crossing_authorized",
                  "official_status": "official_device",
                  "movement_applicability": "governs_exact_diagonal_movement"}
        reviewed = json.loads(json.dumps(receipt))
        for name, claim in claims.items():
            media = folder / (name + ".png")
            media.write_bytes(("synthetic CPU test of " + name).encode())
            document = {"provenance_kind": "original_survey",
                        "review_status": "independently_reviewed",
                        "independent_reviewer": "synthetic CPU reviewer",
                        "native_head_id": "candidate-unverified-203",
                        "device_id": "c109166-planned-diagonal-head",
                        "movement_id": "c109166-287-1d-diagonal-sw-ne", claim: True,
                        "original_survey_media": {"path": media.name,
                                                  "sha256": hashlib.sha256(media.read_bytes()).hexdigest()}}
            path = folder / reviewed[name]["path"]
            path.write_text(json.dumps(document) + "\n")
            reviewed[name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        assert native.authorize_native_capture(folder, reviewed, "candidate-unverified-203")["capture_authorized"]
        failures["wrong_surveyed_head"] = reject(
            lambda: native.authorize_native_capture(folder, reviewed, "different-head"),
            "original independently reviewed")
        (folder / "authorization.png").write_bytes(b"modified synthetic media")
        failures["stale_survey_media"] = reject(
            lambda: native.authorize_native_capture(folder, reviewed, "candidate-unverified-203"),
            "survey media hash differs")
    output = {"format": "c109166-device-authority-interface-cpu-proof-v1",
              "module_sha256": hashlib.sha256(MODULE.read_bytes()).hexdigest(),
              "tested_original_readback_api": True, "tested_source_provenance_api": True,
              "tested_pre_capture_independent_survey_gate": True,
              "rejections": failures, "native_executed": False,
              "original_authority_sources_available": False,
              "official_status_verified": False, "diagonal_authorization_verified": False}
    (HERE / "device-authority-proof.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output))


if __name__ == "__main__":
    main()
