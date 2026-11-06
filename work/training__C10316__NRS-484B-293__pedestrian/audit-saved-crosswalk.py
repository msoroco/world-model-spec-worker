"""Independent retained saved-source, video, contract and controlled-pair audit."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import verify_report


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def video(path):
    result=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                           '-show_entries','stream=width,height,nb_read_frames','-of','json',
                           str(path)],text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,timeout=120)
    assert result.returncode==0
    stream=json.loads(result.stdout)['streams'][0]
    return int(stream['nb_read_frames']),int(stream['width']),int(stream['height'])


def main():
    summary=json.loads((HERE/'saved-crosswalk-summary.json').read_text())
    assert len(summary['records'])==2
    pairs=[]
    for record in summary['records']:
        suffix=record['case_suffix'];positive=Path(record['retained_positive'])
        assert positive.is_relative_to(ROOT/'.runtime-work')
        assert sha(positive/'analysis-report.json')==record['analysis_report_sha256']
        assert sha(positive/'result.json')==record['result_sha256']
        current={str(path.relative_to(positive)):sha(path) for path in positive.rglob('*')
                 if path.is_file() and path.name not in ('result.json','analysis-report.json')}
        assert current==record['original_source_hashes']
        config=json.loads((positive/'config.json').read_text())
        report=json.loads((positive/'analysis-report.json').read_text())
        result=json.loads((positive/'result.json').read_text())
        contract=json.loads((HERE/'draft-crosswalk'/suffix/'measurement-contract.json').read_text())
        verify_report(contract,report,positive)
        assert result['case_id']==record['case_id']==config['case_id']
        assert result['accepted'] is False and result['legal_verdict_claimed'] is False
        assert result['setup_confirmed'] is False and result['behavior_attempted'] is False
        assert result['maneuver_completed'] is False
        assert result['provenance_kind']=='synthetic_local_diagnostic'
        context=json.loads((positive/'crosswalk-context.json').read_text())
        assert context['source_kind']=='synthetic_scene_request'
        assert all(item['observed'] is None for item in context['practicability_facts'])
        trace,evidence,mapping,samples,native=(rows(positive/name) for name in (
            'trace.jsonl','capture/evidence.jsonl','video_frames.jsonl',
            'native_samples.jsonl','capture/native/frames.jsonl'))
        assert all(len(x)==240 for x in (trace,evidence,mapping,samples,native))
        for i,(t,e,m,s,n) in enumerate(zip(trace,evidence,mapping,samples,native)):
            frame=100+i
            assert (t['frame'],e['original_frame'],m['native_frame'],s['native_frame'],n['frame'])==(frame,)*5
            assert m['video_frame']==i and m['carla_frame']==frame
            assert abs(t['time_s']-i/20)<1e-5
            body3={(round(p[0],3),round(p[1],3)) for p in e['ego']['body_vertices_m']}
            body2={(round(p[0],3),round(p[1],3)) for p in s['pedestrian_footprint_xy_m']}
            assert body3==body2 and len(body2)==4
        for camera in config['cameras']:
            assert video(positive/(camera['name']+'.mkv'))==(240,camera['width'],camera['height'])
        for channel in config['recording_description']['channels']:
            assert len(rows(positive/'channels'/(channel['name']+'.jsonl')))==240
        observation=report['measurements']['right_half_passage']['value']
        expected='right' if suffix=='reference' else 'left'
        assert observation['observed_half']==expected
        assert observation['crosswalk_frames']==112
        assert observation['practicability_verified'] is False
        for label,missing in (('missing','native_samples.jsonl'),('missing-video','overview.mkv')):
            negative=positive.parent/(suffix+'-'+label)
            assert not (negative/missing).exists()
        wrong=positive.parent/(suffix+'-wrong-footprint')
        assert sha(wrong/'capture/evidence.jsonl')!=sha(positive/'capture/evidence.jsonl')
        pairs.append((context,samples,trace,result))
    a_context,a_samples,a_trace,a_result=pairs[0]
    b_context,b_samples,b_trace,b_result=pairs[1]
    assert a_context==b_context
    assert a_result['measured_values']['observed_crosswalk_half']=='right'
    assert b_result['measured_values']['observed_crosswalk_half']=='left'
    for a,b,ta,tb in zip(a_samples,b_samples,a_trace,b_trace):
        assert {k:v for k,v in a.items() if k not in ('pedestrian_xy_m','pedestrian_footprint_xy_m')}=={
            k:v for k,v in b.items() if k not in ('pedestrian_xy_m','pedestrian_footprint_xy_m')}
        assert a['pedestrian_xy_m'][0]==b['pedestrian_xy_m'][0]
        assert abs(b['pedestrian_xy_m'][1]-a['pedestrian_xy_m'][1]-1.3)<1e-9
        assert ta['frame']==tb['frame'] and ta['time_s']==tb['time_s']
    print(json.dumps({'audit':'pass','retained_positive_cases':2,'frames_per_case':240,
                      'source_videos_decoded':8,'negative_rejections':6,
                      'controlled_lateral_shift_m':1.3,'accepted_recordings':0},sort_keys=True))


if __name__=='__main__':main()
