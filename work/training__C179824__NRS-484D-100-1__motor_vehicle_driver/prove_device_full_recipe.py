"""Materialize full-device synthetic source recipe and run pinned attempt validation."""
import json
from pathlib import Path
import tempfile

from native.finalize_full_lamp import finalize
from worker_exchange.fixture_recipe import materialize
from worker_exchange.media import audit
from worker_exchange.native_output import validate_result
from worker_exchange.common import sha


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def one(suffix):
    scratch = ROOT/'.runtime-work/c179824'
    recipe = HERE/'cases'/('full_'+suffix)/'recipe.json'
    construction = json.loads((HERE/'draft-device-full'/suffix/'primary'/
                               'construction.json').read_text())
    config = next(item['content'] for item in construction['files']
                  if item['path'] == 'config.json')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='device-full-recipe-') as tmp:
        fixture = Path(tmp)/'fixture'
        source = materialize(ROOT, recipe, fixture)
        (fixture/'config.json').write_text(config)
        analysis = finalize(fixture, fixture/'analysis-report.json')
        result = validate_result(json.loads((fixture/'result.json').read_text()))
        if analysis['case_id'] != result['case_id'] or not result['diagnostic_fixture']:
            raise AssertionError('full-device diagnostic provenance changed')
        mapping = fixture/result['video_frame_map_reference']
        source_audits = {ref: audit(fixture/ref, 600, mapping_sha256=sha(mapping),
                                    receipt=fixture/('source-%d.json'%index))
                         for index, ref in enumerate(result['video_references'])}
        from batch_pipeline.carla import validate_attempt
        case = next(item for item in json.loads(
            (HERE/'proposals/cases.json').read_text())['cases']
                    if item['case_id'] == result['case_id'])
        request = {'case': case, 'cell': {'cell_id': 'C179824'},
                   'actor': 'motor_vehicle_driver'}
        validate_attempt(fixture, request, construction,
                         {'recorded_exit_code': 0}, {}, source_audits=source_audits)
    return {'case_id': analysis['case_id'], 'fixture_sha256': source['fixture_sha256'],
            'diagnostic_video_count': len(source_audits),
            'pinned_native_attempt_validation': True,
            'original_capture_attested': False}


def main():
    (ROOT/'.runtime-work/c179824').mkdir(parents=True, exist_ok=True)
    print(json.dumps({'passed': True, 'cases': [one(suffix) for suffix in
                                               ('controlled_1', 'controlled_2')]},
                     sort_keys=True))


if __name__ == '__main__':
    main()
