"""Independent audit of saved original synthetic sources and controlled pair."""
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SAVED = ROOT/'draft-following'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(suffix):
    folder = SAVED/suffix
    samples = folder/'native_samples.jsonl'
    context = folder/'following_context.json'
    report = json.loads((folder/'measurement.json').read_text())
    assert report['source_sha256'] == {samples.name: digest(samples), context.name: digest(context)}
    rows = [json.loads(line) for line in samples.read_text().splitlines()]
    assert len(rows) == 900
    gaps, headways = [], []
    for i, item in enumerate(rows):
        assert item['native_frame'] == i+1
        assert abs(item['time_s']-(i+1)/20) < 1e-9
        ego, lead = item['ego'], item['lead']
        assert ego['native_road_id'] == lead['native_road_id'] == 1
        assert ego['native_lane_id'] == lead['native_lane_id'] == -1
        assert ego['native_forward_xy'] == lead['native_forward_xy'] == [1.0, 0.0]
        assert ego['speed_mps'] == lead['speed_mps'] == 8.0
        ego_body, lead_body = ego['native_body_xy_m'], lead['native_body_xy_m']
        assert len(ego_body) == len(lead_body) == 4
        assert min(p[1] for p in ego_body) < max(p[1] for p in lead_body)
        assert min(p[1] for p in lead_body) < max(p[1] for p in ego_body)
        gap = min(p[0] for p in lead_body)-max(p[0] for p in ego_body)
        assert gap > 0
        gaps.append(gap)
        headways.append(gap/ego['speed_mps'])
        if i:
            assert min(p[0] for p in lead_body) > min(p[0] for p in rows[i-1]['lead']['native_body_xy_m'])
    assert report['original_frames'] == len(rows)
    assert report['following_duration_s'] == len(rows)/20
    assert report['min_bumper_gap_m'] == round(min(gaps), 6)
    assert report['median_bumper_gap_m'] == round(statistics.median(gaps), 6)
    assert report['median_time_headway_s'] == round(statistics.median(headways), 6)
    assert report['native_highway_status_verified'] is False
    assert report['reasonable_and_prudent_verdict_claimed'] is False
    contract = json.loads((folder/'measurement-contract.json').read_text())
    analysis = json.loads((folder/'analysis-report.json').read_text())
    assert contract['format'] == 'worker-measurement-contract-v1'
    assert len(contract['requirements']) == 1
    requirement = contract['requirements'][0]
    assert requirement['requirement'] == 'text-0'
    assert requirement['inputs'] == ['native_samples.jsonl', 'following_context.json']
    saved_value = analysis['measurements']['moving_following_interval']
    assert saved_value['value'] == report
    assert saved_value['sources'] == {samples.name: digest(samples), context.name: digest(context)}
    return rows, json.loads(context.read_text()), report


def main():
    plan = json.loads((ROOT/'case-plan.json').read_text())
    assert plan['source_law']['text'] == ('The driver of a vehicle shall not follow another vehicle more closely '
           'than is reasonable and prudent, having due regard for the speed of such vehicles and the traffic upon '
           'and the condition of the highway.')
    assert len(plan['cases']) == 2 and all(c['planning_status'] == 'unverified' for c in plan['cases'])
    first, context_a, report_a = inspect('condition_a')
    second, context_b, report_b = inspect('condition_b')
    assert context_a == context_b
    assert report_a['median_bumper_gap_m'] == 10.0
    assert report_b['median_bumper_gap_m'] == 25.0
    assert report_a['median_time_headway_s'] == 1.25
    assert report_b['median_time_headway_s'] == 3.125
    for a, b in zip(first, second):
        assert a['ego'] == b['ego']
        assert a['native_frame'] == b['native_frame'] and a['time_s'] == b['time_s']
        for pa, pb in zip(a['lead']['native_body_xy_m'], b['lead']['native_body_xy_m']):
            assert abs(pb[0]-pa[0]-15) < 1e-9 and pa[1] == pb[1]
    summary = json.loads((SAVED/'summary.json').read_text())
    assert len(summary['negatives']) == 6 and all(x['rejected'] for x in summary['negatives'])
    print(json.dumps({'audit': 'pass', 'paired_frames': len(first),
                      'fixed_ego_and_context': True, 'controlled_lead_shift_m': 15,
                      'negative_rejections': 6}, sort_keys=True))


if __name__ == '__main__':
    main()
