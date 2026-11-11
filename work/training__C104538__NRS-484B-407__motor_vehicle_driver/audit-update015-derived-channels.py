"""Audit the current saved finalizer's 480-row raw-to-channel diagnostic."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ATTEMPT = REPO / '.runtime-work/c104538-update015-derived-channel-positive-v2'
NAMES = ('drv.u_turn','st.curvature','st.grade','st.crest',
         'st.sight_distance','rel.oncoming','drv.approaching','kin.position')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    positive=(HERE/'update015-derived-channel-positive-v2.log').read_text()
    negative=(HERE/'update015-derived-channel-missing-rays.log').read_text()
    assert '"format": "c104538-saved-analysis-v1"' in positive
    assert 'Missing required source: driver_eye_rays.jsonl' in negative
    trace=rows(ATTEMPT/'trace.jsonl')
    history=rows(ATTEMPT/'native_body_history.jsonl')
    rays=rows(ATTEMPT/'driver_eye_rays.jsonl')
    mapping=rows(ATTEMPT/'video_frames.jsonl')
    channels={name:rows(ATTEMPT/'channels'/(name+'.jsonl')) for name in NAMES}
    assert all(len(series)==480 for series in (trace,history,rays,mapping,*channels.values()))
    for index,(t,h,v,m) in enumerate(zip(trace,history,rays,mapping)):
        frame=m['native_frame'];time=m['time_s']
        assert t['frame']==h['native_frame']==v['native_frame']==frame
        assert all(abs(item-time)<1e-4 for item in (t['time_s'],h['time_s'],v['time_s']))
        for channel in channels.values():
            assert channel[index]['native_frame']==frame
            assert abs(channel[index]['time_s']-time)<1e-4
        assert channels['kin.position'][index]['value']==t['position_m']
        assert channels['drv.u_turn'][index]['value']['observed_body_vertices_m']==h['ego_body_vertices_m']
        assert channels['st.sight_distance'][index]['value']['approaching_driver_views']==v['views']
        assert channels['st.sight_distance'][index]['value']['original_body_and_pixel_visibility_verified'] is False
        assert channels['rel.oncoming'][index]['value']['actual_approach_direction_verified'] is False
    result=json.loads((ATTEMPT/'result.json').read_text())
    report=json.loads((ATTEMPT/'analysis-report.json').read_text())
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert result['target_checks'][0]['matched'] is False
    assert report['case_id']==result['case_id']
    assert {item['name'] for item in result['recording_evidence']}==set(NAMES)
    return {'frames':480,'derived_channels':8,'raw_joins_checked':3840,
            'missing_raw_negative_rejected':True,'accepted':False,
            'positive_result_sha256':sha(ATTEMPT/'result.json')}


if __name__=='__main__':
    print(json.dumps(audit(),sort_keys=True))
