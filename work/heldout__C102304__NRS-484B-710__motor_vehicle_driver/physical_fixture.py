"""Test source-shaped complete, incomplete and missing motion packets.

The JSON result is a synthetic CPU test of a prospective Native source protocol.
It must never be used as an actual capture result or physical finding.
"""
import argparse
from hashlib import sha256
import importlib.util
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

folder = Path(__file__).resolve().parent
repo = folder.parents[1]
sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources


def sibling(name):
    spec = importlib.util.spec_from_file_location(name, folder / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(case_id, kind):
    entry = next((e for e in json.loads((folder / 'execution-manifest.json').read_text())['cases']
                  if e['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Unknown exact case')
    with TemporaryDirectory(prefix='fire-motion-', dir=repo / '.runtime-work') as temp:
        base = Path(temp)
        make_fixture(repo, repo / entry['fixture_recipe'], base / 'fixture')
        make_attempt(folder / 'execution-manifest.json', case_id, base / 'attempt')
        copy_sources(base / 'fixture', base / 'attempt')
        attempt = base / 'attempt'
        config = json.loads((attempt / 'config.json').read_text())
        state = attempt / 'participant_state.jsonl'
        if kind == 'incomplete_motion':
            rows = [json.loads(line) for line in state.read_text().splitlines()]
            field = {'traveling_follow': 'ego_following',
                     'stopped_drive_to': 'ego_moving',
                     'stopped_park': 'ego_parked'}[config['fire_branch']]
            for row in rows:
                row[field] = False
            state.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        elif kind == 'missing_evidence':
            state.unlink()
        elif kind != 'complete_motion':
            raise ValueError('Unknown physical fixture kind')
        names = ('video_frames.jsonl', 'trace.jsonl', 'participant_footprints.jsonl',
                 'participant_state.jsonl', 'fire_context.json')
        sources = {name: sha256((attempt / name).read_bytes()).hexdigest()
                   for name in names if (attempt / name).is_file()}
        measured = None
        if kind == 'missing_evidence':
            status = 'unverified'
        else:
            try:
                report = sibling('fire_finalizer').analyze(attempt, write_channel=False)
                measured = report['measurements']['fire_boundary_observation']['value']
                status = 'met'
            except ValueError as error:
                if kind != 'incomplete_motion' or 'no measured active frames' not in str(error):
                    raise
                status = 'not_met'
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Physical fixture status mismatch')
        return {
            'case_id': case_id, 'fixture_kind': kind, 'fixture_only': True,
            'diagnostic_fixture': True, 'actual_native_capture': False,
            'physical_checks': {'maneuver': {
                'status': status,
                'method': 'original-shaped synchronized fire footprints, state and branch activity; synthetic fixture',
                'sources': sources,
                'missing_evidence': ['participant_state.jsonl'] if kind == 'missing_evidence' else [],
            }},
            'maneuver_completed': status == 'met',
            'realized_observables': ({'boundary_distance_ft': measured['min_boundary_distance_ft'],
                                      'active_frame_count': measured['active_frame_count']}
                                     if measured else {}),
            'provenance_kind': 'native',
            'provenance_note': 'Native-shaped test protocol only; synthetic diagnostic fixture, not a Native acquisition',
            'physical_acceptance_claimed': False,
        }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True,
                        choices=('complete_motion', 'incomplete_motion', 'missing_evidence'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'],
          'synthetic_fixture_only')
