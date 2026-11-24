"""Bind four exact C109705 400(2)(b) cases to current CPU constructions.

This partial manifest records passing offline proofs and leaves unproved
compatibility, saved delivery and audit fields absent until those tests pass.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NAMES = ('near_centerline', 'farther_from_centerline',
         'imaginary_near_centerline', 'imaginary_farther_from_centerline')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    draft = json.loads((ROOT / 'execution-manifest.draft.json').read_text())
    by_case = {row['case_id']: row for row in draft['cases']}
    cases = []
    for name in NAMES:
        case = ROOT.name + '__' + name
        row = by_case[case]
        source = ROOT / row['construction']
        if sha(source) != row['construction_sha256']:
            raise ValueError('selected construction changed after exact offline proof')
        compat_log = ROOT / f'cpu-compat-offline-{name}.log'
        semantic_log = ROOT / f'cpu-semantic-offline-{name}.log'
        selected_log = ROOT / f'cpu-selected-offline-{name}.log'
        log_name = (compat_log.name if compat_log.is_file() else
                    semantic_log.name if semantic_log.is_file() else
                    selected_log.name if selected_log.is_file() else
                    f'cpu-source-review-review-offline-{name}.log')
        log = ROOT / log_name
        if not log.is_file():
            raise ValueError('current exact offline proof log missing')
        entry = {
            'case_id': case, 'kind': 'delivery',
            'construction': row['construction'],
            'construction_sha256': row['construction_sha256'],
            'candidate_risk': row['candidate_risk'], 'candidates': [],
            'preparation_status': 'offline_only_partial',
            'offline': {
                'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/execution-manifest.json --case {case} --output .runtime-work/c109705-2b-nov24/semantic-offline-{name} --python $PWD/.venv-cpu/bin/python',
                'exit_code': 0,
                'construction_sha256': row['construction_sha256'],
                'log': log_name, 'log_sha256': sha(log),
            },
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
            'measurement_contract': f'cases/{name}/measurement-contract.json',
            'fixture_recipe': f'work/{ROOT.name}/cases/{name}/fixture-recipe.json',
            'measurement_procedure': {'entrypoint': 'analysis.py'},
            'acquisition': {
                'full_body_departure_xy': {'entrypoint': 'native_capture.py',
                                           'method': 'capture',
                                           'evidence': 'sealed original trace full-body corners'},
                'centerline_and_right_half': {'entrypoint': 'native_seal.py',
                                              'method': 'seal',
                                              'evidence': 'reviewed destination centerline and highway status'},
                'departure_heading': {'entrypoint': 'native_capture.py',
                                      'method': 'capture',
                                      'evidence': 'original heading and road readback'},
                'camera_sources': {'entrypoint': 'native_camera_source.py',
                                   'method': 'camera_frame',
                                   'evidence': 'four source-hashed original camera PNG streams'},
            },
        }
        proof_dir = ROOT / 'cases' / name
        receipt = proof_dir / 'compatibility.json'
        positive = proof_dir / 'analysis-proof.log'
        negative = proof_dir / 'negative-analysis.log'
        if receipt.is_file() and positive.is_file() and negative.is_file():
            proof = json.loads(receipt.read_text())
            if (proof.get('passed') is True and proof.get('case_id') == case and
                    proof.get('construction_sha256') == row['construction_sha256'] and
                    proof.get('log_sha256') == sha(positive) and
                    proof.get('negative_log_sha256') == sha(negative)):
                entry['compatibility'] = {
                    'command': f'.venv-cpu/bin/python runtime.py compatibility --manifest work/{ROOT.name}/execution-manifest.json --case {case} --output .runtime-work/c109705-2b-nov24/compat3-{name} --library runtime/library --validator .runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck',
                    'receipt': f'cases/{name}/compatibility.json',
                    'sha256': sha(receipt),
                    'log': f'cases/{name}/analysis-proof.log',
                }
                contract = json.loads((proof_dir / 'measurement-contract.json').read_text())
                entry['negative'] = {
                    'log': f'cases/{name}/negative-analysis.log',
                    'exit_code': 1,
                    'error_contains': contract['negative']['error_contains'],
                    'removed': contract['negative']['remove'][0],
                }
        physical = proof_dir / 'physical/receipt.json'
        if physical.is_file():
            proof = json.loads(physical.read_text())
            if proof.get('construction_sha256') == row['construction_sha256']:
                entry['physical_preparation'] = {
                    'receipt': f'cases/{name}/physical/receipt.json',
                    'sha256': sha(physical),
                }
        fallback_source = proof_dir / 'fallback1-construction.json'
        if fallback_source.is_file():
            fallback = {
                'id': 'fallback1',
                'construction': f'cases/{name}/fallback1-construction.json',
                'construction_sha256': sha(fallback_source),
                'trigger': {
                    'source': 'original Native trace and physical_checks.maneuver',
                    'metric': 'ordered left-turn route and full-body clearance',
                    'failure_condition': 'maneuver not_met after primary controller or route overshoot',
                },
                'changed_knobs': ['waypoint controller target speed 7.0 to 5.0 m/s'],
            }
            fallback_log = ROOT / f'cpu-fallback-offline-{name}.log'
            if fallback_log.is_file():
                fallback['offline'] = {
                    'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/execution-manifest.json --case {case} --candidate fallback1 --output .runtime-work/c109705-2b-nov24/fallback-offline-{name} --python $PWD/.venv-cpu/bin/python',
                    'exit_code': 0,
                    'construction_sha256': sha(fallback_source),
                    'log': fallback_log.name,
                    'log_sha256': sha(fallback_log),
                }
            fallback_dir = proof_dir / 'fallback1'
            receipt = fallback_dir / 'compatibility.json'
            positive = fallback_dir / 'analysis-proof.log'
            negative = fallback_dir / 'negative-analysis.log'
            if all(path.is_file() for path in (receipt, positive, negative)):
                proof = json.loads(receipt.read_text())
                if (proof.get('passed') is True and proof.get('candidate_id') == 'fallback1' and
                        proof.get('construction_sha256') == sha(fallback_source) and
                        proof.get('log_sha256') == sha(positive) and
                        proof.get('negative_log_sha256') == sha(negative)):
                    fallback['compatibility'] = {
                        'command': f'.venv-cpu/bin/python runtime.py compatibility --manifest work/{ROOT.name}/execution-manifest.json --case {case} --candidate fallback1 --output .runtime-work/c109705-2b-nov24/fallback-compat-{name} --library runtime/library --validator .runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck',
                        'receipt': f'cases/{name}/fallback1/compatibility.json',
                        'sha256': sha(receipt),
                        'log': f'cases/{name}/fallback1/analysis-proof.log',
                        'negative_log': f'cases/{name}/fallback1/negative-analysis.log',
                    }
            entry['candidates'] = [fallback]
            entry['candidate_risk'] = {
                'status': 'physical',
                'reason': 'A surveyed Native route may overshoot or lack sampled full-body departure; retain a slower controller for the same exact case.',
            }
        cases.append(entry)
    manifest = {
        'format': 'worker-execution-manifest',
        'assignment_id': ROOT.name,
        'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
        'preparation_status': 'offline_only_partial',
        'cases': cases,
    }
    (ROOT / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('bound', len(cases), 'selected partial cases')


if __name__ == '__main__':
    build()
