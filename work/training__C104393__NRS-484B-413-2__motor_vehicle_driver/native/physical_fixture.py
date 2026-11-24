"""CPU mock of the selected physical outcome and ownership contracts.

The source rows are synthetic. This tests the runtime predicate, never original
CARLA motion, physical acceptance, or legal compliance.
"""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def rows(path, values):
    path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in values))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[1]
    manifest = json.loads((folder / 'execution-manifest.json').read_text())
    entry = next(x for x in manifest['cases'] if x['case_id'] == args.case)
    construction = json.loads((folder / entry['construction']).read_text())
    cfg = json.loads(next(x['content'] for x in construction['files'] if x['path'] == 'config.json'))
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        with tempfile.TemporaryDirectory(prefix='c104393-physical-') as name:
            source = Path(name)
            write(source / 'config.json', cfg)
            frames = [10, 11, 12]
            times = [0.0, 0.05, 0.1]
            rows(source / 'video_frames.jsonl', [dict(carla_frame=f, time_s=t, video_frame=i) for i, (f, t) in enumerate(zip(frames, times))])
            rows(source / 'trace.jsonl', [dict(frame=f, time_s=t) for f, t in zip(frames, times)])
            if kind != 'missing_evidence':
                roads = [1, 2, 3 if kind == 'complete_motion' else 2]
                centers = [0.0, 2.0, 5.0]
                body = [dict(frame=f, time_s=t, road_id=road,
                             body_vertices_m=[[x-0.5, -0.5], [x+0.5, -0.5], [x+0.5, 0.5], [x-0.5, 0.5]])
                        for f, t, road, x in zip(frames, times, roads, centers)]
                rows(source / 'body_history.jsonl', body)
            assessment = assess_physical(source, cfg)
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met', 'missing_evidence': 'unverified'}[kind]
            actual = assessment['physical_checks']['maneuver']['status']
            if actual != expected:
                raise ValueError(f'{kind}: measured {actual}, expected {expected}')
            result = dict(assessment, format='c104393-physical-cpu-mock', case_id=args.case,
                          fixture_kind=kind, provenance_kind='synthetic_fixture', diagnostic_fixture=True,
                          original_native_observed=False, physical_acceptance_claimed=False,
                          legal_acceptance_claimed=False)
            write(output / (kind + '.json'), result)
            print(kind, actual, 'sources', assessment['physical_checks']['maneuver']['sources'])

    with tempfile.TemporaryDirectory(prefix='c104393-life-') as name:
        source = Path(name)
        write(source / 'construction.json', construction)
        (source / 'runner.py').write_text('synthetic CPU lifecycle fixture\n')
        revision = {'construction_sha256': sha(source / 'construction.json'), 'runner_sha256': sha(source / 'runner.py')}
        write(source / 'capture-seal.json', {'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
                                             'native_revision': revision, 'sources': {},
                                             'diagnostic_fixture': True})
        record_native_exit(source)
        receipt = source / 'owner-release.json'
        acknowledge_owner_release(source, receipt, True)
        _closure(source, receipt, 'native', False)
        events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']
        write(output / 'lifecycle.json', {'events': events, 'exit_code': 0, 'diagnostic_fixture': True,
                                          'original_native_observed': False,
                                          'capture_seal_sha256': sha(source / 'capture-seal.json'),
                                          'native_exit_sha256': sha(source / 'native-exit.json'),
                                          'owner_release_sha256': sha(receipt)})
        print('lifecycle', ','.join(events), 'runtime closure passed')


if __name__ == '__main__':
    main()
