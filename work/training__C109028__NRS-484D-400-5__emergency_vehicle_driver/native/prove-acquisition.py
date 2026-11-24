"""CPU fixture for original-source joins; no physical recording is represented."""
import copy
import json
import tempfile
import wave
from pathlib import Path

from source_acquisition import (sha, validate_acoustic_capability,
                                validate_audio, validate_dispatch)

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[2] / ".runtime-work"


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def rejected(command, fragment):
    try:
        command()
    except (ValueError, FileNotFoundError) as exc:
        if fragment not in str(exc):
            raise
        return str(exc)
    raise AssertionError("Invalid source was accepted: " + fragment)


def run():
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix="c109028-acquisition-") as folder:
        root = Path(folder)
        wav = root / "microphone.wav"
        with wave.open(str(wav), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(48000)
            stream.writeframes(b"\0\0" * 48000 * 30)
        document = root / "dispatch-source.json"
        document.write_text(json.dumps({"fixture_only": True,
                                        "source": "synthetic CPU contract test"}) + "\n")
        mapping = root / "video_frames.jsonl"
        audio = root / "audio_observations.jsonl"
        dispatch = root / "dispatch_records.jsonl"
        rows = [{"video_frame": i, "native_frame": i + 1000,
                 "time_s": (i + 1) / 20} for i in range(600)]
        observations = [{"source_kind": "independent_microphone_review",
                         "audio_sha256": sha(wav), "native_frame": row["native_frame"],
                         "time_s": row["time_s"], "reviewer": "synthetic fixture",
                         "siren_audible": 100 <= i < 300}
                        for i, row in enumerate(rows)]
        calls = [{"source_kind": "original_dispatch_record",
                  "document_sha256": sha(document), "native_frame": row["native_frame"],
                  "time_s": row["time_s"], "emergency_call_documented": True,
                  "immediate_pursuit_documented": False}
                 for row in rows]
        write_rows(mapping, rows)
        write_rows(audio, observations)
        write_rows(dispatch, calls)
        first = validate_audio(wav, audio, mapping)
        second = validate_dispatch(dispatch, mapping, document)
        assert first["reviewed_siren_audible_frames"] == 200
        assert second["emergency_call_frames"] == 600
        assert first["audible_at_500_ft_verified"] is False
        assert second["authorized_emergency_vehicle_verified"] is False
        negatives = {}
        changed = copy.deepcopy(observations)
        changed[0]["source_kind"] = "actuator_request"
        write_rows(audio, changed)
        negatives["actuator_is_not_audio"] = rejected(
            lambda: validate_audio(wav, audio, mapping), "audio observation/frame join")
        write_rows(audio, observations)
        changed = copy.deepcopy(observations)
        changed[200]["native_frame"] += 1
        write_rows(audio, changed)
        negatives["audio_frame_mismatch"] = rejected(
            lambda: validate_audio(wav, audio, mapping), "audio observation/frame join")
        write_rows(audio, observations)
        changed = copy.deepcopy(calls)
        changed[0]["document_sha256"] = "0" * 64
        write_rows(dispatch, changed)
        negatives["dispatch_document_mismatch"] = rejected(
            lambda: validate_dispatch(dispatch, mapping, document), "dispatch record/frame join")
        write_rows(dispatch, calls)
        bad_report = root / "acoustic-report.json"
        bad_report.write_text(json.dumps({"distance_ft": 499.99,
            "method": "fixture", "normal_conditions": True,
            "observer": "fixture", "source_audio_sha256": sha(wav),
            "audibility_assessment": "uncertain", "calibration_source": "fixture"}) + "\n")
        negatives["below_500_feet"] = rejected(
            lambda: validate_acoustic_capability(bad_report, wav), "500-foot")
        report = json.loads(bad_report.read_text())
        report["distance_ft"] = 500
        bad_report.write_text(json.dumps(report) + "\n")
        boundary = validate_acoustic_capability(bad_report, wav)
        assert boundary["distance_ft"] == 500
        assert boundary["legal_equipment_conclusion"] is None
        report["distance_ft"] = 500.01
        bad_report.write_text(json.dumps(report) + "\n")
        assert validate_acoustic_capability(bad_report, wav)["distance_ft"] == 500.01
        report["source_audio_sha256"] = "0" * 64
        bad_report.write_text(json.dumps(report) + "\n")
        negatives["acoustic_audio_hash_mismatch"] = rejected(
            lambda: validate_acoustic_capability(bad_report, wav), "500-foot")
        bad_report.unlink()
        document.unlink()
        negatives["missing_dispatch_document"] = rejected(
            lambda: validate_dispatch(dispatch, mapping, document), "Missing original")
        result = {"format": "c109028-acquisition-cpu-fixture-v1",
                  "positive_checks": ["30-second PCM source", "600-frame audio join",
                                      "600-frame dispatch document join",
                                      "500-foot boundary and above with no legal conclusion"],
                  "negatives": negatives, "fixture_only": True,
                  "original_audio_acquired": False,
                  "original_dispatch_acquired": False,
                  "physical_legal_verdict": None}
    (HERE / "acquisition-cpu-proof.json").write_text(json.dumps(result, indent=2) + "\n")
    return {"positive_checks": len(result["positive_checks"]),
            "negatives": len(negatives), "physical_claimed": False}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
