"""Independent audit of the two saved CPU fixtures and processor negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(FOLDER/'native'))
from measure_saved import measure


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    root=FOLDER/'synthetic-local'
    map_sha=sha(FOLDER/'draft-construction/scene.xodr')
    counts={}
    for case in ('controlled_1','controlled_2'):
        folder=root/case
        report=json.loads((folder/'analysis-report.json').read_text())
        rows=[json.loads(s) for s in (folder/'native_samples.jsonl').read_text().splitlines()]
        assert len(rows)==480 and [r['native_frame'] for r in rows]==list(range(480))
        assert report['case']==case and report['source_kind']=='synthetic_cpu'
        assert report['map_sha256']==map_sha
        assert report['requested_movement_observed_in_saved_rows'] is True
        assert report['actual_native_or_pixels_verified'] is False
        assert report['declared_purpose_is_observed_driver_intent'] is False
        assert report['legal_verdict'] is None
        for name,digest in report['source_hashes'].items():assert digest==sha(folder/name)
        assert report==measure(folder)
        full=[r for r in rows if r['native_road_id'] in (1,14,2) and r['native_lane_id']==-1
              and all(-1.75<=p[1]<=1.75 for p in r['native_body_xy_m'])]
        assert report['measured']['center_full_body_frames']==len(full)
        if case=='controlled_1':
            assert report['measured']['first_left_connector_frames']>0
            assert report['measured']['later_left_connector_frames']==0
        else:
            assert report['measured']['first_opportunity_center_through_frames']>0
            assert report['measured']['later_through_full_body_frames']>0
            assert report['measured']['later_left_connector_frames']>0
        counts[case]=len(full)
    source=root/'controlled_1'
    with tempfile.TemporaryDirectory() as temporary:
        destination=Path(temporary)/'damaged'
        shutil.copytree(source,destination)
        purpose=destination/'declared_purpose.json'
        data=json.loads(purpose.read_text());data['law_text_sha256']='0'*64
        purpose.write_text(json.dumps(data))
        try:measure(destination)
        except ValueError:pass
        else:raise AssertionError('Wrong law source was accepted')
        shutil.copyfile(source/'declared_purpose.json',purpose)
        rows=(destination/'native_samples.jsonl').read_text().splitlines()
        data=json.loads(rows[100]);data['native_body_xy_m']=None;rows[100]=json.dumps(data)
        (destination/'native_samples.jsonl').write_text('\n'.join(rows)+'\n')
        try:measure(destination)
        except ValueError:pass
        else:raise AssertionError('Missing body footprint was accepted')
    return {'passed':True,'synthetic_frame_counts':{'controlled_1':480,'controlled_2':480},
            'center_full_body_frames':counts,'wrong_law_rejected':True,
            'missing_body_rejected':True,'physical_or_legal_verdict_claimed':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
