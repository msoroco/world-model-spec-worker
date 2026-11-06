"""Independent source and controlled-pair audit of the countdown CPU prototype."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    summary = json.loads((HERE / 'draft-countdown-measurement-summary.json').read_text())
    root = Path(summary['retained_root'])
    paired = {}
    for suffix, expected_zero, expected_relation in (
        ('probe_01', 10.0, 'before_zero'), ('probe_02', 7.0, 'at_or_after_zero')
    ):
        folder = root / suffix
        context_path = folder / 'countdown-context.json'
        samples_path = folder / 'countdown_samples.jsonl'
        context = json.loads(context_path.read_text())
        data = rows(samples_path)
        observation = summary['positive'][suffix]
        assert len(data) == observation['original_frames'] == 240
        assert observation['source_sha256'] == {
            'countdown-context.json': sha(context_path),
            'countdown_samples.jsonl': sha(samples_path),
        }
        assert context['source_kind'] == 'synthetic_scene_request'
        assert context['near_highway_edge_xy_m'] == [-3.5, -.65]
        assert context['highway_span_m'] == 7.0 and context['crossing_forward_xy'] == [1, 0]
        assert context['device_governs_crosswalk'] is True and context['device_faces_pedestrian'] is True
        assert all(data[i]['native_frame'] == 100+i and abs(data[i]['time_s']-i/20) < 1e-9 for i in range(240))
        assert all(r['crosswalk_id'] == context['crosswalk_id'] and r['device_id'] == context['device_id'] for r in data)
        assert {r['display_illuminated'] for r in data if r['displayed_countdown_s'] > 0} == {True, False}
        assert [r['display_illuminated'] for r in data[:20]] == [True]*5 + [False]*5 + [True]*5 + [False]*5
        zero = next(i for i, row in enumerate(data) if row['displayed_countdown_s'] == 0)
        clearance = next(i for i, row in enumerate(data)
                         if min(vertex[0] for vertex in row['pedestrian_footprint_xy_m']) >= 3.5-1e-8)
        entry = next(i for i, row in enumerate(data)
                     if max(vertex[0] for vertex in row['pedestrian_footprint_xy_m']) > -3.5)
        assert abs(data[zero]['time_s'] - expected_zero) < 1e-9
        assert abs(data[clearance]['time_s'] - 8.0) < 1e-9
        assert observation['displayed_zero']['first_frame'] == data[zero]['native_frame']
        assert observation['full_body_clearance']['first_frame'] == data[clearance]['native_frame']
        assert observation['entry']['first_frame'] == data[entry]['native_frame']
        assert observation['clearance_relative_to_displayed_zero'] == expected_relation
        assert observation['governing_device_observed'] is False
        assert observation['highway_boundary_observed'] is False
        assert observation['exceptions_reviewed'] is False and observation['legal_verdict_claimed'] is False
        paired[suffix] = data
    for a, b in zip(paired['probe_01'], paired['probe_02']):
        fixed = ('native_frame', 'time_s', 'crosswalk_id', 'device_id',
                 'pedestrian_xy_m', 'pedestrian_footprint_xy_m', 'synthetic_diagnostic')
        assert all(a[key] == b[key] for key in fixed)
    assert len(summary['negatives']) == 8
    assert len({x['name'] for x in summary['negatives']}) == 8
    boundary = summary['boundary_diagnostic']
    assert boundary['clearance_relative_to_displayed_zero'] == 'sampling_overlap_unresolved'
    assert boundary['full_body_clearance']['first_frame'] == boundary['displayed_zero']['first_frame']
    print(json.dumps({'independent_source_positives': 2, 'negative_rejections': 8,
                      'fixed_pedestrian_frames': 240, 'clearance_time_s': 8.0,
                      'displayed_zero_times_s': [10.0, 7.0],
                      'equal_time_boundary_unresolved': True,
                      'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
