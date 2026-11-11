"""Independent original-source comparison of the paired exception probes."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def _module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


branch = _module("exception_audit_fire_branch", "fire_branch.py")
packets = _module("exception_audit_packet_source", "exception_source_packet_bound.py")


def _read(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing comparison original: " + name)
    return path.read_bytes()


def audit(ordinary, authorized):
    ordinary, authorized = Path(ordinary), Path(authorized)
    shared = ("participant_footprints.jsonl", "participant_state.jsonl",
              "video_frames.jsonl", "trace.jsonl")
    for name in shared:
        if sha256(_read(ordinary, name)).digest() != sha256(_read(authorized, name)).digest():
            raise ValueError("Exception comparison changed fixed original: " + name)
    contexts = [json.loads(_read(root, "fire_context.json")) for root in (ordinary, authorized)]
    left, right = contexts
    fixed = ("alarm_response_source", "apparatus_answered_alarm")
    if any(left[key] != right[key] for key in fixed):
        raise ValueError("Exception comparison changed fire-alarm premise")
    for key in ("subject_authorized_emergency", "subject_official_business"):
        if left[key] is not False or right[key] is not True:
            raise ValueError("Exception comparison lacks the exact ordinary/authorized contrast")
    identities = [json.loads(line) for line in _read(ordinary, "participant_footprints.jsonl").splitlines()]
    if not identities or len({row.get("ego_id") for row in identities}) != 1:
        raise ValueError("Exception comparison lacks one stable subject identity")
    packets.read_exception_source(authorized, right, identities[0]["ego_id"])
    if (ordinary / "subject_exception_source.json").exists():
        raise ValueError("Ordinary comparison case carries an exception assertion")
    count = len(_read(ordinary, "video_frames.jsonl").splitlines())
    measured = [branch.measure_branch(root / "participant_footprints.jsonl",
                                      root / "participant_state.jsonl", count,
                                      "traveling_follow", context)
                for root, context in ((ordinary, left), (authorized, right))]
    if measured[0]["min_boundary_distance_ft"] != measured[1]["min_boundary_distance_ft"]:
        raise ValueError("Exception comparison changed measured distance")
    return {"passed": True, "comparison_id": "authorized_emergency_exception",
            "case_count": 2, "measured_distance_ft": measured[0]["min_boundary_distance_ft"],
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def audit_conjunction(roots):
    """Check each truth-table premise against one fixed physical comparison."""
    expected = {
        "ordinary_police_at499": (False, False),
        "authorized_offduty_at499": (True, False),
        "unauthorized_onduty_at499": (False, True),
        "authorized_police_at499": (True, True),
    }
    if set(roots) != set(expected):
        raise ValueError("Exception conjunction lacks a complete four-case truth table")
    roots = {name: Path(root) for name, root in roots.items()}
    baseline = roots["ordinary_police_at499"]
    source_names = ("participant_footprints.jsonl", "participant_state.jsonl",
                    "video_frames.jsonl", "trace.jsonl")
    baseline_hashes = {name: sha256(_read(baseline, name)).hexdigest() for name in source_names}
    baseline_context = json.loads(_read(baseline, "fire_context.json"))
    baseline_measure = None
    for name, root in roots.items():
        if any(sha256(_read(root, source)).hexdigest() != expected_hash
               for source, expected_hash in baseline_hashes.items()):
            raise ValueError("Exception conjunction changed fixed original: " + name)
        context = json.loads(_read(root, "fire_context.json"))
        if (context["subject_authorized_emergency"], context["subject_official_business"]) != expected[name]:
            raise ValueError("Exception conjunction premise differs: " + name)
        for key in ("alarm_response_source", "apparatus_answered_alarm"):
            if context[key] != baseline_context[key]:
                raise ValueError("Exception conjunction changed alarm premise")
        identity = json.loads(_read(root, "participant_footprints.jsonl").splitlines()[0])["ego_id"]
        if any(expected[name]):
            packets.read_exception_source(root, context, identity)
        elif (root / "subject_exception_source.json").exists():
            raise ValueError("Ordinary case carries an exception assertion")
        count = len(_read(root, "video_frames.jsonl").splitlines())
        measured = branch.measure_branch(root / "participant_footprints.jsonl",
                                         root / "participant_state.jsonl", count,
                                         "traveling_follow", context)
        distance = measured["min_boundary_distance_ft"]
        if baseline_measure is None:
            baseline_measure = distance
        elif distance != baseline_measure:
            raise ValueError("Exception conjunction changed measured distance")
    return {"passed": True, "comparison_id": "authorized_emergency_exception",
            "case_count": 4, "measured_distance_ft": baseline_measure,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
