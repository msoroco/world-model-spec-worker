"""Exercise source comparison logic on synthetic shapes, never physical evidence."""
import json
import tempfile
import wave
from pathlib import Path

from audit_original import PAIRS, audit
from prove import BRANCHES, make_source, write_rows
from source_acquisition import sha

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[2] / ".runtime-work"


def wav_file(path, sounding):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(48000)
        stream.writeframes((b"\xe8\x03" if sounding else b"\0\0") *
                           (48000 * 30))


def prepare(root, branch):
    files = make_source(root, branch)
    native = [json.loads(line) for line in files[1].read_text().splitlines()]
    dispatch = [json.loads(line) for line in files[3].read_text().splitlines()]
    mapping = [json.loads(line) for line in files[2].read_text().splitlines()]
    for row in native:
        row["source_kind"] = "original_native"
    # This is a synthetic shape test. A source-kind label in the temporary
    # fixture does not assert any original acquisition occurred.
    write_rows(files[1], native)
    document = root / "dispatch-source.json"
    document.write_text(json.dumps({"synthetic_fixture": True,
                                    "branch": branch}) + "\n")
    for row in dispatch:
        row["source_kind"] = "original_dispatch_record"
        row["document_sha256"] = sha(document)
    write_rows(files[3], dispatch)
    wav = root / "microphone.wav"
    wav_file(wav, BRANCHES[branch]["siren"])
    observations = []
    for state, frame in zip(native, mapping):
        observations.append({"source_kind": "independent_microphone_review",
                             "audio_sha256": sha(wav),
                             "native_frame": frame["native_frame"],
                             "time_s": frame["time_s"],
                             "reviewer": "synthetic fixture only",
                             "siren_audible": state["siren_observed"]})
    write_rows(root / "audio_observations.jsonl", observations)


def reject(call, expected):
    try:
        call()
    except ValueError as exc:
        if expected not in str(exc):
            raise
        return str(exc)
    raise AssertionError("Invalid original-source comparison was accepted")


def run():
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix="c109028-original-audit-") as folder:
        root = Path(folder)
        for branch in BRANCHES:
            case = root / branch
            case.mkdir()
            prepare(case, branch)
        positive = {name: audit(name, root / pair[0], root / pair[1])
                    for name, pair in PAIRS.items()}
        assert len(positive) == 4 and all(row["passed"] for row in positive.values())
        negatives = {}
        native = root / "probe_b/native.jsonl"
        original = native.read_text()
        native.write_text(original.replace('"ego_x_m": 5.1',
                                           '"ego_x_m": 5.2', 1))
        negatives["changed_motion"] = reject(
            lambda: audit("call_vs_ordinary_siren", root / "probe_a",
                          root / "probe_b"), "Fixed Native motion")
        native.write_text(original)
        observations = root / "pursuit/audio_observations.jsonl"
        original = observations.read_text()
        observations.write_text(original.replace('"audio_sha256": "',
                                                  '"audio_sha256": "0', 1))
        negatives["changed_audio_hash"] = reject(
            lambda: audit("call_vs_pursuit_siren", root / "probe_a",
                          root / "pursuit"), "audio observation/frame join")
        observations.write_text(original)
        document = root / "ordinary_lamps_only/dispatch-source.json"
        document.unlink()
        negatives["missing_dispatch_document"] = reject(
            lambda: audit("call_vs_ordinary_lamps_only",
                          root / "call_lamps_only", root / "ordinary_lamps_only"),
            "Missing original dispatch")
        result = {"format": "c109028-original-source-audit-cpu-fixture-v1",
                  "positive_comparisons": positive, "negatives": negatives,
                  "synthetic_fixture_only": True,
                  "original_native_observed": False,
                  "original_audio_acquired": False,
                  "legal_or_physical_acceptance": False}
    (HERE / "original-audit-cpu-proof.json").write_text(json.dumps(result, indent=2) + "\n")
    return {"comparisons": len(positive), "negatives": len(negatives),
            "physical_claimed": False}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
