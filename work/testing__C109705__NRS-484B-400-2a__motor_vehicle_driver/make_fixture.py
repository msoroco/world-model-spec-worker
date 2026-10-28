"""Adapt the pinned retained three-frame acquisition as a software-only pilot fixture."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    source = REPO / 'work/_shared/fixtures/base-v3'
    target = ROOT / 'fixture-diagnostic'
    if target.exists():
        raise FileExistsError('Retain earlier fixture; use a fresh target')
    shutil.copytree(source, target)
    for name in ('config.json', 'case.json', 'result.json', 'analysis-report.json', 'compatibility.json'):
        if (target / name).exists():
            raise ValueError('Base fixture supplied prohibited package output: ' + name)
    trace = rows(target / 'trace.jsonl')
    evidence = rows(target / 'capture/evidence.jsonl')
    if len(trace) != len(evidence):
        raise ValueError('Original diagnostic trace/evidence counts differ')
    channel_root = target / 'channels'
    channel_root.mkdir(exist_ok=False)
    names = ('kin.position', 'kin.heading', 'kin.speed', 'road_geometry', 'turn_history')
    streams = {name: (channel_root / (name + '.jsonl')).open('x') for name in names}
    try:
        for point, event in zip(trace, evidence):
            if point['frame'] != event['original_frame']:
                raise ValueError('Retained original frame mismatch')
            position = point['position_m']
            values = {'kin.position': position, 'kin.heading': point['heading_deg'],
                'kin.speed': point['speed_mps'],
                'road_geometry': {'projection': event['world']['road_projection'],
                    'map_context': event['original_observations'].get('map_context'),
                    'native_topology_reference': None, 'junction_confirmed': False},
                'turn_history': {'position_m': position, 'heading_deg': point['heading_deg'],
                    'route_index': None, 'turn_completed': False}}
            for name, stream in streams.items():
                stream.write(json.dumps({'time_s': point['time_s'], 'value': values[name]}) + '\n')
    finally:
        for stream in streams.values():
            stream.close()
    provenance = json.loads((target / 'fixture-provenance.json').read_text())
    provenance['pilot_adaptations'] = [
        'Three retained original frames from the pinned runtime; this is not a 400(2)(a) maneuver.',
        'Pre-acquired diagnostic channels are derived from retained trace/evidence before analysis.',
        'Road/junction and turn fields explicitly remain unconfirmed; no physical or legal success is inferred.']
    (target / 'fixture-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')


if __name__ == '__main__':
    main()
