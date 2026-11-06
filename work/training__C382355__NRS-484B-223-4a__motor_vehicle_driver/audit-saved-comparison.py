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
        left=root/'controlled_1';right=root/'controlled_2'
        fixture.make_base(left,'controlled_1',-5.25,480)
        fixture.make_base(right,'controlled_2',-5.25,480)
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
        lv=l['measurements']['right_only_lane_subsequent_movement']['value']
        rv=r['measurements']['right_only_lane_subsequent_movement']['value']
        assert l['original_joins']['frames']==r['original_joins']['frames']==480
        assert all(count==480 for count in l['video_frames'].values())
        assert all(count==480 for count in r['video_frames'].values())
        assert lv['right_only_lane_identity_fraction']==rv['right_only_lane_identity_fraction']==1
        assert lv['full_body_in_right_only_lane_approach_samples'] is True
        assert rv['full_body_in_right_only_lane_approach_samples'] is True
        assert lv['observed_subsequent_movement']=='right_turn_follows'
        assert rv['observed_subsequent_movement']=='straight_follows'
        assert lv['right_only_lane_design_native_verified'] is False
        assert rv['right_only_lane_design_native_verified'] is False
        motion=[read_rows(source/'native_samples.jsonl') for source in (left,right)]
        assert len(motion[0])==len(motion[1])==480
        assert [row['native_frame'] for row in motion[0]]==[row['native_frame'] for row in motion[1]]
        assert [row['time_s'] for row in motion[0]]==[row['time_s'] for row in motion[1]]
        for index,(first,second) in enumerate(zip(*motion)):
            if index<160:
                assert first==second,'Approach changed before the controlled movement'
            elif index<320:
                assert (first['native_road_id'],second['native_road_id'])==(13,14)
            else:
                assert (first['native_road_id'],second['native_road_id'])==(4,2)
        return {'format':'c382355-4a-synthetic-controlled-pair-audit-v1',
                'frames_per_case':480,'cases':2,
                'fixed':['cell','law','actor','duration','rate','camera policies',
                         'recording channels','road geometry','frame/time IDs',
                         'complete 160-frame approach body/road/lane trace'],
                'deliberate_difference':'subsequent movement: right turn versus straight continuation',
                'measured_approach_lane_identity_fractions':[1,1],
                'measured_subsequent_movements':['right_turn_follows','straight_follows'],
                'right_only_design_verified':False,
                'source_unchanged':True,
                'scope':'synthetic saved controlled comparison only; no Native physical or legal outcome proof'}


if __name__=='__main__':print(json.dumps(run(),indent=2))
