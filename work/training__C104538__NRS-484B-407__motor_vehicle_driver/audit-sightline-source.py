"""Independent authored-source and controlled 500 ft comparison audit."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FT_M=.3048
RADIUS=500.0
LIMITS={'below_500_ft':450,'at_500_ft':500,'above_500_ft':550}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    law=json.loads((ROOT/'inputs/training__C104538__NRS-484B-407__motor_vehicle_driver/assignment.json').read_text())
    assert law['law_record']['text'].endswith('within 500 feet.')
    assert law['cell']['layout']=='hill_crest' and law['cell']['maneuver']=='u_turn'
    folder=HERE/'draft-sightline'
    summary=json.loads((folder/'summary.json').read_text())
    assert summary['positive_count']==3 and summary['negative_count']==6
    assert {row['case_suffix'] for row in summary['cases']}==set(LIMITS)
    road_hashes=set();classifications={}
    for row in summary['cases']:
        suffix=row['case_suffix'];base=folder/suffix
        road=base/'road.xodr';obstruction=base/'obstruction.json'
        measured=json.loads((base/'measurement.json').read_text())
        setup=json.loads(obstruction.read_text())
        assert row['road_sha256']==sha(road)==setup['road_xodr_sha256']
        assert row['obstruction_sha256']==sha(obstruction)
        assert row['measurement_sha256']==sha(base/'measurement.json')
        road_hashes.add(sha(road))
        assert setup['case_suffix']==suffix and setup['requested_reference_limit_ft']==LIMITS[suffix]
        expected=RADIUS*math.cos(LIMITS[suffix]*FT_M/(2*RADIUS))
        assert math.isclose(setup['inner_radius_m'],expected,abs_tol=1e-10)
        assert math.isclose(measured['authored_reference_limit_ft'],LIMITS[suffix],abs_tol=1e-8)
        assert measured['source_hashes']=={'road.xodr':sha(road),'obstruction.json':sha(obstruction)}
        rays=measured['rays_at_500_ft']
        assert {r['direction'] for r in rays}=={'increasing_station','decreasing_station'}
        expected_clearance=RADIUS*math.cos(500*FT_M/(2*RADIUS))-expected
        for ray in rays:
            assert ray['observer_distance_ft']==500
            assert math.isclose(ray['signed_radial_clearance_m'],expected_clearance,abs_tol=1e-10)
            assert ray['reference_ray_blocked']==(expected_clearance < -1e-8)
            assert ray['actual_vehicle_visibility_proven'] is False
        assert measured['native_loaded'] is False and measured['legal_verdict_claimed'] is False
        assert row['missing_obstruction_rejected'] and row['wrong_road_hash_rejected']
        classifications[suffix]=rays[0]['reference_ray_blocked']
    assert len(road_hashes)==1
    assert classifications=={'below_500_ft':True,'at_500_ft':False,'above_500_ft':False}
    return {'passed':True,'case_count':3,'negative_count':6,
            'fixed':'frozen cell/law/actor, authored road, turn station, crest, curve, 500 ft probe',
            'deliberate_difference':'inner obstruction radius setting 450/500/550 ft reference limit',
            '500_ft_reference_ray_blocked':classifications,
            'native_loaded':False,'physical_visibility_measured':False,
            'legal_verdict_claimed':False}


if __name__=='__main__':print(json.dumps(audit(),indent=2))
