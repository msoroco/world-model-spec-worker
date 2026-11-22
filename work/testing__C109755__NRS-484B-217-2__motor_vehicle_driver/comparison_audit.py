"""Independent signal comparison over saved, source-bound measurements."""
import argparse
import json
from pathlib import Path

FIXED=('law_id','cell_id','actor_id','map_sha256','stripe_geometry_sha256',
       'route_sha256','oncoming_policy_sha256','following_policy_sha256',
       'camera_contract_sha256','duration_s')


def audit(signaled,unsignaled):
    for name in FIXED:
        if not signaled.get(name) or not unsignaled.get(name):
            raise ValueError('missing fixed condition: '+name)
        if signaled[name]!=unsignaled[name]:
            raise ValueError('fixed condition differs: '+name)
    for label,record in (('signaled',signaled),('unsignaled',unsignaled)):
        measured=record.get('measurement')
        if not measured or measured.get('format')!='worker-stripe-measurements' or not measured.get('turn_history_sha256') or not measured.get('zone_context_sha256'):
            raise ValueError(label+': missing source-bound stripe measurement')
        if measured['crossing_time_s'] is None:
            raise ValueError(label+': stripe crossing absent')
    a=signaled['measurement'];b=unsignaled['measurement']
    if not a['signal_active_at_crossing'] or a['signal_started_s'] is None or a['signal_started_s']>=a['crossing_time_s']:
        raise ValueError('signal not observed before crossing')
    if b['signal_active_at_crossing'] or b['signal_started_s'] is not None:
        raise ValueError('unsignaled comparison has observed signal')
    return {'comparison_id':'turn_signal_before_stripe','passed':True,
            'fixed_conditions':list(FIXED),'difference':'observed signal activation before crossing'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('signaled');parser.add_argument('unsignaled')
    args=parser.parse_args();print(json.dumps(audit(json.loads(Path(args.signaled).read_text()),
                                                  json.loads(Path(args.unsignaled).read_text())),indent=2))
if __name__=='__main__':main()
