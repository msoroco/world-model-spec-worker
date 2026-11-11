"""Bind exact physical-risk alternatives for daylight and shoulder cases."""

from hashlib import sha256
import json
from pathlib import Path

from build_night_fallbacks import change_file


HERE = Path(__file__).resolve().parent


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def build():
    manifest = json.loads((HERE / 'context-execution-manifest.json').read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        primary = json.loads((HERE / entry['construction']).read_text())
        route_call = ("select_follow_route(world.get_map(), target_gap_ft=config['requested_gap_ft'], surface='shoulder')"
                      if suffix.startswith('shoulder_') else
                      "select_follow_route(world.get_map(), target_gap_ft=config['requested_gap_ft'])")
        route_change = route_call[:-1] + ', step_m=1.25)'
        variants = [
            ('fallback1', 'native_headlamp_probe.py', route_call, route_change,
             'Native connected route selector on exact requested roadway surface',
             'eligible connected route count',
             'Primary 2.5 m waypoint sampling finds no eligible exact-case route',
             'waypoint sampling 2.5 m to 1.25 m on the same selected surface'),
            ('fallback2', 'native_headlamp_probe.py',
             'def _command(actor, target, speed=6):',
             'def _command(actor, target, speed=5):',
             'retained original subject and lead velocity and full-body gap samples',
             '20 Hz measured body-gap tracking error',
             'Primary 6 m/s command misses the ±2 ft engineering attainment screen',
             'target cruise speed 6 m/s to 5 m/s'),
            ('fallback3', 'headlamp_camera.py',
             '"overview": ((-32, 0, 10), (-4, 0, 0), (1920, 1080), 95)',
             '"overview": ((-36, 0, 12), (-4, 0, 0), (1920, 1080), 95)',
             'original overview source-pixel review',
             'full subject and lead body visibility on every original frame',
             'Primary overview source omits either required body in any frame',
             'overview mount (-32,0,10) m to (-36,0,12) m'),
        ]
        candidates = []
        for ident, filename, old, new, trigger_source, metric, failure, knob in variants:
            construction = json.loads(json.dumps(primary))
            change_file(construction, filename, old, new)
            relative = f'context-probes/{suffix}-{ident}-construction.json'
            path = HERE / relative
            path.write_text(json.dumps(construction, indent=2) + '\n')
            candidates.append({'id': ident, 'construction': relative,
                               'construction_sha256': sha(path),
                               'trigger': {'source': trigger_source,
                                           'metric': metric,
                                           'failure_condition': failure},
                               'changed_knobs': [knob]})
        entry['candidates'] = candidates
    (HERE / 'context-fallback-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    build()
