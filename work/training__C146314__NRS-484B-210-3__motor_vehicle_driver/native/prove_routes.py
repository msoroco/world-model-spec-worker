"""Independent CPU checks of the authored right-pass corridor and route separation."""
import hashlib
import json
from pathlib import Path

import geometry
import necessity
import runner


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    geometry_result = geometry.check()
    necessity_result = necessity.check()
    runner_result = runner.check()
    assert runner_result['geometry'] == geometry_result
    assert runner_result['necessity'] == necessity_result
    assert runner_result['frames'] == 600
    assert runner_result['camera_names'] == ['overview', 'approach', 'reference_corner', 'driver_reference']
    assert runner.ROUTES == {'probe_a': (-2.0, -6.0), 'probe_b': (-6.0, -8.7)}
    assert geometry.PAVED_RIGHT_EDGE_Y_M == -8.0
    assert necessity.paved_right_pass_feasible(-2.0)['feasible']
    assert not necessity.paved_right_pass_feasible(-6.0)['feasible']
    assert necessity.paved_right_pass_feasible(-6.0, ego_width_m=.5)['feasible']
    for bad_width in (0, -1):
        try:
            necessity.paved_right_pass_feasible(-6.0, ego_width_m=bad_width)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid body width accepted')
    base = Path(__file__).resolve().parent
    proof = {'format': 'c146314-right-pass-route-geometry-cpu-proof-v1',
             'selected_cases': [runner.ASSIGNMENT + '__' + suffix for suffix in runner.ROUTES],
             'source_hashes': {name: sha(base / name) for name in ('geometry.py', 'necessity.py', 'runner.py')},
             'paved_case': necessity_result['paved_case'],
             'shoulder_case': necessity_result['shoulder_case'],
             'camera_names': runner_result['camera_names'],
             'frame_count': runner_result['frames'],
             'physical_native_verified': False,
             'shoulder_surface_material_verified': False,
             'legal_verdict': None}
    path = base / 'route-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    return {'proof_sha256': sha(path), 'routes': len(runner.ROUTES), 'passed': True}


if __name__ == '__main__':
    print(json.dumps(run()))
