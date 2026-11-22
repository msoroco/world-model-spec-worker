"""Saved-only measurement of sign, dismount, and reversal events.

The capture must supply original phase-events.jsonl and sign-inventory.json with
SHA256 bindings in acquisition.json. This finalizer does not assign a legal label.
"""
import argparse
import hashlib
import json
from pathlib import Path

REQUIRED = ('phase-events.jsonl', 'sign-inventory.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_bound(attempt, acquisition, name):
    entry = acquisition.get(name)
    if not entry or entry.get('kind') != 'original_native' or not entry.get('sha256'):
        raise ValueError('missing original Native acquisition: ' + name)
    path = (attempt / name).resolve()
    if attempt.resolve() not in path.parents or not path.is_file() or sha(path) != entry['sha256']:
        raise ValueError('missing or changed source: ' + name)
    return path


def finalize(attempt):
    attempt = Path(attempt)
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    event_path = read_bound(attempt, acquisition, 'phase-events.jsonl')
    sign_path = read_bound(attempt, acquisition, 'sign-inventory.json')
    rows = [json.loads(line) for line in event_path.read_text().splitlines() if line.strip()]
    if not rows or any(rows[i]['frame'] >= rows[i+1]['frame'] or rows[i]['time_s'] >= rows[i+1]['time_s']
                       for i in range(len(rows)-1)):
        raise ValueError('phase events lack monotone original frame/time order')
    operators = {r.get('operator_id') for r in rows}
    bikes = {r.get('bicycle_id') for r in rows}
    if len(operators) != 1 or None in operators or len(bikes) != 1 or None in bikes:
        raise ValueError('operator or bicycle identity changes')
    sign = json.loads(sign_path.read_text())
    if sign.get('message') != 'NO U TURN' or not sign.get('erected') or not sign.get('authorization_source_sha256'):
        raise ValueError('governing sign identity/authorization missing')
    phases = {key: [r for r in rows if r.get('phase') == key]
              for key in ('mounted_approach','dismount_hold','afoot_reversal','mounted_reversal','turn_complete')}
    if not phases['mounted_approach'] or not phases['turn_complete']:
        raise ValueError('approach or completed reversal missing')
    start = min((r['time_s'] for name in ('afoot_reversal','mounted_reversal') for r in phases[name]), default=None)
    if start is None or phases['turn_complete'][0]['time_s'] <= start:
        raise ValueError('reversal phase or completion missing')
    dismounted = bool(phases['dismount_hold'])
    if dismounted:
        if not phases['afoot_reversal'] or phases['mounted_reversal']:
            raise ValueError('dismount phase conflicts with reversal body state')
        dismount_time = phases['dismount_hold'][0]['time_s']
        if not dismount_time < start:
            raise ValueError('dismount did not precede reversal')
    else:
        if not phases['mounted_reversal'] or phases['afoot_reversal']:
            raise ValueError('mounted reversal body state missing or mixed')
        dismount_time = None
    return {'format':'worker-phase-measurements','operator_id':next(iter(operators)),
            'bicycle_id':next(iter(bikes)),'observed_sign':sign,'dismount_time_s':dismount_time,
            'turn_start_s':start,'turn_complete_s':phases['turn_complete'][0]['time_s'],
            'dismounted_before_turn':dismounted,'source_sha256':{name:acquisition[name]['sha256'] for name in REQUIRED},
            'legal_judgment':'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = finalize(Path(args.attempt))
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':
    main()
