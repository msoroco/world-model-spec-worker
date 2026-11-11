"""Risk-triggered Native engineering alternatives for one Walk comparison."""
from __future__ import annotations

CASES=('reference','contrast')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
BASE={'route_tracking_lookahead_m':4.0,'crosswalk_hold_margin_m':1.0,
      'overview_fov_deg':90.0,'rate_hz':20,'duration_s':24.0,
      'camera_profile':['overview','approach','reference_corner','driver_reference']}
CHANGES={
    'fallback1':{'route_tracking_lookahead_m':5.5},
    'fallback2':{'crosswalk_hold_margin_m':1.8},
    'fallback3':{'overview_fov_deg':105.0},
}
TRIGGERS={
    'fallback1':{'source':'native_samples.jsonl','metric':'observed_bus_cross_track_error_m',
                 'op':'>','threshold':0.45,
                 'risk':'Full-size bus misses the authored through-lane path'},
    'fallback2':{'source':'native_samples.jsonl','metric':'bus_front_margin_before_walk_crosswalk_m',
                 'op':'<','threshold':1.0,
                 'risk':'Bus body stopping margin too small for the marked crossing'},
    'fallback3':{'source':'reference_corner.mkv','metric':'walk_display_pixel_margin_px',
                 'op':'<','threshold':40,
                 'risk':'Walk display is clipped or too small in original pixels'},
}


def parameters(case: str,candidate: str) -> dict:
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown exact Walk case or risk candidate')
    knobs={**BASE,**CHANGES.get(candidate,{})}
    return {'case':case,'candidate':candidate,
            'yield_policy':'yield_request' if case=='reference' else 'no_yield_request',
            'knobs':knobs,
            'trigger':TRIGGERS.get(candidate),
            'physical_acceptance_claimed':False}


if __name__=='__main__':
    import json
    rows=[parameters(case,candidate) for case in CASES for candidate in CANDIDATES]
    for case in CASES:
        group=[r for r in rows if r['case']==case]
        if len({tuple(sorted((k,str(v)) for k,v in r['knobs'].items())) for r in group})!=4:
            raise ValueError('Candidate engineering settings duplicate')
        if any(r['knobs']['camera_profile']!=BASE['camera_profile'] or
               r['knobs']['duration_s']!=24.0 for r in group):
            raise ValueError('Risk candidate changed capture profile')
    print(json.dumps({'cases':len(CASES),'candidate_plans':len(rows),
                      'distinct_triggers':len({(v['source'],v['metric']) for v in TRIGGERS.values()}),
                      'selected':False},sort_keys=True))
