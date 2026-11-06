"""Independently audit the synthetic 480-frame same-cell lane comparison."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('lane_fixture', FOLDER/'saved-fixture-proof.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def config(path):
    value = json.loads(path.read_text())
    for key in ('case_id','case_suffix','selected_case_id','supported_case_ids','case'):
        value.pop(key, None)
    return value


def run():
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
        str(ROOT/'runtime/pipeline/python'), str(ROOT/'runtime/pipeline'), env.get('PYTHONPATH','')))
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work', prefix='c382389-pair-') as tmp:
        base = Path(tmp)
        a,b = base/'reference',base/'contrast'
        fixture.make_base(a,'reference',-1.75,480)
        fixture.make_base(b,'contrast',-5.25,480)
        assert config(a/'config.json') == config(b/'config.json')
        assert (a/'road_geometry.json').read_bytes() == (b/'road_geometry.json').read_bytes()
        for source in (a,b):
            before = fixture.source_digest(source)
            result = subprocess.run([sys.executable,str(FOLDER/'native/finalize.py'),
                '--attempt',str(source),'--output',str(source/'analysis-report.json')],
                env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            if result.returncode: raise RuntimeError(result.stdout)
            assert fixture.source_digest(source) == before
        left,right = [json.loads((source/'analysis-report.json').read_text()) for source in (a,b)]
        lv = left['measurements']['right_only_lane_through_crossing']['value']
        rv = right['measurements']['right_only_lane_through_crossing']['value']
        assert left['original_joins']['frames'] == right['original_joins']['frames'] == 480
        assert all(v == 480 for report in (left,right) for v in report['video_frames'].values())
        assert (lv['observed_approach_lane_id'],rv['observed_approach_lane_id']) == (-1,-2)
        assert (lv['right_only_lane_intersection_sample_fraction'],rv['right_only_lane_intersection_sample_fraction']) == (0,1)
        assert (lv['straight_through_from_right_only_lane_observed'],rv['straight_through_from_right_only_lane_observed']) == (False,True)
        assert not lv['right_only_lane_design_native_verified'] and not rv['right_only_lane_design_native_verified']
        motion = [rows(source/'native_samples.jsonl') for source in (a,b)]
        for first,second in zip(*motion):
            for key in ('native_frame','time_s','native_road_id','native_forward_xy'):
                assert first[key] == second[key], key
            assert first['native_center_xy_m'][0] == second['native_center_xy_m'][0]
            assert first['native_center_xy_m'][1] - 3.5 == second['native_center_xy_m'][1]
            assert (first['native_lane_id'],second['native_lane_id']) == (-1,-2)
        return {'format':'c382389-4b-synthetic-saved-pair-audit-v1',
            'frames_per_case':480,'source_unchanged':True,
            'fixed':'cell, law, actor, geometry, straight movement, x/time/frame/road trace, rate, cameras and channels',
            'deliberate_difference':'approach lane ID and 3.5 m lateral placement',
            'measured_lane_ids':[-1,-2], 'intersection_right_only_fractions':[0,1],
            'native_right_only_design_verified':False,
            'scope':'synthetic saved comparison only; no physical or legal outcome proof'}


if __name__ == '__main__': print(json.dumps(run(),indent=2))
