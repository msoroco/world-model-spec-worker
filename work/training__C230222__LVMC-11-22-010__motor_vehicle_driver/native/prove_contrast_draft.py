"""Audit the two unselected C230222 source-capture construction bundles."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    paths = [ROOT / 'draft-primary' / name / 'primary/construction.json'
             for name in ('reference', 'contrast')]
    bundles = [json.loads(path.read_text()) for path in paths]
    files = [{item['path']: item['content'] for item in bundle['files']}
             for bundle in bundles]
    configs = [json.loads(item['config.json']) for item in files]
    assert set(files[0]) == set(files[1])
    for key in files[0]:
        if key != 'config.json':
            if key == 'tests/test_offline.py':
                assert files[1][key].startswith(files[0][key])
            else:
                assert files[0][key] == files[1][key], key
    ref, contrast = configs
    for key in ref:
        if key not in ('case_id', 'selected_case_id', 'control_phases'):
            assert ref[key] == contrast[key], key
    assert ref['case_id'].endswith('__reference')
    assert contrast['case_id'].endswith('__contrast')
    assert ref['control_phases'][0] == contrast['control_phases'][0]
    for original, changed in zip(ref['control_phases'][1:],
                                 contrast['control_phases'][1:]):
        assert {key: value for key, value in original.items() if key != 'throttle'} == {
            key: value for key, value in changed.items() if key != 'throttle'}
    assert [phase['throttle'] for phase in ref['control_phases']] == [0.24, 0.18, 0.12]
    assert [phase['throttle'] for phase in contrast['control_phases']] == [0.24, 0.10, 0.08]
    assert ref['driver_attention_to_operation'] is None
    assert contrast['driver_attention_to_operation'] is None
    assert ref['legal_verdict'] is None and contrast['legal_verdict'] is None
    manifest = ROOT / 'draft-contrast-manifest.json'
    listed = json.loads(manifest.read_text())['cases'][0]
    assert listed['construction_sha256'] == sha(paths[1])
    return {
        'format': 'c230222-unselected-motion-probe-audit-v1',
        'passed': True, 'selected': False,
        'reference_sha256': sha(paths[0]),
        'contrast_sha256': sha(paths[1]),
        'manifest_sha256': sha(manifest),
        'fixed': ['law', 'cell', 'actor', 'vehicle', 'spawn', 'cameras',
                  'duration', 'rate', 'required_atoms', 'runner', 'observer'],
        'changed': ['travel_throttle_request', 'departure_throttle_request'],
        'attention_observed': False,
        'legal_verdict_claimed': False,
        'limitations': ['The proposed motion difference is an engineering probe.',
                        'It does not measure a human driver\'s attention.'],
    }


if __name__ == '__main__':
    path = ROOT / 'draft-contrast-audit.json'
    path.write_text(json.dumps(check(), indent=2) + '\n')
    print(path)
