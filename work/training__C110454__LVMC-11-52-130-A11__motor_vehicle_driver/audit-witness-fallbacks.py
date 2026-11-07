"""Independently measure each parking fallback against its exact manifest threshold."""
import hashlib
import json
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--numeric', action='store_true')
    args = parser.parse_args()
    source_path = HERE / ('numeric-fallback-source.json' if args.numeric else 'witness-fallback-source.json')
    source = json.loads(source_path.read_text())
    manifest = json.loads((HERE / ('draft-numeric-execution-manifest.json' if args.numeric else 'draft-execution-manifest.json')).read_text())
    assert source['format'] == 'c110454-parking-trigger-source-v1'
    assert source['source_kind'] == 'synthetic_cpu'
    assert manifest['status'] == 'draft_not_selected'
    rows = []
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        evidence = source['cases'][case]
        assert sha(ROOT / '.runtime-work/c110454-lvmc-synthetic' / (case+'-native.json')) == evidence['saved_source_sha256']
        assert sha(HERE / 'native/routes' / (case+'.json')) == evidence['route_sha256']
        assert len(entry['candidates']) == 3
        assert {c['id'] for c in entry['candidates']} == {'fallback1','fallback2','fallback3'}
        assert {c['changed_knobs'][0] for c in entry['candidates']} == {
            'route_lookahead_m','parking_brake_start_m','overview_fov_deg'}
        values = {}
        for name, samples in evidence['scenarios'].items():
            assert len(samples) == 480 and [r['frame'] for r in samples] == list(range(480))
            assert all(len(r['overview_body_bbox_px']) == 4 for r in samples)
            parked = samples[400:]
            route_error = max(r['route_error_m'] for r in samples)
            endpoint_speed = max(r['speed_m_s'] for r in parked)
            width, height = 1920, 1080
            margin = min(min(x1, y1, width-x2, height-y2)
                         for x1,y1,x2,y2 in (r['overview_body_bbox_px'] for r in parked))
            values[name] = {'max_park_route_cross_track_error_m':route_error,
                            'parked_endpoint_speed_m_s':endpoint_speed,
                            'min_parked_ego_pixel_margin_px':margin}
        for candidate in entry['candidates']:
            trigger = candidate['trigger']
            metric, op, threshold = trigger['metric'], trigger['op'], trigger['threshold']
            assert metric in values['baseline'] and op in ('>','<')
            crossing = {'fallback1':'route_error','fallback2':'endpoint_speed','fallback3':'pixel_margin'}[candidate['id']]
            decision = lambda v: v > threshold if op == '>' else v < threshold
            assert not decision(values['baseline'][metric])
            assert decision(values[crossing][metric])
            assert sum(decision(values[name][metric]) for name in values) == 1
            rows.append({'case_id':entry['case_id'],'candidate':candidate['id'],
                         'metric':metric,'op':op,'threshold':threshold,
                         'baseline':values['baseline'][metric],
                         'crossing':values[crossing][metric],
                         'crossing_scenario':crossing})
    assert len(rows) == (9 if args.numeric else 6)
    receipt = {'format':'c110454-parking-trigger-audit-v1','passed':True,
               'source_sha256':sha(source_path),'source_kind':'synthetic_cpu',
               'original_native_or_pixels_observed':False,'rows':rows}
    (HERE/('numeric-fallback-audit.json' if args.numeric else 'witness-fallback-audit.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,sort_keys=True))


if __name__ == '__main__':
    main()
