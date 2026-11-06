"""Pinned CPU integration of the original-shaped source parser with synthetic data."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.package_compatibility import run

spec=importlib.util.spec_from_file_location('fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
from trigger_measure import measure as measure_triggers
from engineering import evaluate_trigger


def main():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c111294-original-shaped-') as temporary:
        scratch=Path(temporary)
        source=scratch/'fixture';fixture.make(source,'witness_2',full_resolution=True)
        fixture.emulate_original_shape(source)
        metrics=measure_triggers(source)
        if metrics['source_kind']!='synthetic_original_shape_emulation':
            raise ValueError('Synthetic trigger provenance differs')
        trigger_path=source/'fallback-metrics.json'
        trigger_path.write_text(json.dumps(metrics,sort_keys=True)+'\n')
        from measure import sha
        try:evaluate_trigger('fallback1',metrics,trigger_path,sha(trigger_path))
        except ValueError as error:
            if 'not bound to original' not in str(error):raise
        else:raise ValueError('Synthetic trigger metrics accepted as original')
        (source/'config.json').unlink()
        case=HERE.name+'__witness_2'
        receipt=run(HERE/'draft-execution-manifest.json',case,source,scratch/'output',
            ROOT/'runtime/pipeline/library',
            ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck','primary')
        result=json.loads((scratch/'output/result.json').read_text())
        value=result['measured_values']['bicycle_motorist_interaction']
        if value['physical_behavior_observed'] or value['human_propulsion_physically_verified'] or result['accepted']:
            raise ValueError('Synthetic original-shape emulation claimed physical observation')
        return {'passed':True,'case_id':case,'candidate':'primary',
            'construction_sha256':receipt['construction_sha256'],
            'checks':receipt['checks'],'source_kind':'synthetic_original_shape_emulation',
            'measured_trigger_metrics':{key:metrics[key] for key in (
                'max_bicycle_route_cross_track_error_m',
                'min_motorist_conflict_clearance_s',
                'min_projected_body_frame_margin_px')},
            'physical_behavior_observed':False,'accepted':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
