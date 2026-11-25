"""Independent source contrast for the no-reference sight-point pair."""
import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VARIABLE_FIELDS = {'speed_mps', 'body_vertices_m', 'road_id'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError('Missing sight comparison source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def meter():
    spec = importlib.util.spec_from_file_location('sight_measure', HERE / 'native/measure_sight_point.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.measure


def compare(base):
    sources = [base / f'selected-source-sight_{label}' for label in ('stop', 'pass')]
    samples = [rows(folder / 'native_samples.jsonl') for folder in sources]
    mapping = [rows(folder / 'video_frames.jsonl') for folder in sources]
    sight = [rows(folder / 'sight_samples.jsonl') for folder in sources]
    if any(len(value) != 600 for value in samples + mapping + sight):
        raise ValueError('Sight comparison lacks full 600-frame source')
    if (sources[0] / 'road.xodr').read_bytes() != (sources[1] / 'road.xodr').read_bytes():
        raise ValueError('Fixed no-reference road changed')
    if mapping[0] != mapping[1]:
        raise ValueError('Fixed frame clock changed')
    for index, (first, second) in enumerate(zip(*samples)):
        changed = {key for key in first if first[key] != second.get(key)}
        if changed - VARIABLE_FIELDS or set(first) != set(second):
            raise ValueError('Undeclared fixed subject condition changed at frame ' + str(index))
    for index, (first, second) in enumerate(zip(*sight)):
        for key in ('native_frame', 'time_s', 'approaching_traffic',
                    'intersecting_actor_approach', 'intersecting_actor_xy_m',
                    'occluder_xy_bounds_m', 'view_source_kind'):
            if first.get(key) != second.get(key):
                raise ValueError('Fixed traffic or occluder condition changed at frame ' + str(index))
    measure = meter()
    observed = [measure(folder, HERE.name + '__sight_' + label)
                for folder, label in zip(sources, ('stop', 'pass'))]
    if not observed[0]['halt_at_view_point_observed'] or observed[1]['halt_at_view_point_observed']:
        raise ValueError('Source-measured sight stop contrast absent')
    return {'format': 'c111325-independent-sight-comparison-v1',
            'assignment_id': HERE.name, 'case_ids': [item['case_id'] for item in observed],
            'fixed_road_sha256': sha(sources[0] / 'road.xodr'),
            'fixed_frame_map_sha256': sha(sources[0] / 'video_frames.jsonl'),
            'source_sha256': {label: sha(folder / 'native_samples.jsonl')
                              for label, folder in zip(('stop', 'pass'), sources)},
            'view_source_kind': 'synthetic_view_proxy',
            'halt_frames_after_view_open': [item['longest_halt_after_view_open_frames'] for item in observed],
            'physical_visibility_verified': False, 'legal_verdict_claimed': False}


def selftest():
    report = compare(HERE)
    try:
        compare(HERE / 'nonexistent-source')
    except ValueError as error:
        if 'Missing sight comparison source' not in str(error):
            raise
    else:
        raise AssertionError('Missing source accepted')
    report['missing_source_negative_passed'] = True
    with tempfile.TemporaryDirectory(dir=HERE.parents[1] / '.runtime-work',
                                     prefix='c111325-sight-comparison-') as temporary:
        altered = Path(temporary)
        for label in ('stop', 'pass'):
            shutil.copytree(HERE / f'selected-source-sight_{label}',
                            altered / f'selected-source-sight_{label}')
        path = altered / 'selected-source-sight_pass/sight_samples.jsonl'
        lines = path.read_text().splitlines()
        row = json.loads(lines[100])
        row['intersecting_actor_xy_m'][0] += 1
        lines[100] = json.dumps(row)
        path.write_text('\n'.join(lines) + '\n')
        try:
            compare(altered)
        except ValueError as error:
            if 'Fixed traffic or occluder condition changed' not in str(error):
                raise
        else:
            raise AssertionError('Changed approaching traffic accepted')
    report['changed_fixed_traffic_negative_passed'] = True
    target = HERE / 'selected-sight-comparison-audit.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    return {'passed': True, 'audit_sha256': sha(target)}


if __name__ == '__main__':
    print(json.dumps(selftest(), sort_keys=True))
