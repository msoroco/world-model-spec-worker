"""Independent source comparison for the diagnostic guarded-lead hypothesis.

This does not claim a Native encounter or a legal immediate-hazard finding.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from window_audit import audit as audit_window


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(base, guarded):
    base, guarded = Path(base), Path(guarded)
    left, right = [read(root / 'config.json') for root in (base, guarded)]
    prefix = 'heldout__C228508__NRS-484B-650-1__motor_vehicle_driver__'
    if (left['selected_case_id'], right['selected_case_id']) != (prefix+'repeated_following', prefix+'no_hazard'):
        raise ValueError('Wrong hazard comparison identities')
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'duration_s',
                'required_atoms', 'source_packets', 'cameras', 'closing_encounters'):
        if left[key] != right[key]:
            raise ValueError('Fixed construction differs: ' + key)
    if left['engineering'] or right['engineering'] != {'hazard_guard_ttc_s': 3.0}:
        raise ValueError('Declared physical response difference missing or confounded')
    for name in ('video_frames.jsonl', 'driving_trace.jsonl', 'trace.jsonl'):
        if digest(base/name) != digest(guarded/name):
            raise ValueError('Fixed diagnostic original source differs: ' + name)
    a, b = rows(base/'following_sources.jsonl'), rows(guarded/'following_sources.jsonl')
    if len(a) != len(b) or not a:
        raise ValueError('Lead source row count differs')
    for x, y in zip(a, b):
        if (x['frame'], x['time_s'], x['ego'], x['lead']['position_m']) != (y['frame'], y['time_s'], y['ego'], y['lead']['position_m']):
            raise ValueError('Fixed body source differs')
        if not y['lead']['speed_mps'] > x['lead']['speed_mps']:
            raise ValueError('Guarded lead source does not differ physically')
    categories = [[event['category'] for event in read(root/'event_annotations.json')]
                  for root in (base, guarded)]
    if categories != [['speed','too_close','too_close','hazard'],
                      ['speed','too_close','too_close']]:
        raise ValueError('Diagnostic event hypothesis difference missing')
    windows = [audit_window(root, root/'analysis-report.json')['candidate_window']
               for root in (base, guarded)]
    if windows[0] is None or windows[1] is not None:
        raise ValueError('Measured diagnostic window difference missing')
    return {'format':'worker-following-hazard-comparison-audit',
            'comparison_id':'following_hazard_required',
            'case_ids':[left['selected_case_id'],right['selected_case_id']],
            'fixed_source_sha256':{name:digest(base/name) for name in
                                   ('video_frames.jsonl','driving_trace.jsonl','trace.jsonl')},
            'lead_source_sha256':[digest(root/'following_sources.jsonl') for root in (base, guarded)],
            'event_source_sha256':[digest(root/'event_annotations.json') for root in (base, guarded)],
            'auditor_sha256':digest(__file__),
            'scope':'synthetic software diagnostic only',
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--guarded',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();out=Path(a.output)
    if out.exists():raise ValueError('Retain prior comparison receipt')
    out.write_text(json.dumps(audit(a.base,a.guarded),indent=2)+'\n')

if __name__=='__main__':main()
