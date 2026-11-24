"""Independent CPU shape audit of the four selected joint judgment probes.

The fixture's source-kind labels are synthetic inputs, never evidence that an
original Native, acoustic, or incident source has been acquired.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
POINTS = ((500, 10), (500, 20), (600, 10), (600, 20))


def rows(value):
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def center(vertices):
    return sum(vertex[0] for vertex in vertices) / len(vertices)


def audit(specs):
    if len(specs) != 4:
        raise ValueError("Four exact joint sweep sources required")
    fixed = None
    source_hashes = {}
    for i, (spec, (distance, approach)) in enumerate(zip(specs, POINTS)):
        files = spec["files"]
        for key in ("native_samples.jsonl", "video_frames.jsonl",
                    "microphone-pcm16.json", "acoustic-report.json",
                    "dispatch.jsonl", "audio_observations.jsonl"):
            if key not in files:
                raise ValueError("Missing original-source-shaped input: " + key)
        native = rows(files["native_samples.jsonl"])
        frames = rows(files["video_frames.jsonl"])
        dispatch = rows(files["dispatch.jsonl"])
        audio = rows(files["audio_observations.jsonl"])
        report = json.loads(files["acoustic-report.json"])
        pcm = files["microphone-pcm16.json"].encode()
        if len(native) != len(frames) or len(native) != len(dispatch) or len(native) != len(audio) or len(native) != 600:
            raise ValueError("Incomplete 600-frame original-source join")
        if report.get("distance_ft") != distance or report.get("audibility_assessment") != "uncertain":
            raise ValueError("Observer distance or acoustic uncertainty changed")
        if report.get("source_audio_sha256") != hashlib.sha256(pcm).hexdigest():
            raise ValueError("Acoustic report is not bound to the audio source")
        measured = 50 - center(native[0]["other"]["body_vertices_m"])
        if abs(measured - approach) > 1e-9:
            raise ValueError("Other vehicle approach geometry differs")
        identity = [(n["native_frame"], n["time_s"], n["ego"]["center_xy_m"])
                    for n in native]
        invariant = (identity, [f["native_frame"] for f in frames],
                     [d.get("documented_emergency_call") for d in dispatch],
                     [a.get("siren_audible") for a in audio])
        if fixed is None:
            fixed = invariant
        elif invariant != fixed:
            raise ValueError("Fixed ego, frame, dispatch, or siren source differs")
        source_hashes[f"sweep_{i}"] = {key: hashlib.sha256(value.encode()).hexdigest()
                                       for key, value in files.items() if key in
                                       ("native_samples.jsonl", "video_frames.jsonl",
                                        "microphone-pcm16.json", "acoustic-report.json")}
    return {"format": "c109028-joint-sweep-cpu-audit-v1", "passed": True,
            "points": [{"observer_distance_ft": a, "other_approach_distance_m": b}
                       for a, b in POINTS], "frames_per_case": 600,
            "source_hashes": source_hashes, "synthetic_fixture_only": True,
            "physical_legal_verdict": None}


def main():
    specs = [json.loads((HERE / "selected-fixture" / f"sweep_{i}" /
                         "diagnostic.json").read_text()) for i in range(4)]
    positive = audit(specs)
    negatives = []
    for index, mutate, expected in (
            (0, lambda s: s["files"].pop("acoustic-report.json"),
             "Missing original-source-shaped input"),
            (1, lambda s: s["files"].__setitem__("acoustic-report.json",
                 s["files"]["acoustic-report.json"].replace('"distance_ft": 500', '"distance_ft": 501')),
             "Observer distance"),
            (2, lambda s: s["files"].__setitem__("native_samples.jsonl",
                 s["files"]["native_samples.jsonl"].replace('"center_xy_m": [5.1, 0.0]',
                                                               '"center_xy_m": [5.2, 0.0]', 1)),
             "Fixed ego")):
        damaged = json.loads(json.dumps(specs))
        mutate(damaged[index])
        try:
            audit(damaged)
        except ValueError as exc:
            if expected not in str(exc):
                raise
            negatives.append(str(exc))
        else:
            raise AssertionError("Mutated joint sweep source accepted")
    proof = {"positive": positive, "negative_rejections": negatives}
    (HERE / "native/joint-sweep-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"positive": True, "negative_rejections": len(negatives)}))


if __name__ == "__main__":
    main()
