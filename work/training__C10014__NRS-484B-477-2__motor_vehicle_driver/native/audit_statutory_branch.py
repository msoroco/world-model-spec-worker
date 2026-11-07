"""Independent CPU source-to-branch audit for the unselected alley pair."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ROOT = WORK.parents[1]
LAW = 'NRS-484B-477-2'
AID = WORK.name
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def run_audit(name):
    path = WORK / name
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.audit()


def check_saved_stop(rows, expected_x):
    if len(rows) != 480:
        raise ValueError('Frame count differs')
    stationary = [r for r in rows if r['speed_mps'] <= 0.1]
    if len(stationary) < 40:
        raise ValueError('Stationary interval missing')
    last = stationary[-1]
    if last['native_center_xy_m'] != [expected_x, -2]:
        raise ValueError('Stop position differs')
    if last['native_road_id'] != 1 or last['native_lane_id'] != -1:
        raise ValueError('Alley lane identity differs')
    body = last['native_body_xy_m']
    if len(body) != 4 or min(p[0] for p in body) != expected_x - 2.6 or max(p[0] for p in body) != expected_x + 2.6:
        raise ValueError('Body footprint differs')
    return round(max(0, min(expected_x + 2.6, 3) - max(expected_x - 2.6, -3)), 6)


def audit():
    sources = read(ROOT / 'inputs/coverage/branch-sources.json')['laws'][LAW]
    plan = read(WORK / 'case-plan.json')
    matrix_path = ROOT / 'work/_shared/branch-coverage.json'
    branch = read(matrix_path)['laws'][LAW]['branches'][0]
    review = read(ROOT / 'work/_shared/branch-review.json')
    assert sources['law']['text'] == plan['source_law_text']
    assert set(sources['topics']) == {'text-0', 'reviewed-scope-0'}
    assert set(branch['topic_ids']) == set(sources['topics'])
    assert branch['status'] == 'runnable' and branch['assignment_id'] == AID
    assert set(branch['case_ids']) == {AID + '__reference', AID + '__contrast'}
    assert branch['comparison_ids'] == [AID + '__comparison_main']
    assert review['coverage_sha256'] == sha(matrix_path)
    assert LAW not in review['missing_branches']
    assert {x['requirement'] for x in plan['requirement_dispositions']} == set(sources['topics'])
    assert set(branch['cpu_proofs']) == {
        'draft-execution-manifest.json', 'draft-offline-summary.json',
        'draft-package-probe-summary.json', 'saved-comparison-summary.json'}
    for name, digest in branch['cpu_proofs'].items():
        assert sha(WORK / name) == digest, name

    manifest = read(WORK / 'draft-execution-manifest.json')
    offline = read(WORK / 'draft-offline-summary.json')
    package = read(WORK / 'draft-package-probe-summary.json')
    saved = read(WORK / 'saved-comparison-summary.json')
    assert manifest['status'] == 'draft_not_selected'
    assert len(manifest['cases']) == 2 and len(offline['results']) == 8
    assert package['count'] == 8 and not package['ready'] and not package['strict_v2_compatibility']
    assert saved['cases'] == 2 and saved['shared_prefix_frames'] == 132
    assert saved['reference_overlap_m'] == 0 and saved['contrast_overlap_m'] == 5.2
    assert not saved['physical_success_claimed'] and not saved['selected']
    assert {r['case_id'] for r in offline['results']} == set(branch['case_ids'])
    assert {(r['case_id'].rsplit('__', 1)[1], r['candidate_id']) for r in offline['results']} == {
        (suffix, name) for suffix in ('reference', 'contrast') for name in NAMES}
    for entry in manifest['cases']:
        assert entry['case_id'] in branch['case_ids']
        assert entry['kind'] == 'draft_not_selected'
        assert {c['id'] for c in entry['candidates']} == set(NAMES) - {'primary'}
        metrics = {c['trigger']['metric'] for c in entry['candidates']}
        assert len(metrics) == 3
        assert all(c['trigger']['failure_condition'] and c['changed_knobs'] for c in entry['candidates'])

    assert run_audit('audit-draft-offline.py')['passed']
    assert run_audit('audit-draft-comparison.py')['passed']
    assert run_audit('audit-draft-measurements.py')['reference_overlap_m'] == 0
    assert run_audit('audit-saved-comparison.py')['contrast_overlap_m'] == 5.2
    assert run_audit('audit-package-probes.py')['count'] == 8
    rejected = []
    for suffix, expected_x, expected_overlap in (('reference', -12, 0), ('contrast', 0, 5.2)):
        path = WORK / 'draft-measurements' / suffix / 'native_samples.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert check_saved_stop(rows, expected_x) == expected_overlap
        for label, change, error in (
            ('stop', lambda r: r[-1]['native_center_xy_m'].__setitem__(0, 99), 'Stop position differs'),
            ('lane', lambda r: r[-1].update(native_lane_id=7), 'Alley lane identity differs'),
            ('body', lambda r: r[-1]['native_body_xy_m'][0].__setitem__(0, 99), 'Body footprint differs')):
            import copy
            bad = copy.deepcopy(rows)
            change(bad)
            try:
                check_saved_stop(bad, expected_x)
            except ValueError as exc:
                assert str(exc) == error
                rejected.append(suffix + ':' + label)
            else:
                raise AssertionError('Corrupt ' + label + ' accepted')
    result = read(WORK / 'result.json')
    assert result['status'] == 'blocked' and result['cases_selected'] == 0
    return {'passed': True, 'law_id': LAW, 'source_topic_count': 2,
            'exact_offline_bundles': 8, 'synthetic_positive_and_negative_pairs': 8,
            'controlled_overlap_m': [0, 5.2], 'selected': False,
            'negative_rejections': rejected,
            'physical_or_strict_v2_verified': False,
            'manifest_sha256': sha(WORK / 'draft-execution-manifest.json'),
            'offline_sha256': sha(WORK / 'draft-offline-summary.json'),
            'portable_sha256': sha(WORK / 'draft-package-probe-summary.json'),
            'saved_pair_sha256': sha(WORK / 'saved-comparison-summary.json')}


if __name__ == '__main__':
    output = audit()
    (HERE / 'statutory-cpu-audit.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, sort_keys=True))
