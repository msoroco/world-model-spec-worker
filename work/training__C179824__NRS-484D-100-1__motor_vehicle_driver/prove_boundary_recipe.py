"""Materialize a hash-bound public diagnostic and finalize saved sources."""
import json
from pathlib import Path
import tempfile

from native.finalize_boundary import finalize
from worker_exchange.fixture_recipe import materialize
from worker_exchange.media import audit
from worker_exchange.native_output import validate_result
from worker_exchange.common import sha


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIX = 'minutes_after_sunset_at'


def main():
    scratch = ROOT/'.runtime-work/c179824'
    scratch.mkdir(parents=True, exist_ok=True)
    recipe = HERE/'cases'/SUFFIX/'recipe.json'
    construction = json.loads((HERE/'draft-boundary-cases'/SUFFIX/'primary'/
                               'construction.json').read_text())
    config = next(item['content'] for item in construction['files']
                  if item['path'] == 'config.json')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='boundary-recipe-') as tmp:
        fixture = Path(tmp)/'fixture'
        source = materialize(ROOT, recipe, fixture)
        (fixture/'config.json').write_text(config)
        analysis = finalize(fixture, fixture/'analysis-report.json')
        result = validate_result(json.loads((fixture/'result.json').read_text()))
        if analysis['case_id'] != result['case_id'] or not result['diagnostic_fixture']:
            raise AssertionError('diagnostic provenance or case changed')
        mapping = fixture/result['video_frame_map_reference']
        if len(mapping.read_text().splitlines()) != 600:
            raise AssertionError('diagnostic frame map changed')
        audits = {name: audit(fixture/(name+'.mkv'), 600)
                  for name in ('overview', 'approach', 'reference_corner',
                               'driver_reference')}
        if any(item['frames'] != 600 for item in audits.values()):
            raise AssertionError('diagnostic video count changed')
        source_audits = {ref: audit(fixture/ref, 600, mapping_sha256=sha(mapping),
                                    receipt=fixture/('source-%d.json'%index))
                         for index, ref in enumerate(result['video_references'])}
        from batch_pipeline.carla import validate_attempt
        case = next(item for item in json.loads(
            (HERE/'proposals/boundary-cases-draft.json').read_text())['cases']
                    if item['case_id'] == result['case_id'])
        request = {'case': case, 'cell': {'cell_id': 'C179824'},
                   'actor': 'motor_vehicle_driver'}
        validate_attempt(fixture, request, construction,
                         {'recorded_exit_code': 0}, {}, source_audits=source_audits)
    print(json.dumps({'passed': True, 'case_id': analysis['case_id'],
                      'fixture_sha256': source['fixture_sha256'],
                      'diagnostic_video_count': len(audits),
                      'pinned_native_attempt_validation': True,
                      'recorded_only_finalizer': True,
                      'original_capture_attested': False}, sort_keys=True))


if __name__ == '__main__':
    main()
