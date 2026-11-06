"""Independent receipt and saved-source audit for the 480-frame synthetic probe."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
PARENT=REPO/'.runtime-work/c104538/full-saved-v1'
CAMERAS=('overview','reference_left','reference_right','ego')
CHANNELS=('drv.u_turn','st.curvature','st.grade','st.crest',
          'st.sight_distance','rel.oncoming','drv.approaching','kin.position')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):return json.loads(Path(path).read_text())


def audit():
    summary=read(ROOT/'full-saved-summary.json')
    assert summary['positive_count']==summary['negative_count']==3
    assert summary['frames_per_case']==480 and summary['recording_accepted'] is False
    seen=set();probe=REPO/'.runtime-work/linux_arm64/ffprobe'
    for item in summary['cases']:
        case=item['case_id'];suffix=case.split('__')[-1];assert suffix not in seen
        seen.add(suffix)
        pos=PARENT/suffix/'positive';neg=PARENT/suffix/'negative_missing_body'
        assert read(pos/'config.json')['case_id']==case
        assert read(pos/'config.json')['synthetic_fixture'] is True
        assert read(pos/'capture/manifest.json')['frames']==480
        assert read(pos/'capture/manifest.json')['extraction_confirmed'] is True
        contract=ROOT/'draft-candidates'/suffix/'measurement-contract.json'
        assert sha(contract)==item['contract_sha256']
        assert sha(pos/'analysis-report.json')==item['positive_report_sha256']
        assert sha(pos/'result.json')==item['positive_result_sha256']
        assert sha(pos/'trace.jsonl')==item['positive_trace_sha256']
        assert sha(pos/'ego.mkv')==item['positive_video_sha256']
        result=read(pos/'result.json');report=read(pos/'analysis-report.json')
        assert result['case_id']==report['case_id']==case
        assert result['provenance_kind']=='synthetic'
        assert not any((result['accepted'],result['legal_verdict_claimed'],
                        result['setup_confirmed'],result['target_checks'][0]['matched']))
        measured=result['measured_values']
        assert measured['original_frames']==480
        assert measured['actual_body_visibility_proven'] is False
        assert measured['original_pixel_visibility_proven'] is False
        assert report['video_frames']=={name:480 for name in CAMERAS}
        for name in ('trace.jsonl','capture/evidence.jsonl','native_body_history.jsonl',
                     'driver_eye_rays.jsonl','video_frames.jsonl'):
            assert len((pos/name).read_text().splitlines())==480
        for name in CHANNELS:
            assert len((pos/'channels'/(name+'.jsonl')).read_text().splitlines())==480
        for name in CAMERAS:
            decoded=subprocess.run([str(probe),'-v','error','-count_frames',
                '-select_streams','v:0','-show_entries','stream=nb_read_frames',
                '-of','default=noprint_wrappers=1:nokey=1',str(pos/(name+'.mkv'))],
                capture_output=True,text=True,check=True,timeout=120)
            assert decoded.stdout.strip()=='480'
        assert not (neg/'native_body_history.jsonl').exists()
        for receipt in item['receipts']:
            assert sha(ROOT/receipt['log'])==receipt['log_sha256']
            log=(ROOT/receipt['log']).read_text()
            if receipt['label']=='positive':assert receipt['exit_code']==0
            else:
                assert receipt['label']=='negative_missing_body' and receipt['exit_code']!=0
                assert 'Missing required source: native_body_history.jsonl' in log
    return {'cases_audited':len(seen),'decoded_video_streams':len(seen)*len(CAMERAS),
            'positive_contracts':len(seen),'negative_rejections':len(seen),
            'physical_native_runs':0,'accepted_recordings':0}


if __name__=='__main__':print(json.dumps(audit()))
