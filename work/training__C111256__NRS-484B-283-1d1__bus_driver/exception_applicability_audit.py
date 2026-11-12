"""Source-bound factual review of cited NRS 484B.283 introductory branches.

This checks whether the selected ordinary marked-crosswalk scene still fits its
planned scope. It does not decide any person's legal right of way.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('road_geometry.json', 'native_samples.jsonl', 'video_frames.jsonl',
           *(name + '.mkv' for name in CAMERAS))
QUESTIONS = {
    'crossing_outside_crosswalk': 'NRS 484B.287(1)(a)',
    'tunnel_or_overhead_crossing_provided': 'NRS 484B.287(1)(b)',
    'crossing_outside_marked_crosswalk_between_controlled_intersections':
        'NRS 484B.287(1)(c)',
    'unauthorized_diagonal_crossing': 'NRS 484B.287(1)(d)',
    'diagonal_crossing_contrary_to_device': 'NRS 484B.287(1)(e)',
    'blind_pedestrian_using_service_animal_or_qualifying_cane': 'NRS 484B.290',
    'school_crossing_guard_direction_or_signal': 'NRS 484B.350(1)',
}
PRIMARY = 'https://www.leg.state.nv.us/nrs/nrs-484b.html'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_review(review, hashes, *, diagnostic=False):
    kind = 'source_shaped_unit_test' if diagnostic else 'original_native_exception_review'
    require(review.get('format') == 'c111256-exception-applicability-review-v1' and
            review.get('source_kind') == kind and
            review.get('source_sha256') == hashes and
            review.get('reviewer') and review.get('method') and
            review.get('legal_verdict_claimed') is False,
            'Exception review identity, provenance or source hashes differ')
    checks = review.get('checks')
    require(isinstance(checks, dict) and set(checks) == set(QUESTIONS),
            'Cited exception branch review incomplete')
    observed = []
    for name, section in QUESTIONS.items():
        item = checks[name]
        require(item.get('section') == section and type(item.get('observed')) is bool and
                item.get('method') and item.get('coverage_complete') is True and
                isinstance(item.get('evidence'), list) and item['evidence'],
                'Exception branch lacks source-bound factual review: ' + name)
        for evidence in item['evidence']:
            source = evidence.get('source')
            require(source in hashes and evidence.get('sha256') == hashes[source] and
                    evidence.get('frame_range') == [0, 479] and
                    evidence.get('observation') and evidence.get('limitations') is not None,
                    'Exception branch source or frame coverage differs: ' + name)
        if item['observed']:
            observed.append(name)
    return {'reviewed_branches': len(QUESTIONS),
            'observed_alternate_branches': observed,
            'ordinary_marked_crosswalk_scope_supported': not observed and not diagnostic,
            'legal_verdict_claimed': False}


def audit_original(attempt, review_path):
    attempt = Path(attempt)
    capture = json.loads((attempt / 'capture/manifest.json').read_text())
    require(capture.get('synthetic_diagnostic') is False,
            'Synthetic source cannot prove exception applicability')
    hashes = {name: sha(attempt / name) for name in SOURCES}
    review_path = Path(review_path)
    require(review_path.is_file(), 'Original exception review missing')
    review = json.loads(review_path.read_text())
    summary = validate_review(review, hashes)
    require(not summary['observed_alternate_branches'],
            'Selected ordinary Walk case has a cited alternate branch requiring review')
    return {'format': 'c111256-original-exception-applicability-audit-v1',
            'primary_source': PRIMARY, 'source_sha256': hashes,
            'review_sha256': sha(review_path), **summary,
            'physical_acceptance_claimed': False}
