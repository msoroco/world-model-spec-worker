"""Independent comparison audit for retained Native, audio and dispatch sources."""
import json
from pathlib import Path

from measure import rows, sha
from source_acquisition import measure_with_original_sources

FILES = ("config.json", "native.jsonl", "video_frames.jsonl", "dispatch.jsonl",
         "microphone.wav", "audio_observations.jsonl", "dispatch-source.json")
PAIRS = {
    "call_vs_ordinary_siren": ("probe_a", "probe_b", set(),
                               {"emergency_call_documented"}),
    "call_vs_pursuit_siren": ("probe_a", "pursuit", set(),
                              {"emergency_call_documented",
                               "immediate_pursuit_documented"}),
    "call_siren_vs_lamps_only": ("probe_a", "call_lamps_only",
                                  {"siren_observed"}, set()),
    "call_vs_ordinary_lamps_only": ("call_lamps_only",
                                    "ordinary_lamps_only", set(),
                                    {"emergency_call_documented"}),
}


def sources(root):
    root = Path(root)
    return tuple(root / name for name in FILES)


def _without(row, keys):
    return {key: value for key, value in row.items() if key not in keys}


def audit(pair_id, first_root, second_root):
    if pair_id not in PAIRS:
        raise ValueError("Unknown exact C109028 comparison")
    a_name, b_name, permitted_native, permitted_dispatch = PAIRS[pair_id]
    first, second = sources(first_root), sources(second_root)
    a = measure_with_original_sources(*first)
    b = measure_with_original_sources(*second)
    ca, cb = json.loads(first[0].read_text()), json.loads(second[0].read_text())
    if (not ca["case_id"].endswith("__" + a_name) or
            not cb["case_id"].endswith("__" + b_name)):
        raise ValueError("Exact comparison identities differ")
    different_config = {"case_id", "emergency_call_requested",
                        "immediate_pursuit_requested", "siren_requested"}
    if _without(ca, different_config) != _without(cb, different_config):
        raise ValueError("Fixed construction differs")
    an, bn = rows(first[1]), rows(second[1])
    am, bm = rows(first[2]), rows(second[2])
    ad, bd = rows(first[3]), rows(second[3])
    if am != bm:
        raise ValueError("Fixed video/frame map differs")
    if any(_without(x, permitted_native) != _without(y, permitted_native)
           for x, y in zip(an, bn)):
        raise ValueError("Fixed Native motion or signal source differs")
    if any(_without(x, permitted_dispatch | {"document_sha256"}) !=
           _without(y, permitted_dispatch | {"document_sha256"})
           for x, y in zip(ad, bd)):
        raise ValueError("Fixed dispatch records differ")
    if not permitted_native and sha(first[4]) != sha(second[4]):
        raise ValueError("Fixed microphone source differs")
    if not permitted_native and rows(first[5]) != rows(second[5]):
        raise ValueError("Fixed independent audio observations differ")
    if permitted_native and sha(first[4]) == sha(second[4]):
        raise ValueError("Siren contrast lacks distinct audio source")
    if pair_id == "call_vs_ordinary_siren":
        if not (a["siren_observed_frames"] == b["siren_observed_frames"] > 0 and
                a["siren_outside_documented_response_frames"] == 0 and
                b["siren_outside_documented_response_frames"] ==
                b["siren_observed_frames"]):
            raise ValueError("Call versus ordinary siren contrast differs")
    elif pair_id == "call_vs_pursuit_siren":
        if not (a["siren_observed_frames"] == b["siren_observed_frames"] > 0 and
                a["siren_outside_documented_response_frames"] == 0 and
                b["siren_outside_documented_response_frames"] == 0):
            raise ValueError("Call versus pursuit contrast differs")
    elif pair_id == "call_siren_vs_lamps_only":
        if not (a["siren_observed_frames"] > 0 and b["siren_observed_frames"] == 0 and
                a["warning_lamp_observed_frames"] ==
                b["warning_lamp_observed_frames"] > 0):
            raise ValueError("Siren versus lamps-only contrast differs")
    else:
        if not (a["siren_observed_frames"] == b["siren_observed_frames"] == 0 and
                a["warning_lamp_observed_frames"] ==
                b["warning_lamp_observed_frames"] > 0):
            raise ValueError("Call versus ordinary lamps-only contrast differs")
    return {"format": "c109028-original-source-comparison-audit-v1",
            "comparison_id": pair_id, "passed": True,
            "case_ids": [a["case_id"], b["case_id"]],
            "frames_per_case": 600,
            "siren_frames": [a["siren_observed_frames"], b["siren_observed_frames"]],
            "outside_response_frames": [a["siren_outside_documented_response_frames"],
                                        b["siren_outside_documented_response_frames"]],
            "source_hashes": {a_name: {name: sha(path) for name, path in zip(FILES, first)},
                              b_name: {name: sha(path) for name, path in zip(FILES, second)}},
            "physical_legal_verdict": None}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=sorted(PAIRS), required=True)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.comparison, args.first, args.second)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "comparison": args.comparison}))


if __name__ == "__main__":
    main()
