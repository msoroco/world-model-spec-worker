"""Independent source comparison of the marked-line stop and pass attempts."""
import hashlib
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
        raise ValueError('Missing comparison source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def compare(base):
    sources = [base / f'selected-source-line_{label}' for label in ('stop', 'pass')]
    samples = [rows(folder / 'native_samples.jsonl') for folder in sources]
    maps = [rows(folder / 'video_frames.jsonl') for folder in sources]
    if any(len(value) != 600 for value in samples + maps):
        raise ValueError('Comparison lacks full 600-frame source')
    if (sources[0] / 'road.xodr').read_bytes() != (sources[1] / 'road.xodr').read_bytes():
        raise ValueError('Fixed road geometry changed')
    if maps[0] != maps[1]:
        raise ValueError('Fixed frame clock changed')
    for index, (first, second) in enumerate(zip(*samples)):
        changed = {key for key in first if first[key] != second.get(key)}
        if changed - VARIABLE_FIELDS or set(first) != set(second):
            raise ValueError('Undeclared fixed source condition changed at frame ' + str(index))
    measured = []
    for index, folder in enumerate(sources, start=1):
        manifest = json.loads((folder / 'diagnostic-source-manifest.json').read_text())
        if manifest.get('case_id') != HERE.name + ('__line_stop' if index == 1 else '__line_pass') or any(
                manifest['sha256'].get(name) != sha(folder / name)
                for name in ('road.xodr', 'native_samples.jsonl')):
            raise ValueError('Comparison source identity/hash differs')
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location('line_measure', HERE / 'native/measure_stop_line.py')
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        measured.append(module.measure(folder, HERE.name + ('__line_stop' if index == 1 else '__line_pass')))
    if not measured[0]['pre_line_full_halt_observed'] or measured[1]['pre_line_full_halt_observed']:
        raise ValueError('Controlled measured stop contrast absent')
    return {'format': 'c111325-independent-marked-line-comparison-v1',
            'assignment_id': HERE.name, 'case_ids': [m['case_id'] for m in measured],
            'fixed_road_sha256': sha(sources[0] / 'road.xodr'),
            'fixed_frame_map_sha256': sha(sources[0] / 'video_frames.jsonl'),
            'dynamic_source_fields': sorted(VARIABLE_FIELDS),
            'source_sha256': {str(i): sha(folder / 'native_samples.jsonl')
                              for i, folder in enumerate(sources, start=1)},
            'measured_stop_frames': [m['longest_pre_line_halt_frames'] for m in measured],
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def selftest():
    report = compare(HERE)
    try:
        compare(HERE / 'nonexistent-source')
    except ValueError as error:
        if 'Missing comparison source' not in str(error):
            raise
    else:
        raise AssertionError('Missing source was accepted')
    report['missing_source_negative_passed'] = True
    scratch_root = HERE.parents[1] / '.runtime-work'
    with tempfile.TemporaryDirectory(dir=scratch_root, prefix='c111325-comparison-') as temporary:
        altered = Path(temporary)
        for label in ('stop', 'pass'):
            shutil.copytree(HERE / f'selected-source-line_{label}',
                            altered / f'selected-source-line_{label}')
        path = altered / 'selected-source-line_pass/native_samples.jsonl'
        lines = path.read_text().splitlines()
        row = json.loads(lines[100])
        row['lane_id'] = 1
        lines[100] = json.dumps(row)
        path.write_text('\n'.join(lines) + '\n')
        try:
            compare(altered)
        except ValueError as error:
            if 'Undeclared fixed source condition' not in str(error):
                raise
        else:
            raise AssertionError('Changed lane was accepted')
    report['changed_fixed_source_negative_passed'] = True
    target = HERE / 'selected-line-comparison-audit.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    return {'passed': True, 'audit_sha256': sha(target)}


if __name__ == '__main__':
    print(json.dumps(selftest(), sort_keys=True))
