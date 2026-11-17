"""Bind four adjacent-mail diagnostic constructions to the CPU pipeline."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = 'mail_adjacent_deposit'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    source = json.loads((ROOT / 'execution-manifest-diagnostic-emergency-business-draft.json').read_text())
    entry = source['cases'][0]
    entry['case_id'] = ROOT.name + '__' + CASE
    entry['construction'] = 'selected-primary/' + CASE + '/construction.json'
    entry['construction_sha256'] = digest(ROOT / entry['construction'])
    entry['candidate_risk']['reason'] = (
        'Ordinary vehicle may overshoot red paint; the worker, attached parcel or '
        'authored mail box may be hidden by camera angle; physical deposit unverified')
    for candidate in entry['candidates']:
        ident = candidate['id']
        candidate['construction'] = f'selected-fallbacks/{CASE}/{ident}/construction.json'
        candidate['construction_sha256'] = digest(ROOT / candidate['construction'])
        trigger = candidate['trigger']
        for field in ('source','metric','failure_condition'):
            trigger[field] = trigger[field].replace('firetruck body', 'ordinary vehicle body').replace(
                'service-worker', 'mail worker').replace('red curb', 'red curb and mail box')
    target = ROOT / 'execution-manifest-diagnostic-mail-adjacent-deposit-draft.json'
    target.write_text(json.dumps(source, indent=2, allow_nan=False) + '\n')
    return {'manifest': str(target.relative_to(ROOT)), 'sha256': digest(target),
            'case_id': entry['case_id'], 'candidates': 4}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
