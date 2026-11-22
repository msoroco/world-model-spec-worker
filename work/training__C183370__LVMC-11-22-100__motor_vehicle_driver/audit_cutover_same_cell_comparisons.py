"""Independently compare current-runtime cutover same-cell CPU sources.

This is a diagnostic audit. It never promotes a pair to physical or legal
acceptance; selected delivery and original-source audits remain separate.
"""
import argparse
import hashlib
import json
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')
PAIRS = {
    'comparison_main': ('reference', 'contrast', 'contact'),
    'comparison_barrier': ('barrier_crossing', 'barrier_avoidance', 'contact'),
    'comparison_warning_sign': ('warning_sign_crossing',
                                'warning_sign_avoidance', 'contact'),
    'comparison_highway_closed_sign': ('highway_closed_sign_crossing',
                                      'highway_closed_sign_avoidance', 'contact'),
    'comparison_employee_exception': (
        'employee_exception_employee_crossing',
        'employee_exception_nonemployee_crossing', 'activity'),
}
SOURCE_LABELS = {
    'reference': 'update143', 'contrast': 'update143',
    'barrier_crossing': 'update144', 'barrier_avoidance': 'update144',
    'warning_sign_crossing': 'update145', 'warning_sign_avoidance': 'update145',
    'highway_closed_sign_crossing': 'update146',
    'highway_closed_sign_avoidance': 'update146',
    'employee_exception_employee_crossing': 'update147',
    'employee_exception_nonemployee_crossing': 'update147',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def source_paths(short, source_short=None):
    short = source_short or short
    if short == 'reference':
        base = REPO / '.runtime-work/c183370-cutover-probe'
        return (base / 'source', base / 'saved2/v0001')
    base = REPO / '.runtime-work/c183370-cutover-chains' / short / 'primary'
    return (base / 'source', base / 'saved/v0001')


def inspect(short, case, entry, manifest_sha, source_short=None):
    attempt, saved = source_paths(short, source_short)
    selection = read(attempt / 'candidate-selection.json')
    processing = read(saved / 'processing.json')
    report = read(saved / 'analysis/analysis-report.json')
    result = read(saved / 'analysis/result.json')
    require(selection['case_id'] == processing['case_id'] ==
            report['case_id'] == result['case_id'] == case,
            'Comparison case identity differs: ' + short)
    require(selection['candidate_id'] == processing['candidate_id'] == 'primary'
            and selection['manifest_sha256'] == manifest_sha
            and selection['construction_sha256'] ==
            processing['analysis_revision']['construction_sha256'] ==
            entry['construction_sha256'],
            'Comparison exact selection differs: ' + short)
    require(sha(HERE / entry['construction']) == entry['construction_sha256'],
            'Comparison construction hash differs: ' + short)
    require(processing['passed'] is True and processing['recorded_only'] is True
            and processing['originals_preserved'] is True
            and processing['timestamp_joins']['passed'] is True
            and processing['timestamp_joins']['frames'] == 600
            and processing['final_video_checks']['passed'] is True
            and processing['final_video_checks']['frames'] == 600,
            'Comparison saved processing differs: ' + short)
    require(report['diagnostic_fixture'] is True
            and report['physical_acceptance_claimed'] is False
            and result['diagnostic_fixture'] is True
            and result['accepted'] is False
            and result['legal_verdict_claimed'] is False,
            'Comparison fixture was promoted: ' + short)
    for name, digest in processing['original_source_hashes'].items():
        require(sha(attempt / name) == digest,
                'Comparison retained source hash differs: ' + short + '/' + name)
    for name in CAMERAS:
        require(name in processing['original_source_hashes'],
                'Comparison camera source missing: ' + short + '/' + name)
    actors, frames = rows(attempt / 'native-actors.jsonl'), rows(attempt / 'video_frames.jsonl')
    require(len(actors) == len(frames) == 600,
            'Comparison source frame count differs: ' + short)
    polygon = Polygon(read(attempt / 'live-readback.json')['plan']['repair_polygon_xy_m'])
    contact = []
    for index, (actor, frame) in enumerate(zip(actors, frames)):
        require(actor['frame'] == frame['native_frame'] and
                actor['video_frame'] == frame['video_frame'] == index and
                actor['time_s'] == frame['time_s'],
                'Comparison source join differs: ' + short + '/' + str(index))
        if MultiPoint([(v[0], v[1]) for v in actor['ego_body_vertices_xyz_m']]).convex_hull.intersects(polygon):
            contact.append(index)
    measured = report['measurements']['surveyed_pavement_contact']
    require(measured['value']['contact_frames'] == contact and
            measured['value']['measured_contact'] == bool(contact),
            'Comparison saved contact differs from Native source: ' + short)
    for name, digest in measured['sources'].items():
        require(sha(attempt / name) == digest,
                'Comparison measurement source hash differs: ' + short + '/' + name)
    return {'attempt': attempt, 'saved': saved, 'actors': actors, 'frames': frames,
            'readback': read(attempt / 'live-readback.json'),
            'contact': contact, 'result': result,
            'selection_sha256': sha(attempt / 'candidate-selection.json'),
            'processing_sha256': sha(saved / 'processing.json')}


def audit(comparison_suffix, swapped=False):
    require(comparison_suffix in PAIRS, 'Unknown C183370 comparison')
    left_short, right_short, variable = PAIRS[comparison_suffix]
    plan = read(HERE / 'case-plan.json')
    comparison_id = HERE.name + '__' + comparison_suffix
    spec = next((c for c in plan['comparisons']
                 if c['comparison_id'] == comparison_id), None)
    require(spec is not None and spec['case_ids'] == [
        HERE.name + '__' + left_short, HERE.name + '__' + right_short],
        'Comparison plan identities differ')
    manifest_path = HERE / 'current-runtime-probe-manifest.json'
    manifest, manifest_sha = read(manifest_path), sha(manifest_path)
    entries = [next(c for c in manifest['cases'] if c['case_id'] == case)
               for case in spec['case_ids']]
    left = inspect(left_short, spec['case_ids'][0], entries[0], manifest_sha,
                   right_short if swapped else None)
    right = inspect(right_short, spec['case_ids'][1], entries[1], manifest_sha,
                    left_short if swapped else None)
    require(left['readback']['plan'] == right['readback']['plan']
            and {k: v for k, v in left['readback'].items() if k != 'plan'} ==
            {k: v for k, v in right['readback'].items() if k != 'plan'},
            'Comparison changed fixed surveyed context')
    require(left['frames'] == right['frames'],
            'Comparison changed source frame clock')
    changed = 0
    for index, (a, b) in enumerate(zip(left['actors'], right['actors'])):
        if variable == 'contact':
            fixed = set(a) - {'ego_position_xyz_m', 'ego_body_vertices_xyz_m'}
            require(set(a) == set(b) and all(a[k] == b[k] for k in fixed),
                    'Comparison changed fixed actor source at ' + str(index))
            changed += a['ego_position_xyz_m'] != b['ego_position_xyz_m']
        else:
            require(a == b, 'Employee comparison changed Native actor source at ' + str(index))
    if variable == 'contact':
        require(changed > 0 and len(left['contact']) == 300
                and not right['contact'],
                'Comparison crossing/avoidance contrast absent')
    else:
        require(len(left['contact']) == len(right['contact']) == 300,
                'Employee comparison changed crossing contact')
        cases = left['readback']['plan']['cases']
        require(cases['employee_crossing']['operator_activity_source'] !=
                cases['nonemployee_crossing']['operator_activity_source'],
                'Employee comparison activity labels are not distinct')
        require(all(row['result']['physical_checks']['setup']['status'] == 'unverified'
                    for row in (left, right)),
                'Employee activity was asserted verified')
    return {'format': 'c183370-selected-same-cell-comparison-diagnostic-v1',
            'comparison_id': comparison_id, 'case_ids': spec['case_ids'],
            'manifest_sha256': manifest_sha, 'plan_sha256': sha(HERE / 'case-plan.json'),
            'source_selection_sha256': [left['selection_sha256'],
                                         right['selection_sha256']],
            'saved_processing_sha256': [left['processing_sha256'],
                                         right['processing_sha256']],
            'contact_frames': [len(left['contact']), len(right['contact'])],
            'changed_ego_position_frames': changed,
            'passed': True, 'diagnostic_only': True,
            'original_native_verified': False,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=PAIRS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--swap-sources', action='store_true')
    args = parser.parse_args()
    result = audit(args.comparison, args.swap_sources)
    require(not args.output.exists(), 'Retain previous comparison audit')
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'comparison': args.comparison, 'passed': True,
                      'diagnostic_only': True, 'receipt_sha256': sha(args.output)},
                     sort_keys=True))
