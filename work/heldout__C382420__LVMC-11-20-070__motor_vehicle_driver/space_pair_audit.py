"""Independent diagnostic comparison of fixed entry conditions and blocker change."""
import argparse
import hashlib
import json
from pathlib import Path


CAMERAS = ('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(clear_spec, blocked_spec, clear_receipt, blocked_receipt):
    paths = [Path(x) for x in (clear_spec,blocked_spec,clear_receipt,blocked_receipt)]
    if any(not p.is_file() for p in paths):
        raise ValueError('missing comparison source')
    specs = [json.loads(p.read_text()) for p in paths[:2]]
    receipts = [json.loads(p.read_text()) for p in paths[2:]]
    scenes = [json.loads(s['files']['space_scene.json']) for s in specs]
    rows = [[json.loads(line) for line in s['files']['space_frames.jsonl'].splitlines()]
            for s in specs]
    if scenes[0].get('region_kind') not in ('marked_crosswalk','intersection') or \
            scenes[0].get('region_kind') != scenes[1].get('region_kind'):
        raise ValueError('changed entry alternative')
    if {k:v for k,v in scenes[0].items() if k!='case_id'} != \
            {k:v for k,v in scenes[1].items() if k!='case_id'}:
        raise ValueError('changed fixed entry or receiving geometry')
    if not rows[0] or len(rows[0]) != len(rows[1]):
        raise ValueError('missing joined entry frames')
    for a,b in zip(*rows):
        if a.get('downstream_occupants') != [] or len(b.get('downstream_occupants',[])) != 1:
            raise ValueError('missing single standing blocker difference')
        if b['downstream_occupants'][0].get('speed_mps') != 0:
            raise ValueError('blocker is not standing')
        if {k:v for k,v in a.items() if k!='downstream_occupants'} != \
                {k:v for k,v in b.items() if k!='downstream_occupants'}:
            raise ValueError('changed fixed ego, passage, signal or time source')
    for s in specs:
        videos = {v['path']:(v['frames'],v['width'],v['height'],v['fps']) for v in s['videos']}
        if set(videos) != set(CAMERAS):
            raise ValueError('missing named source camera')
    if not all(r.get('passed') and 'negative_case_source' in r.get('checks',[])
               for r in receipts):
        raise ValueError('missing source-bound compatibility receipt')
    entries = [r['measurement_examples']['space_at_entry']['value']['entry'] for r in receipts]
    if not (entries[0]['frame'] == entries[1]['frame'] and
            entries[0]['region_kind'] == entries[1]['region_kind'] == scenes[0]['region_kind'] and
            entries[0]['signal_state'] == entries[1]['signal_state'] and
            entries[0]['first_downstream_occupant'] is None and
            entries[1]['first_downstream_occupant'] is not None and
            entries[0]['downstream_available_length_m'] > entries[1]['downstream_available_length_m']):
        raise ValueError('missing measured blocker contrast at fixed entry')
    return {'format':'space-entry-pair-audit-v1','passed':True,
            'region_kind':scenes[0]['region_kind'],'entry_frame':entries[0]['frame'],
            'signal_state':entries[0]['signal_state'],
            'measured_available_length_m':[e['downstream_available_length_m'] for e in entries],
            'fixed':['entry geometry','ego body and time','participant passage','signal readback','four camera plans'],
            'changed':['standing downstream occupant footprint'],
            'sources':[{'path':str(p),'sha256':sha(p)} for p in paths],
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser = argparse.ArgumentParser()
    for name in ('clear_spec','blocked_spec','clear_receipt','blocked_receipt','output'):
        parser.add_argument('--'+name.replace('_','-'),required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.clear_spec,args.blocked_spec,
                                                  args.clear_receipt,args.blocked_receipt),indent=2)+'\n')


if __name__=='__main__':
    main()
