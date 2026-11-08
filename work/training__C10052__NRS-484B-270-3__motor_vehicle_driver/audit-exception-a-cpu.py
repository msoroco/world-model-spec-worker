"""Independent CPU proof of the unselected alley-entry exception geometry."""
import hashlib
import json
from pathlib import Path

from audit_geometry import clipped_area

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure(folder, source_name):
    source = read(folder / source_name)
    assert source['source_kind'] == 'synthetic_cpu_fixture'
    assert all(sha(folder / name) == digest for name, digest in source['sha256'].items())
    geometry = read(folder / 'road_geometry.json')
    samples = rows(folder / 'native_samples.jsonl')
    assert len(samples) == 480
    facility = geometry['bicycle_facility_native_xy_bounds_m']
    alley = geometry['alley_entrance_native_xy_bounds_m']
    f = [clipped_area(r['native_body_xy_m'], facility) for r in samples]
    a = [clipped_area(r['native_body_xy_m'], alley) for r in samples]
    moving = [r['speed_mps'] > .1 for r in samples]
    first_f = next((i for i in range(1, 480)
                    if moving[i] and f[i-1] <= .01 and f[i] > .01), None)
    first_a = next((i for i in range(480) if moving[i] and a[i] > .01), None)
    both = sum(moving[i] and f[i] > .01 and a[i] > .01 for i in range(480))
    gap = None if first_f is None or first_a is None else round(
        samples[first_a]['time_s'] - samples[first_f]['time_s'], 6)
    candidate = first_f is not None and first_a is not None and 0 <= gap <= 2 and both > 0
    return samples, {
        'first_facility_entry_native_frame': None if first_f is None else samples[first_f]['native_frame'],
        'first_alley_footprint_native_frame': None if first_a is None else samples[first_a]['native_frame'],
        'facility_to_alley_gap_s': gap,
        'simultaneous_moving_overlap_frames': both,
        'time_bounded_geometry_candidate': candidate,
        'moving_facility_occupied_frames': sum(moving[i] and f[i] > .01 for i in range(480)),
    }


def main():
    alley_manifest = HERE / 'draft-alley-execution-manifest.json'
    no_entry_manifest = HERE / 'draft-no-entry-execution-manifest.json'
    alley_cases = read(alley_manifest)['cases']
    no_entry_cases = read(no_entry_manifest)['cases']
    assert len(alley_cases) == len(no_entry_cases) == 1
    assert alley_cases[0]['case_id'].endswith('__probe_c_alley_entry')
    assert no_entry_cases[0]['case_id'].endswith('__probe_d_no_entry')
    pairs = []
    for name in NAMES:
        a_summary = read(HERE / f'alley-package-{name}-summary.json')
        n_summary = read(HERE / f'no-entry-package-{name}-summary.json')
        assert a_summary['selected'] is n_summary['selected'] is False
        assert a_summary['accepted'] is n_summary['accepted'] is False
        assert a_summary['manifest_sha256'] == sha(alley_manifest)
        assert n_summary['manifest_sha256'] == sha(no_entry_manifest)
        a_ref = alley_cases[0] if name == 'primary' else next(
            c for c in alley_cases[0]['candidates'] if c['id'] == name)
        n_ref = no_entry_cases[0] if name == 'primary' else next(
            c for c in no_entry_cases[0]['candidates'] if c['id'] == name)
        assert a_summary['construction_sha256'] == a_ref['construction_sha256'] == sha(HERE / a_ref['construction'])
        assert n_summary['construction_sha256'] == n_ref['construction_sha256'] == sha(HERE / n_ref['construction'])
        a_root, n_root = REPO / a_summary['source_root'], REPO / n_summary['source_root']
        a_rows, a = measure(a_root / 'fixture', 'alley-transition-sources.json')
        n_rows, n = measure(n_root / 'fixture', 'entry-sources.json')
        a_report = read(a_root / 'positive/analysis-report.json')
        n_report = read(n_root / 'positive/analysis-report.json')
        a_value = a_report['measurements']['alley_transition_observation']['value']
        n_value = n_report['measurements']['moving_body_facility_entry']['value']
        assert all(a_value[k] == a[k] for k in (
            'first_facility_entry_native_frame', 'first_alley_footprint_native_frame',
            'facility_to_alley_gap_s', 'simultaneous_moving_overlap_frames',
            'time_bounded_geometry_candidate'))
        assert n_value['moving_occupied_frames'] == n['moving_facility_occupied_frames'] == 0
        assert a['first_facility_entry_native_frame'] == 170
        assert a['first_alley_footprint_native_frame'] == 201
        assert a['facility_to_alley_gap_s'] == 1.55 and a['simultaneous_moving_overlap_frames'] == 27
        assert a['time_bounded_geometry_candidate'] and not n['time_bounded_geometry_candidate']
        assert a_value['statutory_exception_observed'] == n_value['exception_a_observed'] == 'unresolved'
        assert a_value['accepted'] is n_value['accepted'] is False
        for root, summary, required in ((a_root, a_summary, 'alley-transition-sources.json'),
                                        (n_root, n_summary, 'entry-sources.json')):
            receipt = read(root / 'positive/compatibility.json')
            assert sha(root / 'positive/compatibility.json') == summary['positive_receipt_sha256']
            assert receipt['passed'] is True and receipt['format'] == 'worker-package-compatibility-v1'
            assert summary['negative_exit_code'] != 0
            assert sha(root / 'negative.log') == summary['negative_log_sha256']
            assert required in (root / 'negative.log').read_text()
            assert not (root / 'negative/result.json').exists()
        assert n_summary['trigger_negative_exit_code'] != 0
        assert sha(n_root / 'trigger-negative.log') == n_summary['trigger_negative_log_sha256']
        pairs.append({'candidate': name, 'alley': a, 'no_entry': n,
                      'alley_source_sha256': sha(a_root / 'fixture/native_samples.jsonl'),
                      'no_entry_source_sha256': sha(n_root / 'fixture/native_samples.jsonl'),
                      'longitudinal_trace_identical': all(
                          left['native_center_xy_m'][0] == right['native_center_xy_m'][0]
                          for left, right in zip(a_rows, n_rows))})
    controlled = read(HERE / 'alley-transition-summary.json')
    assert controlled['selected'] is controlled['accepted'] is False
    controlled_root = REPO / controlled['source_root']
    near_rows, near = measure(controlled_root / 'near_alley', 'alley-transition-sources.json')
    away_rows, away = measure(controlled_root / 'away_from_alley', 'alley-transition-sources.json')
    assert near['time_bounded_geometry_candidate'] and not away['time_bounded_geometry_candidate']
    assert near['first_facility_entry_native_frame'] == away['first_facility_entry_native_frame'] == 170
    assert near['simultaneous_moving_overlap_frames'] == 27 and away['simultaneous_moving_overlap_frames'] == 0
    assert all(left['native_frame'] == right['native_frame'] and
               left['time_s'] == right['time_s'] and left['speed_mps'] == right['speed_mps'] and
               left['native_center_xy_m'][1] == right['native_center_xy_m'][1] and
               left['native_center_xy_m'][0] - right['native_center_xy_m'][0] == 12
               for left, right in zip(near_rows, away_rows))
    return {'format': 'c10052-exception-a-cpu-audit-v1', 'passed': True,
            'exact_candidate_pairs': pairs, 'controlled_near': near, 'controlled_away': away,
            'controlled_summary_sha256': sha(HERE / 'alley-transition-summary.json'),
            'source_scope': 'synthetic_cpu_fixture', 'selected': False,
            'legal_exception_observed': False, 'accepted': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
