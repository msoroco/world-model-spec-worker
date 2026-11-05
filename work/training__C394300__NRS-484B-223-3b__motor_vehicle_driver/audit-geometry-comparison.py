"""Independent CPU audit of five authored center-lane route proposals."""
import importlib.util
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('center_geometry',FOLDER/'native/geometry.py')
geometry=importlib.util.module_from_spec(spec);spec.loader.exec_module(geometry)


def run():
    cases=geometry.TARGET_FEET
    routes={name:geometry.route(name) for name in cases}
    assert len(routes)==5
    reference=routes['witness_1']
    for case,points in routes.items():
        assert len(points)==len(reference)==1601
        assert [p[0] for p in points]==[p[0] for p in reference]
        assert all(a==b for a,b in zip(points[850:],reference[850:])),case
        assert all(p[1]==-3.5 for p in points[:75]),case
    x68={case:points[270][1] for case,points in routes.items()}
    assert len(set(x68.values()))==5
    stations={case:round(geometry.TURN_START_X-feet*.3048,5) for case,feet in cases.items()}
    assert len(set(stations.values()))==5
    parsed=geometry.check()
    assert parsed['passed'] and parsed['native_center_lane_design_verified'] is False
    return {'format':'c394300-3b-authored-route-comparison-v1','passed':True,
      'same_map':True,'cases':list(cases),
      'fixed':'actor, law, map, initial 7.5 m, longitudinal route stations, turn connector and destination',
      'deliberate_difference':'nominal lane-change station before the same left turn',
      'nominal_entry_station_x_m':stations,'lateral_at_x_minus_68_m':x68,
      'native_lane_design_verified':False,
      'scope':'authored CPU geometry only; commanded feet are not measured entry-to-turn distances'}


if __name__=='__main__':print(json.dumps(run(),indent=2))
