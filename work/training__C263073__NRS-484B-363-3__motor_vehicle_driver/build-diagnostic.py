"""Build a source-hashed synthetic CPU fixture for school-zone package checks.

These artifacts exercise software joins only. They are not Native acquisition.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DONOR = REPO / 'work/training__C24758__LVMC-11-16-040__motor_vehicle_driver/diagnostic-source/reference'
GENERATOR = REPO / 'work/training__C24758__LVMC-11-16-040__motor_vehicle_driver/diagnostic-generator-reference.json'
sys.path.insert(0, str(ROOT / 'native'))
from prove_saved import fixture
from layout import open_drive


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, values):
    path.write_text(''.join(json.dumps(value, separators=(',', ':')) + '\n' for value in values))


def build(suffix):
    if suffix not in ('controlled_1', 'controlled_2'):
        raise ValueError('Select one original case')
    scratch = REPO / '.runtime-work/c263073-owner' / ('fixture-shape-' + suffix)
    if scratch.exists():
        shutil.rmtree(scratch)
    fixture(scratch, suffix == 'controlled_2')
    target = ROOT / 'diagnostic-source' / suffix
    target.mkdir(parents=True, exist_ok=True)
    source_names = ('acquisition-provenance.json', 'capture/evidence.jsonl',
                    'capture/manifest.json', 'capture/native/frames.jsonl',
                    'capture/recorder_info.txt', 'frame-map.json')
    for name in source_names:
        out = target / name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DONOR / name, out)
    own_names = ['school-context.json', 'native-motion.jsonl', 'video_frames.jsonl', 'trace.jsonl']
    own_names += ['review-sources/' + name + '.json' for name in (
        'zone_designation', 'zone_boundaries', 'school_adjacency', 'highway_status',
        'driver_identity', 'driver_control', 'vehicle_classification',
        'child_identity', 'child_location', 'school_session', 'school_operation',
        'class_hours', 'civil_time', 'beacon_configuration', 'beacon_lights',
        'zone_sign')]
    for name in own_names:
        (target / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(scratch / name, target / name)
    (target / 'road.xodr').write_text(open_drive().rstrip() + '\n')
    shutil.copyfile(target / 'road.xodr', target / 'native-map-readback.xodr')
    motions = rows(target / 'native-motion.jsonl')
    traces = rows(target / 'trace.jsonl')
    evidence = rows(target / 'capture/evidence.jsonl')
    frames = rows(target / 'capture/native/frames.jsonl')
    mapping = rows(target / 'frame-map.json') if False else json.loads((target / 'frame-map.json').read_text())
    if not (len(motions) == len(traces) == len(evidence) == len(frames) == len(mapping) == 600):
        raise ValueError('Diagnostic frame count differs')
    for i, motion in enumerate(motions):
        x, y = motion['ego']['center_xy_m']
        heading = motion['ego']['heading_deg']
        native = motion['native_frame']
        traces[i].update(frame=native, position={'x': x, 'y': y, 'z': 1},
                         position_m=[x, y, 1], heading_deg=heading,
                         speed_mps=0, speed_mph=0,
                         velocity_mps=[0, 0, 0], synthetic_diagnostic=True)
        traces[i]['control'] = {'throttle': motion['control']['throttle'],
                                'brake': motion['control']['brake'],
                                'steer': motion['control']['steer'],
                                'hand_brake': False}
        evidence[i].update(original_frame=native, replay_frame=native,
                           recording_time_s=i / 20, replay_simulation_time_s=i / 20)
        evidence[i]['ego'].update(position_m=[x, y, 1], heading_deg=heading,
                                  speed_mps=0, speed_provenance='synthetic_native_sample')
        frames[i].update(frame=native, time_s=i / 20, simulation_time=i / 20)
        mapping[i].update(native_frame=native, time_s=i / 20)
    write_rows(target / 'trace.jsonl', traces)
    write_rows(target / 'capture/evidence.jsonl', evidence)
    write_rows(target / 'capture/native/frames.jsonl', frames)
    (target / 'frame-map.json').write_text(json.dumps(mapping, separators=(',', ':')) + '\n')
    manifest = json.loads((target / 'capture/manifest.json').read_text())
    manifest.update(case_id=ROOT.name + '__' + suffix, frames=600,
                    sources={'road.xodr': sha(target / 'road.xodr'),
                             'trace.jsonl': sha(target / 'trace.jsonl')})
    (target / 'capture/manifest.json').write_text(json.dumps(manifest, separators=(',', ':')) + '\n')
    gen = json.loads(GENERATOR.read_text())
    generator_path = ROOT / ('diagnostic-generator-' + suffix + '.json')
    generator_path.write_text(json.dumps(gen, separators=(',', ':')) + '\n')
    inventoried = source_names + tuple(own_names) + ('road.xodr', 'native-map-readback.xodr')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': name, 'source': str((target / name).relative_to(REPO)),
                           'sha256': sha(target / name)} for name in inventoried],
              'generator': {'source': str(generator_path.relative_to(REPO)),
                            'sha256': sha(generator_path)}}
    recipe_path = ROOT / ('diagnostic-recipe-' + suffix + '.json')
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    print(suffix, 'sources', len(inventoried), 'max_bytes',
          max((target / name).stat().st_size for name in inventoried))


if __name__ == '__main__':
    for selected in ('controlled_1', 'controlled_2'):
        build(selected)
