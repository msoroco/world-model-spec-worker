"""Independent physical path comparison for the manual-wheelchair branch."""
import argparse
import json
from pathlib import Path

FIXED=('law_id','cell_id','actor_id','map_sha256','ego_route_sha256',
       'wheelchair_identity_sha256','camera_contract_sha256','duration_s')


def audit(clear,crossing):
    if not clear.get('case_id','').endswith('__wheelchair_clear_path') or not crossing.get('case_id','').endswith('__wheelchair_crossing'):
        raise ValueError('wrong exact comparison cases')
    for name in FIXED:
        if not clear.get(name) or not crossing.get(name):
            raise ValueError('missing fixed condition: '+name)
        if clear[name]!=crossing[name]:
            raise ValueError('fixed condition differs: '+name)
    for record in (clear,crossing):
        measured=record.get('measurement',{})
        if measured.get('format')!='worker-manual-wheelchair-measurements' or not all(
            measured.get('sources',{}).get(source) for source in
            ('encounter-history.jsonl','intersection-context.json')):
            raise ValueError('missing source-bound manual-wheelchair measurement')
        if measured.get('frame_count',0)<2 or measured.get('minimum_surface_gap_m') is None:
            raise ValueError('insufficient original encounter evidence')
        if measured.get('contact_frames'):
            raise ValueError('observed contact fails collision-avoidance target')
        if measured.get('legal_due_care_verdict')!='unresolved':
            raise ValueError('comparison asserted a legal due-care verdict')
    if not crossing['measurement']['minimum_surface_gap_m']<clear['measurement']['minimum_surface_gap_m']:
        raise ValueError('declared path conflict difference was not physically observed')
    if crossing['measurement']['first_brake_frame'] is None:
        raise ValueError('crossing case lacks observed motorist brake response')
    return {'comparison_id':'manual_wheelchair_path_conflict','passed':True,
            'fixed_conditions':list(FIXED),'difference':'observed wheelchair path conflict and brake response',
            'legal_verdict':None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('clear');parser.add_argument('crossing')
    args=parser.parse_args()
    print(json.dumps(audit(json.loads(Path(args.clear).read_text()),
                           json.loads(Path(args.crossing).read_text())),indent=2))


if __name__=='__main__':main()
