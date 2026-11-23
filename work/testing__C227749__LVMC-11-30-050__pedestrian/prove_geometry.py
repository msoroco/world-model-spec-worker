"""CPU proof of authored route geometry only; no Native or legal conclusion."""
import json
from pathlib import Path
from crossing_geometry import validate_scene

ROOT = Path(__file__).resolve().parent
EXPECTED = {
    'outside_right_angle': {'right_angle': True, 'shortest': True, 'crosswalk': 'outside'},
    'outside_shortest_endpoint': {'right_angle': False, 'shortest': True, 'crosswalk': 'outside'},
    'outside_neither': {'right_angle': False, 'shortest': False, 'crosswalk': 'outside'},
    'outside_endpoint_detour': {'right_angle': False, 'shortest': False, 'crosswalk': 'outside'},
    'inside_crosswalk_oblique': {'right_angle': False, 'shortest': False, 'crosswalk': 'inside'},
}


def prove():
    findings = {}
    for name, expected in EXPECTED.items():
        scene = json.loads((ROOT/'cases'/name/'scene.json').read_text())
        result = validate_scene(scene)
        # Engineering geometry target checks, not a legal tolerance or classification.
        right_angle = abs(result['angle_to_starting_curb_deg']-90) < 1e-8
        shortest = abs(result['route_excess_over_geometric_minimum_m']) < 1e-8
        observed = {'right_angle': right_angle, 'shortest': shortest,
                    'crosswalk': scene['crosswalk_context']}
        if observed != expected:
            raise ValueError(f'{name}: geometry target mismatch: {observed} != {expected}')
        findings[name] = {'case_id': scene['case_id'], 'authored_target': observed,
                          'measurement': result, 'physical_realization': 'unconfirmed'}
    return findings


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
