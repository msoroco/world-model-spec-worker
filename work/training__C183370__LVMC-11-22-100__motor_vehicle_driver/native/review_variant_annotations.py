"""Bind independent statutory variant review to retained original CARLA sources.

The review is a cited observation, not physical acceptance or a legal verdict.
Employee exception activity needs its own retained independent source.
"""
import argparse
import hashlib
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CONTROLS = {
    'barrier': ('barrier_placement', 'across_or_around_identified_pavement'),
    'warning_sign': ('warning_sign_content',
                     'against_riding_or_driving_over_identified_pavement'),
    'highway_closed_sign': ('highway_closed_sign_content', 'highway_closed'),
}
EMPLOYEE_CONTROLS = {
    'barrier_across_or_around_identified_pavement',
    'person_warning_against_riding_or_driving_over_identified_pavement',
    'sign_warning_against_riding_or_driving_over_identified_pavement',
    'highway_closed_sign',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def citation(row, cameras, first, last):
    name = row.get('camera')
    require(name in cameras and row.get('camera_sha256') == cameras[name],
            'Original review camera source hash differs')
    interval = row.get('frame_interval')
    require(isinstance(interval, list) and len(interval) == 2
            and all(type(v) is int for v in interval)
            and first <= interval[0] <= interval[1] <= last,
            'Original review frame interval differs')
    require(isinstance(row.get('observation'), str)
            and len(row['observation'].strip()) >= 20,
            'Original review needs a specific observed fact')
    require(row.get('observed') is True,
            'Original review observation must be affirmative')
    return interval


def evaluate(analysis, review, *, analysis_sha256):
    require(analysis.get('format') == 'c183370-variant-original-analysis-v1'
            and analysis.get('source_kind') == 'original_carla_capture',
            'Original variant source analysis required')
    kind = analysis.get('control_kind')
    require(kind in CONTROLS or kind == 'employee_exception',
            'Unknown statutory control review')
    require(review.get('source_analysis_sha256') == analysis_sha256,
            'Variant review source-analysis hash differs')
    require(isinstance(review.get('reviewer_id'), str)
            and review['reviewer_id'].strip(),
            'Independent reviewer identity required')
    observations = analysis['observations']
    first, last = observations['source_first_frame'], observations['source_last_frame']
    require(observations['source_frames'] >= 600
            and observations['source_elapsed_s'] >= 30 - .001
            and observations['control_actor_near_pavement_frames'] ==
            observations['source_frames'],
            'Original variant source continuity or control vicinity differs')
    cameras = {row['name']: row['source_sha256']
               for row in analysis['camera_sources']}
    require(set(cameras) == set(CAMERAS)
            and all(isinstance(value, str) and len(value) == 64
                    and all(ch in '0123456789abcdef' for ch in value)
                    for value in cameras.values()),
            'Four original camera sources required')
    annotations = review.get('annotations')
    require(isinstance(annotations, dict),
            'Original variant annotations required')
    control_name, content = (CONTROLS[kind] if kind in CONTROLS else
                             ('governing_warning_control', None))
    require(control_name in annotations and
            'newly_repaired_pavement' in annotations,
            'Control and pavement observations required')
    control, pavement = annotations[control_name], annotations['newly_repaired_pavement']
    if kind == 'employee_exception':
        require(control.get('content') in EMPLOYEE_CONTROLS,
                'Governing warning control was not reviewed')
    else:
        require(control.get('content') == content,
                'Specific control content was not reviewed')
    require(pavement.get('condition') in ('newly_laid', 'newly_repaired'),
            'Newly laid or repaired condition was not reviewed')
    control_interval = citation(control, cameras, first, last)
    pavement_interval = citation(pavement, cameras, first, last)
    overlap = [max(control_interval[0], pavement_interval[0]),
               min(control_interval[1], pavement_interval[1])]
    require(overlap[0] <= overlap[1],
            'Control and pavement observations do not overlap')
    contact = observations['pavement_footprint_contact_frames']
    require(all(type(v) is int and 0 <= v < observations['source_frames']
                for v in contact),
            'Original variant contact frame index differs')
    concurrent = [first + frame for frame in contact
                  if overlap[0] <= first + frame <= overlap[1]]
    route = analysis['case']
    if kind == 'employee_exception':
        require(route in ('employee_crossing', 'nonemployee_crossing'),
                'Original employee exception route differs')
        activity = annotations.get('operator_activity')
        require(isinstance(activity, dict) and
                activity.get('status') ==
                ('actually_engaged' if route == 'employee_crossing'
                 else 'not_actually_engaged'),
                'Operator activity status differs from comparison route')
        evidence = activity.get('independent_evidence')
        require(isinstance(evidence, dict) and
                isinstance(evidence.get('reference'), str) and
                isinstance(evidence.get('sha256'), str) and
                len(evidence['sha256']) == 64 and
                isinstance(evidence.get('observation'), str) and
                len(evidence['observation'].strip()) >= 20,
                'Operator activity needs independent source evidence')
        activity_status = activity['status']
    else:
        require(route in ('crossing', 'avoidance'),
                'Original variant route differs')
        activity_status = 'unreviewed'
    return {'format': 'c183370-variant-source-review-v1',
            'case': route, 'control_kind': kind,
            'reviewer_id': review['reviewer_id'],
            'source_analysis_sha256': analysis_sha256,
            'source_review_sha256': None,
            'control_and_repair_overlap_frames': overlap,
            'contact_during_reviewed_context_frames': concurrent,
            'requested_contact_context_observed':
                bool(concurrent) if route.endswith('crossing') else not contact,
            'paving_employee_exception_status': activity_status,
            'evidence_level': 'reviewer_attested_source_citations',
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


def review_attempt(attempt, annotations_path, output):
    attempt, annotations_path, output = map(
        Path, (attempt, annotations_path, output))
    require(not output.exists(), 'Preserve prior review receipt; use a new output')
    analysis_path = attempt / 'source-analysis.json'
    analysis, annotations = (json.loads(path.read_text())
                             for path in (analysis_path, annotations_path))
    for name, expected in analysis.get('source_hashes', {}).items():
        require(digest(attempt / name) == expected,
                'Original variant source changed after analysis: ' + name)
    for camera in analysis.get('camera_sources', []):
        name = camera['name'] + '.mkv'
        require(digest(attempt / name) == camera['source_sha256'],
                'Original variant camera changed after analysis: ' + name)
    activity = annotations.get('annotations', {}).get('operator_activity', {})
    if activity:
        evidence = activity.get('independent_evidence', {})
        reference = Path(evidence.get('reference', ''))
        require(not reference.is_absolute() and '..' not in reference.parts
                and reference.parts and
                digest(attempt / reference) == evidence.get('sha256'),
                'Original operator activity source hash differs')
    result = evaluate(analysis, annotations,
                      analysis_sha256=digest(analysis_path))
    result['source_review_sha256'] = digest(annotations_path)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--annotations', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    review_attempt(args.attempt, args.annotations, args.output)
