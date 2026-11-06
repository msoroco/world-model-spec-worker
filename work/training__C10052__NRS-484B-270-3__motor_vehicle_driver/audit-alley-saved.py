"""Independently recompute saved alley overlap and check source/negative receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def overlap(rect, bounds):
    left,right = min(p[0] for p in rect),max(p[0] for p in rect)
    bottom,top = min(p[1] for p in rect),max(p[1] for p in rect)
    x0,y0,x1,y1 = bounds
    return max(0,min(right,x1)-max(left,x0))*max(0,min(top,y1)-max(bottom,y0))


def audit():
    summary = json.loads((HERE/'alley-saved-summary.json').read_text())
    root = REPO/summary['source_root']
    positive = root/'positive'
    assert sha(positive/'analysis-report.json') == summary['positive_report_sha256']
    assert sha(positive/'result.json') == summary['positive_result_sha256']
    assert sha(root/'positive.log') == summary['positive_log_sha256']
    for name,digest in summary['source_hashes'].items():
        assert sha(positive/name) == digest
    report = json.loads((positive/'analysis-report.json').read_text())
    result = json.loads((positive/'result.json').read_text())
    samples = read_rows(positive/'native_samples.jsonl')
    geometry = json.loads((positive/'road_geometry.json').read_text())
    facility = geometry['bicycle_facility_native_xy_bounds_m']
    alley = geometry['alley_entrance_native_xy_bounds_m']
    assert len(samples) == 480
    first_facility = None; first_alley = None; simultaneous = 0
    prior_facility = 0
    for i,row in enumerate(samples):
        assert row['native_frame'] == 100+i
        assert abs(row['time_s']-(i+1)/20) < 1e-6
        body = row['native_body_xy_m']
        assert len(body) == 4
        assert abs(sum(p[0] for p in body)/4-row['native_center_xy_m'][0]) < 1e-6
        assert abs(sum(p[1] for p in body)/4-row['native_center_xy_m'][1]) < 1e-6
        facility_area = overlap(body,facility)
        alley_area = overlap(body,alley)
        moving = row['speed_mps'] > .1
        if i and first_facility is None and moving and prior_facility <= .01 and facility_area > .01:
            first_facility = row['native_frame']
        if first_alley is None and moving and alley_area > .01:
            first_alley = row['native_frame']
        simultaneous += bool(moving and facility_area > .01 and alley_area > .01)
        prior_facility = facility_area
    measurement = report['measurements']['alley_transition_observation']['value']
    assert (first_facility,first_alley,simultaneous) == (170,201,27)
    assert measurement['first_facility_entry_native_frame'] == first_facility
    assert measurement['first_alley_footprint_native_frame'] == first_alley
    assert measurement['simultaneous_moving_overlap_frames'] == simultaneous
    assert measurement['facility_to_alley_gap_s'] == round((first_alley-first_facility)/20,6)
    assert result['measured_values']['simultaneous_moving_overlap_frames'] == simultaneous
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert sorted(n['name'] for n in summary['negatives']) == ['changed_body','missing_manifest']
    for negative in summary['negatives']:
        log = root/(negative['name']+'.log')
        assert sha(log) == negative['log_sha256'] and negative['exit_code'] != 0
        assert not (root/negative['name']/'result.json').exists()
        expected = ('source hash differs' if negative['name'] == 'changed_body'
                    else 'alley-transition-sources.json')
        assert expected in log.read_text()
    return {'passed':True,'frames':480,'first_facility_frame':first_facility,
            'first_alley_frame':first_alley,'simultaneous_frames':simultaneous,
            'negative_count':2,'selected':False,'accepted':False}


if __name__ == '__main__':
    print(json.dumps(audit(),indent=2))
