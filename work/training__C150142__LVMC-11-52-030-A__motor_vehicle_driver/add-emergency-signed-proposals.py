"""Add source-limited signed emergency comparison proposals."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build():
    path = ROOT / 'proposals/cases.json'
    document = json.loads(path.read_text())
    existing = {row['case_id']: row for row in document['cases']}
    result = []
    for suffix in ('business', 'no_business'):
        old = ROOT.name + '__emergency_vehicle_unsigned_' + suffix
        new = ROOT.name + '__emergency_vehicle_signed_' + suffix
        proposal = json.loads(json.dumps(existing[old]))
        proposal['case_id'] = new
        proposal['rationale'] = proposal['rationale'].replace('Unsigned red-curb',
            'Signed red-curb').replace('No exception sign',
            'Authored emergency-class exception sign; physical pixels unreviewed')
        proposal['variable_assignments']['sign_classes']['value'] = ['armored_or_emergency']
        proposal['variable_assignments']['road_and_actors']['value'] = (
            proposal['variable_assignments']['road_and_actors']['value']
            .replace('without exception sign', 'with emergency-class exception sign'))
        construction = json.loads((ROOT / 'selected-primary' /
            ('emergency_vehicle_signed_' + suffix) / 'construction.json').read_text())
        proposal['recording_description'] = construction['recording_description']
        proposal['unresolved_judgment_calls'].append(
            'The authored sign text and Native signal readback require physical visibility review.')
        if new in existing:
            if existing[new] != proposal:
                raise ValueError('Signed proposal differs from existing case')
            result.append({'case_id': new, 'added': False})
        else:
            document['cases'].append(proposal)
            result.append({'case_id': new, 'added': True})
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
