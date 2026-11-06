"""Independently audit the 480-frame synthetic left-turn exit-side pair."""
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('exit_fixture',FOLDER/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def config(path):
    value=json.loads(path.read_text())
    for key in ('case_id','case_suffix','selected_case_id','supported_case_ids','case'):
        value.pop(key,None)
    return value


def run():
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
       str(ROOT/'runtime/pipeline/python'),str(ROOT/'runtime/pipeline'),env.get('PYTHONPATH','')))
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c329610-exit-pair-') as temporary:
        a=Path(temporary)/'witness_1';b=Path(temporary)/'witness_2'
        fixture.make_base(a,'witness_1',1.75,480)
        fixture.make_base(b,'witness_2',-1.75,480)
        assert config(a/'config.json')==config(b/'config.json')
        assert (a/'road_geometry.json').read_bytes()==(b/'road_geometry.json').read_bytes()
        for source in (a,b):
            before=fixture.source_digest(source)
            result=subprocess.run([sys.executable,str(FOLDER/'native/finalize.py'),
                '--attempt',str(source),'--output',str(source/'analysis-report.json')],
                env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            if result.returncode:raise RuntimeError(result.stdout)
            assert fixture.source_digest(source)==before
        left,right=[json.loads((source/'analysis-report.json').read_text()) for source in (a,b)]
        lv=left['measurements']['destination_exit_geometry']['value']
        rv=right['measurements']['destination_exit_geometry']['value']
        assert left['original_joins']['frames']==right['original_joins']['frames']==480
        assert all(v==480 for report in (left,right) for v in report['video_frames'].values())
        assert (lv['geometric_side'],rv['geometric_side'])==('right','left')
        assert lv['full_body_exit_observed'] and rv['full_body_exit_observed']
        for value in (lv,rv):
            assert value['intersection_entry_observed']
            entry=value['first_intersection_entry_time_bracket_s']
            exit_window=value['first_full_body_exit_time_bracket_s']
            assert entry[0] is not None and entry[0]<entry[1]<=exit_window[0]<exit_window[1]
        motion=[rows(source/'native_samples.jsonl') for source in (a,b)]
        assert len(motion[0])==len(motion[1])==480
        for index,(first,second) in enumerate(zip(*motion)):
            for key in ('native_frame','time_s','native_forward_xy'):
                assert first[key]==second[key],key
            assert math.isclose(first['native_center_xy_m'][1],second['native_center_xy_m'][1],abs_tol=1e-10)
            expected=0 if index<160 else -3.5*(index-160)/159 if index<320 else -3.5
            assert math.isclose(second['native_center_xy_m'][0]-first['native_center_xy_m'][0],expected,abs_tol=1e-10)
            if index<160:assert first==second,'Approach changed before the controlled exit divergence'
        return {'format':'c329610-2b-synthetic-saved-pair-audit-v1',
            'frames_per_case':480,'source_unchanged':True,
            'fixed':'cell, actor, law, road geometry, first 160 approach frames, frame/time/y/heading trace, rate, cameras and channels',
            'deliberate_difference':'destination lateral exit x=1.75 m versus -1.75 m',
            'measured_full_body_exit_sides':['right','left'],
            'sampled_entry_before_exit_both_cases':True,
            'scope':'synthetic saved controlled comparison only; no Native physical or legal outcome proof'}


if __name__=='__main__':print(json.dumps(run(),indent=2))
