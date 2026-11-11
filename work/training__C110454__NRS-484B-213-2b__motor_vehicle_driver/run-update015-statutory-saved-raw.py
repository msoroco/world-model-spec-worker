"""Exercise current statutory finalization on four source-shaped raw attempts."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
spec=importlib.util.spec_from_file_location('stat_fixture',HERE/'saved-statutory-fixture.py')
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from finalize_statutory import finalize


def run():
    for suffix in ('rail_reference','rail_contrast','oneway_absent','oneway_present'):
        attempt=REPO/'.runtime-work'/'c110454-update015-statutory-raw'/suffix
        attempt.parent.mkdir(parents=True,exist_ok=True)
        if attempt.exists():shutil.rmtree(attempt)
        fixture.make_base(attempt,suffix,480)
        if (attempt/'channels').exists():raise ValueError('Fixture supplied derived channels')
        report=finalize(attempt,attempt/'analysis-report.json')
        result=json.loads((attempt/'result.json').read_text())
        if (report['original_joins']['frames']!=480 or result['accepted'] is not False or
            result['setup_confirmed'] is not False or result['behavior_attempted'] is not False or
            result['maneuver_completed'] is not False or len(result['recording_evidence'])<11):
            raise ValueError('Synthetic statutory saved proof claimed physical success')
        print(json.dumps({'case':suffix,'frames':480,'derived_channels':11,
              'relation':result['measured_values']['sampled_relation'],
              'provenance':result['provenance_kind']}),flush=True)


if __name__=='__main__':run()
