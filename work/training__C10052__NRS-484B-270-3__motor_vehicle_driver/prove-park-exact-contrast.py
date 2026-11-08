"""Run exact synthetic v1 packages on one stopped pose with and without held control."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
spec = importlib.util.spec_from_file_location('core_fixture', HERE / 'probe-core-synthetic.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from worker_exchange.package_compatibility import run

CASE = 'training__C10052__NRS-484B-270-3__motor_vehicle_driver__probe_b'
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def source_variant(root, name, held):
    source = root / name
    fixture.make_attempt(source, 'probe_b', full_resolution=True)
    poses = fixture.rows(source / 'native_samples.jsonl')
    traces = fixture.rows(source / 'trace.jsonl')
    controls = []
    for i, (pose, trace) in enumerate(zip(poses, traces)):
        hand_brake = held and 160 <= i < 440
        control = {'native_frame': pose['native_frame'], 'time_s': pose['time_s'],
                   'throttle': 0.0, 'brake': 0.5 if 132 <= i < 479 else 0.0,
                   'hand_brake': hand_brake, 'control_source': 'synthetic_fixture',
                   'synthetic_diagnostic': True}
        controls.append(control)
        trace['control'] = {key: control[key] for key in ('throttle', 'brake', 'hand_brake')}
    fixture.write_rows(source / 'native_controls.jsonl', controls)
    fixture.write_rows(source / 'trace.jsonl', traces)
    capture = json.loads((source / 'capture/manifest.json').read_text())
    capture['sources']['trace.jsonl'] = sha(source / 'trace.jsonl')
    write_json(source / 'capture/manifest.json', capture)
    names = ('native_samples.jsonl', 'native_controls.jsonl', 'road_geometry.json')
    write_json(source / 'park-act-sources.json', {
        'format': 'c10052-park-act-sources-v1',
        'source_kind': 'synthetic_cpu_fixture',
        'sha256': {item: sha(source / item) for item in names}})
    (source / 'config.json').unlink()
    return source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', choices=NAMES, required=True)
    parser.add_argument('--scratch', type=Path)
    args = parser.parse_args()
    scratch = args.scratch or Path(tempfile.mkdtemp(
        dir=ROOT / '.runtime-work', prefix='c10052-park-contrast-'))
    scratch = scratch.resolve()
    print('scratch', scratch, flush=True)
    held = scratch / 'held-source'
    if not held.is_dir():
        held = source_variant(scratch, 'held-source', True)
    released = scratch / 'released-source'
    if not released.is_dir():
        shutil.copytree(held, released)
        controls = fixture.rows(released / 'native_controls.jsonl')
        traces = fixture.rows(released / 'trace.jsonl')
        for control, trace in zip(controls, traces):
            control['hand_brake'] = False
            trace['control']['hand_brake'] = False
        fixture.write_rows(released / 'native_controls.jsonl', controls)
        fixture.write_rows(released / 'trace.jsonl', traces)
        capture = json.loads((released / 'capture/manifest.json').read_text())
        capture['sources']['trace.jsonl'] = sha(released / 'trace.jsonl')
        write_json(released / 'capture/manifest.json', capture)
        manifest = json.loads((released / 'park-act-sources.json').read_text())
        manifest['sha256']['native_controls.jsonl'] = sha(released / 'native_controls.jsonl')
        write_json(released / 'park-act-sources.json', manifest)
    same = ('native_samples.jsonl', 'road_geometry.json', 'entry-sources.json',
            'exception_context.json', 'context.json', 'video_frames.jsonl',
            'overview.mkv', 'approach.mkv', 'facility.mkv', 'driver_reference.mkv')
    assert all(sha(held / name) == sha(released / name) for name in same)
    package = HERE / 'draft-execution-manifest.json'
    decoder = ROOT / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck'
    reports = []
    for label, source in (('held', held), ('released', released)):
        output = scratch / ((label if args.candidate == 'primary' else args.candidate + '-' + label) + '-output')
        if (output / 'compatibility.json').is_file():
            receipt = json.loads((output / 'compatibility.json').read_text())
        else:
            receipt = run(package, CASE, source, output,
                          ROOT / 'runtime/pipeline/library', decoder, args.candidate)
        analysis = json.loads((output / 'analysis-report.json').read_text())
        value = analysis['measurements']['parking_control_observation']['value']
        assert receipt['passed'] is True
        assert analysis['measurements']['parking_control_observation']['sources']['native_controls.jsonl'] == sha(source / 'native_controls.jsonl')
        assert value['park_control_candidate'] is (label == 'held')
        assert value['held_duration_s'] == (14.0 if label == 'held' else 0)
        assert value['max_held_facility_overlap_m2'] == (9.36 if label == 'held' else 0)
        assert value['legal_park_verdict_claimed'] is False
        assert json.loads((output / 'result.json').read_text())['accepted'] is False
        reports.append({'variant': label, 'source_root': source.relative_to(ROOT).as_posix(),
                        'output_root': output.relative_to(ROOT).as_posix(),
                        'receipt_sha256': sha(output / 'compatibility.json'),
                        'park_source_sha256': sha(source / 'park-act-sources.json'),
                        'measurement': value})
    return {'format': 'c10052-park-exact-control-contrast-v1', 'passed': True,
            'candidate': args.candidate, 'case_id': CASE,
            'construction_manifest_sha256': sha(package), 'held_source_files_equal': list(same),
            'source_difference': ['native_controls.jsonl', 'trace.jsonl',
                                  'capture/manifest.json', 'park-act-sources.json'],
            'reports': reports, 'selected': False, 'accepted': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
