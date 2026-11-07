"""Independent 480-frame synthetic controlled-pair audit; no physical claim."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('right_turn_fixture',FOLDER/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def checked_config(path):
    config=json.loads(path.read_text())
    for key in ('case_id','case_suffix','selected_case_id','supported_case_ids','case'):
        config.pop(key)
    return config


def run():
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
        str(ROOT/'runtime/pipeline/python'),str(ROOT/'runtime/pipeline'),env.get('PYTHONPATH','')))
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c382355-pair-') as temporary:
        root=Path(temporary)
        left=root/'witness_1';right=root/'witness_2'
        fixture.make_base(left,'witness_1',5.25,480)
        fixture.make_base(right,'witness_2',1.75,480)
        assert checked_config(left/'config.json')==checked_config(right/'config.json')
        assert (left/'road_geometry.json').read_bytes()==(right/'road_geometry.json').read_bytes()
        for source in (left,right):
            before=fixture.source_digest(source)
            command=[sys.executable,str(FOLDER/'native/finalize.py'),'--attempt',str(source),
                     '--output',str(source/'analysis-report.json')]
            result=subprocess.run(command,env=env,text=True,stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT,timeout=180)
            if result.returncode:raise RuntimeError(result.stdout)
            if fixture.source_digest(source)!=before:
                raise RuntimeError('Saved finalizer changed original sources')
        l=json.loads((left/'analysis-report.json').read_text())
        r=json.loads((right/'analysis-report.json').read_text())
        for source,report in ((left,l),(right,r)):
            result=json.loads((source/'result.json').read_text())
            assert report['acquisition_provenance']['native_executed'] is False
            assert result['provenance_kind']=='synthetic_local_diagnostic'
            assert result['setup_confirmed'] is False
            assert result['behavior_attempted'] is False
            assert result['maneuver_completed'] is False
        lv=l['measurements']['right_turn_lane_occupancy']['value']
        rv=r['measurements']['right_turn_lane_occupancy']['value']
        assert l['original_joins']['frames']==r['original_joins']['frames']==480
        assert all(count==480 for count in l['video_frames'].values())
        assert all(count==480 for count in r['video_frames'].values())
        assert lv['approach_lane_identity_fraction']==1
        assert rv['approach_lane_identity_fraction']==0
        assert lv['full_body_in_right_turn_lane_approach_samples'] is True
        assert rv['full_body_in_right_turn_lane_approach_samples'] is False
        assert lv['right_turn_observed_at_complete_exit'] is True
        assert rv['right_turn_observed_at_complete_exit'] is True
        assert lv['right_turn_lane_design_native_verified'] is False
        assert rv['right_turn_lane_design_native_verified'] is False
        motion=[read_rows(source/'native_samples.jsonl') for source in (left,right)]
        assert len(motion[0])==len(motion[1])==480
        assert [row['native_frame'] for row in motion[0]]==[row['native_frame'] for row in motion[1]]
        assert [row['time_s'] for row in motion[0]]==[row['time_s'] for row in motion[1]]
        for first,second in zip(*motion):
            assert first['native_road_id']==second['native_road_id']
            if first['native_road_id']==1:
                assert first['native_lane_id']==-2 and second['native_lane_id']==-1
                assert first['native_center_xy_m'][0]==second['native_center_xy_m'][0]
            else:
                assert first['native_lane_id']==second['native_lane_id']==-2
        return {'format':'c382355-synthetic-controlled-pair-audit-v1',
                'frames_per_case':480,'cases':2,
                'fixed':['cell','law','actor','duration','rate','camera policies',
                         'recording channels','road geometry','frame/time IDs',
                         'approach longitudinal stations','right-turn connector'],
                'deliberate_difference':'approach lane and lateral path to shared right-turn connector',
                'measured_approach_lane_identity_fractions':[1,0],
                'right_turn_complete_both':True,'right_only_design_verified':False,
                'source_unchanged':True,
                'synthetic_physical_flags_false':True,
                'scope':'synthetic saved controlled comparison only; no Native physical or legal outcome proof'}


if __name__=='__main__':print(json.dumps(run(),indent=2))
