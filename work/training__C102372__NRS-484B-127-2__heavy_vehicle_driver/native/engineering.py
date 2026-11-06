"""Exact unselected truck-following plans; every fallback preserves the law and cell."""
from __future__ import annotations

CASES=('probe_1','probe_2')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
TARGET_GAP_M={'probe_1':165.,'probe_2':140.}
BASE={'ego_target_speed_mps':8.,'lead_target_speed_mps':8.,
      'gap_controller_gain_per_s':.35,'overview_fov_deg':90.,
      'overview_height_m':7.,'rate_hz':20,'duration_s':24}
CHANGES={
    'primary':{},
    'fallback1':{'ego_target_speed_mps':7.5},
    'fallback2':{'lead_target_speed_mps':8.5,'gap_controller_gain_per_s':.5},
    'fallback3':{'overview_fov_deg':110.,'overview_height_m':10.},
}
TRIGGERS={
    'fallback1':{'metric':'min_surface_gap_m','op':'<','threshold':152.4,
        'source':'original full-body truck footprints, Native road elevation and 480-frame source hashes'},
    'fallback2':{'metric':'max_gap_shortfall_m','op':'>','threshold':2.,
        'source':'original full-body truck footprints and target gap over joined Native frames'},
    'fallback3':{'metric':'min_projected_truck_frame_margin_px','op':'<','threshold':40.,
        'source':'original truck 3D bodies, surveyed overview camera calibration and decoded video frame join'},
}


def parameters(case:str,candidate:str)->dict:
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown C102372 case or candidate')
    return {'case':case,'candidate':candidate,'target_gap_m':TARGET_GAP_M[case],
            'knobs':BASE|CHANGES[candidate],'fallback_trigger':TRIGGERS.get(candidate),
            'law_id':'NRS-484B-127-2','cell_id':'C102372','actor':'heavy_vehicle_driver',
            'comparison_variable':'following_surface_gap_ft',
            'status':'unselected_native_plan','legal_verdict_claimed':False}


def speed_requests(plan:dict,observed_gap_m:float)->tuple[float,float]:
    """Follow at measured gap; distinct fallbacks change speed and correction."""
    knobs=plan['knobs']
    correction=knobs['gap_controller_gain_per_s']*(observed_gap_m-plan['target_gap_m'])
    ego=max(0.,min(knobs['ego_target_speed_mps'],knobs['ego_target_speed_mps']+correction))
    lead=knobs['lead_target_speed_mps']
    return round(ego,5),round(lead,5)
