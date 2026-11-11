"""Exercise raw saved right-turn finalization on both synthetic cases."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
spec=importlib.util.spec_from_file_location('c110919_fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from finalize import finalize


def run():
    for suffix in ('reference','contrast'):
        attempt=REPO/'.runtime-work'/'c110919-update015-saved-raw'/suffix
        attempt.parent.mkdir(parents=True,exist_ok=True)
        if attempt.exists():shutil.rmtree(attempt)
        fixture.make_attempt(attempt,suffix,full_resolution=False)
        if (attempt/'channels').exists():raise ValueError('Fixture supplied derived channels')
        report=finalize(attempt,attempt/'analysis-report.json')
        result=json.loads((attempt/'result.json').read_text())
        if (report['original_joins']['frames']!=480 or result['accepted'] is not False or
            result['setup_confirmed'] is not False or result['behavior_attempted'] is not False or
            result['maneuver_completed'] is not False or len(result['recording_evidence'])!=10):
            raise ValueError('Synthetic right-turn saved proof claimed physical success')
        print(json.dumps({'case':suffix,'frames':480,'derived_channels':10,
              'stationary_pre_crossing_frames':result['measured_values']['stop']['stationary_pre_crossing_frames'],
              'provenance':result['provenance_kind']}),flush=True)


if __name__=='__main__':run()
