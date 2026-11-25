"""Check exact materialized source recipes and missing-source rejection."""
import json
import os
from pathlib import Path
import shutil
import tempfile

from audit_comparison import audit
from measure_scooter import measure


def main():
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).parent
    cases = ('controlled_1', 'controlled_at_cap', 'controlled_2')
    sources = {'controlled_1': root/'c230224-public-c1-v10',
               'controlled_at_cap': root/'c230224-public-cap-v2',
               'controlled_2': root/'c230224-public-c2-v2'}
    reports = {suffix: measure(sources[suffix]) for suffix in cases}
    if [reports[suffix]['above_15_mph_frames'] for suffix in cases] != [0, 0, 600]:
        raise AssertionError('15 mph continuous boundary mismatch')
    if abs(reports['controlled_at_cap']['max_speed_mph'] - 15) > 1e-10:
        raise AssertionError('At-cap fixture measurement mismatch')
    audit(reports['controlled_1'], reports['controlled_2'], original_only=False)
    with tempfile.TemporaryDirectory(prefix='scooter-missing-source-', dir=os.environ['TMPDIR']) as temp:
        target = Path(temp)
        source = sources['controlled_1']
        for name in ('video_frames.jsonl', 'native_rider_trace.jsonl', 'scooter_context.json'):
            shutil.copyfile(source/name, target/name)
        (target/'scooter_context.json').unlink()
        try:
            measure(target)
        except ValueError as error:
            if 'Missing required source: scooter_context.json' not in str(error):
                raise
        else:
            raise AssertionError('Missing source was accepted')
    print(json.dumps({'cases': list(cases), 'measured_mph': [reports[s]['max_speed_mph'] for s in cases],
                      'comparison_passed': True, 'missing_source_rejected': True,
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
