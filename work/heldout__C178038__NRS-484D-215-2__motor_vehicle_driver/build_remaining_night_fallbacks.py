"""Create exact route, speed, and camera alternatives for remaining night cases."""

from hashlib import sha256
import json
from pathlib import Path

from build_night_fallbacks import change_file


HERE = Path(__file__).resolve().parent


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def build():
    manifest = json.loads((HERE / 'night-execution-manifest.json').read_text())
    first = json.loads((HERE / 'night-fallback-manifest.json').read_text())['cases'][0]
    manifest['cases'][0] = first
    variants = [
        ('fallback1', 'native_headlamp_probe.py',
         "select_follow_route(world.get_map(), target_gap_ft=config['requested_gap_ft'])",
         "select_follow_route(world.get_map(), target_gap_ft=config['requested_gap_ft'], step_m=1.25)",
         'Native waypoint route-selection diagnostic', 'eligible connected same-lane route count',
         'Primary 2.5 m sampling finds no eligible route at the exact requested gap',
         'route waypoint sampling 2.5 m to 1.25 m'),
        ('fallback2', 'native_headlamp_probe.py',
         'def _command(actor, target, speed=6):',
         'def _command(actor, target, speed=5):',
         'retained original actor velocity and full-body gap samples',
         '20 Hz body-gap tracking error around requested target',
         'Primary 6 m/s command misses the stated ±2 ft engineering attainment screen',
         'target cruise speed 6 m/s to 5 m/s'),
        ('fallback3', 'headlamp_camera.py',
         '"overview": ((-32, 0, 10), (-4, 0, 0), (1920, 1080), 95)',
         '"overview": ((-36, 0, 12), (-4, 0, 0), (1920, 1080), 95)',
         'original overview source-pixel review',
         'complete subject and lead body visibility on all reviewed frames',
         'Primary overview source omits either required full body in any frame',
         'overview mount (-32,0,10) m to (-36,0,12) m'),
    ]
    for entry in manifest['cases'][1:]:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        primary = json.loads((HERE / entry['construction']).read_text())
        candidates = []
        for ident, filename, old, new, trigger_source, metric, failure, knob in variants:
            construction = json.loads(json.dumps(primary))
            change_file(construction, filename, old, new)
            relative = f'night-probes/{suffix}-{ident}-construction.json'
            path = HERE / relative
            path.write_text(json.dumps(construction, indent=2) + '\n')
            candidates.append({'id': ident, 'construction': relative,
                               'construction_sha256': sha(path),
                               'trigger': {'source': trigger_source,
                                           'metric': metric,
                                           'failure_condition': failure},
                               'changed_knobs': [knob]})
        entry['candidates'] = candidates
    (HERE / 'night-all-fallback-manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    build()
