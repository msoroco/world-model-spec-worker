"""Recorded-only boundary finalizer CPU diagnostic with explicit synthetic provenance."""
import json
from pathlib import Path
import tempfile

from prove_boundary_finalizer import packet, sha
from native.finalize_boundary import finalize


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE_SUFFIX = 'minutes_after_sunset_at'


def synthetic_packet(distance_ft=1000, civil_branch='sunset', civil_offset_min=30):
    raw = packet(distance_ft, civil_branch, civil_offset_min)
    context = json.loads(raw['visibility-context.json'])
    context['source_kind'] = 'synthetic_diagnostic'
    context['visibility_weather_source'] = {
        'native_weather_request': 'ClearNoon',
        'independent_conditions_reviewed': False,
        'synthetic_diagnostic': True}
    raw['visibility-context.json'] = json.dumps(context).encode()
    clock = json.loads(raw['civil-clock.json'])
    clock['source_kind'] = 'synthetic_diagnostic'
    raw['civil-clock.json'] = json.dumps(clock).encode()
    pixel = json.loads(raw['visibility-pixel-review.json'])
    pixel['source_kind'] = 'synthetic_diagnostic'
    pixel['context_sha256'] = sha(raw['visibility-context.json'])
    raw['visibility-pixel-review.json'] = json.dumps(pixel).encode()
    civil = json.loads(raw['civil-time-review.json'])
    civil['source_kind'] = 'synthetic_diagnostic'
    civil['clock_sha256'] = sha(raw['civil-clock.json'])
    raw['civil-time-review.json'] = json.dumps(civil).encode()
    return raw


def run_one(root, remove=None):
    construction = json.loads((HERE/'draft-boundary-cases'/CASE_SUFFIX/'primary'/
                               'construction.json').read_text())
    config = next(item['content'] for item in construction['files']
                  if item['path'] == 'config.json')
    (root/'config.json').write_text(config)
    for name, content in synthetic_packet().items():
        if name != remove:
            (root/name).write_bytes(content)
    return finalize(root, root/'analysis-report.json')


def main():
    scratch = ROOT/'.runtime-work/c179824'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix='boundary-saved-') as tmp:
        root = Path(tmp)
        analysis = run_one(root)
        from worker_exchange.native_output import validate_result
        result = validate_result(json.loads((root/'result.json').read_text()))
        if analysis['case_id'] != result['case_id'] or not result['diagnostic_fixture']:
            raise AssertionError('recorded-only diagnostic provenance changed')
        if result['accepted'] or result['legal_verdict_claimed']:
            raise AssertionError('diagnostic claimed acceptance')
        if set(name['name'] for name in result['recording_evidence']) != {
                channel['name'] for channel in
                result['recording_description']['channels'] +
                result['recording_description']['context_inputs']}:
            raise AssertionError('required boundary channels missing')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='boundary-negative-') as tmp:
        try:
            run_one(Path(tmp), remove='civil-time-review.json')
        except ValueError as error:
            if 'Missing required source: civil-time-review.json' not in str(error):
                raise
        else:
            raise AssertionError('missing independent civil review passed')
    print(json.dumps({'passed': True, 'recorded_only_diagnostic': True,
                      'positive': 1, 'negative': 1,
                      'original_capture_attested': False}, sort_keys=True))


if __name__ == '__main__':
    main()
