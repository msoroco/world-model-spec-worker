"""Independent raw-row audit of the mock original-style parser test."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def area(body,bounds):
    x0,y0,x1,y1 = bounds
    bx0,bx1 = min(p[0] for p in body),max(p[0] for p in body)
    by0,by1 = min(p[1] for p in body),max(p[1] for p in body)
    return max(0,min(x1,bx1)-max(x0,bx0))*max(0,min(y1,by1)-max(y0,by0))


def audit():
    summary = json.loads((HERE/'alley-source-mode-summary.json').read_text())
    root = REPO/summary['source_root']
    folder = root/'positive'
    manifest = json.loads((folder/'alley-transition-sources.json').read_text())
    assert manifest['source_kind'] == 'original_native'
    assert manifest['sha256'] == summary['positive_source_hashes']
    for name,digest in manifest['sha256'].items():assert sha(folder/name) == digest
    values = rows(folder/'native_samples.jsonl')
    geometry = json.loads((folder/'road_geometry.json').read_text())
    facility = geometry['bicycle_facility_native_xy_bounds_m']
    alley = geometry['alley_entrance_native_xy_bounds_m']
    first_facility = None;first_alley = None;simultaneous = 0;prior = 0
    assert len(values) == 480
    for i,row in enumerate(values):
        assert row['native_frame'] == 5010+i
        assert abs(row['time_s']-(8.05+i/20)) < 1e-6
        assert 'synthetic_diagnostic' not in row
        facility_area = area(row['native_body_xy_m'],facility)
        alley_area = area(row['native_body_xy_m'],alley)
        moving = row['speed_mps'] > .1
        if i and first_facility is None and moving and prior <= .01 and facility_area > .01:
            first_facility = row['native_frame']
        if first_alley is None and moving and alley_area > .01:
            first_alley = row['native_frame']
        simultaneous += bool(moving and facility_area > .01 and alley_area > .01)
        prior = facility_area
    assert (first_facility,first_alley,simultaneous) == (5080,5111,27)
    assert summary['first_facility_entry_native_frame'] == first_facility
    assert summary['first_alley_footprint_native_frame'] == first_alley
    assert summary['simultaneous_moving_overlap_frames'] == simultaneous
    assert sorted(n['name'] for n in summary['negatives']) == ['synthetic_relabel','time_drift']
    for negative in summary['negatives']:
        target = root/negative['name']
        assert sha(target/'native_samples.jsonl') == negative['samples_sha256']
        assert sha(target/'native_samples.jsonl') == json.loads(
            (target/'alley-transition-sources.json').read_text())['sha256']['native_samples.jsonl']
    assert summary['physical_observation_claimed'] is False and summary['accepted'] is False
    return {'passed':True,'frames':480,'first_facility_frame':first_facility,
            'first_alley_frame':first_alley,'simultaneous_frames':simultaneous,
            'physical_observation_claimed':False}


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
