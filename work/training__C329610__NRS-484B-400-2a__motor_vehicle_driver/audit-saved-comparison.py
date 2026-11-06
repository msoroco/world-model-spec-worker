"""Independently audit the synthetic 480-frame centerline-offset pair."""
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
spec=importlib.util.spec_from_file_location('offset_fixture',FOLDER/'saved-fixture-proof.py')
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
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c329610-offset-pair-') as temporary:
        a=Path(temporary)/'controlled_1';b=Path(temporary)/'controlled_2'
        fixture.make_base(a,'controlled_1',-1.75,480)
        fixture.make_base(b,'controlled_2',-5.25,480)
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
        lv=left['measurements']['approach_placement_geometry']['value']
        rv=right['measurements']['approach_placement_geometry']['value']
        assert left['original_joins']['frames']==right['original_joins']['frames']==480
        assert all(v==480 for report in (left,right) for v in report['video_frames'].values())
        assert (lv['sampled_right_offset_m']['mean'],rv['sampled_right_offset_m']['mean'])==(1.75,5.25)
        assert lv['full_body_right_half'] and rv['full_body_right_half']
        assert lv['destination_exit_observed'] and rv['destination_exit_observed']
        motion=[rows(source/'native_samples.jsonl') for source in (a,b)]
        assert len(motion[0])==len(motion[1])==480
        for index,(first,second) in enumerate(zip(*motion)):
            for key in ('native_frame','time_s','native_forward_xy'):
                assert first[key]==second[key],key
            assert math.isclose(first['native_center_xy_m'][0],second['native_center_xy_m'][0],abs_tol=1e-10)
            expected=-3.5 if index<160 else -3.5*(1-(index-160)/159) if index<320 else 0
            assert math.isclose(second['native_center_xy_m'][1]-first['native_center_xy_m'][1],expected,abs_tol=1e-10)
        return {'format':'c329610-2a-synthetic-saved-pair-audit-v1',
            'frames_per_case':480,'source_unchanged':True,
            'fixed':'cell, actor, law, road geometry, movement, frame/time/x/heading trace, rate, cameras and channels',
            'deliberate_difference':'approach centerline offset: 1.75 m versus 5.25 m, converging to same left-turn destination',
            'measured_mean_approach_offsets_m':[1.75,5.25],
            'both_full_body_within_right_half':True,'both_destination_exits_observed':True,
            'scope':'synthetic saved controlled comparison only; no Native physical or legal outcome proof'}


if __name__=='__main__':print(json.dumps(run(),indent=2))
